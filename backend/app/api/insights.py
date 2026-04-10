import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.db.base import get_db
from app.db.models import User, Project
from app.db.models.insight import (
    InsightRun, InsightFinding, InsightRunStatus,
    InsightCategory, InsightSeverity, InsightStatus,
)
from app.auth.dependencies import get_current_user
from app.services.sync_logger import stream_log_events

router = APIRouter(
    prefix="/api/projects/{project_id}/insights",
    tags=["insights"],
)


class InsightRunOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    findings_count: int
    error_message: str | None = None
    model_config = {"from_attributes": True}


class InsightFindingOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    project_id: uuid.UUID
    category: str
    severity: str
    slug: str
    title: str
    description: str
    recommendation: str
    metric_data: dict | None = None
    affected_entities: dict | None = None
    status: str
    first_detected_at: datetime
    last_detected_at: datetime
    resolved_at: datetime | None = None
    dismissed_at: datetime | None = None
    dismissed_by_id: uuid.UUID | None = None
    model_config = {"from_attributes": True}


class InsightsSummary(BaseModel):
    total_active: int
    critical: int
    warning: int
    info: int
    resolved_30d: int
    by_category: dict[str, int]


async def _get_project(db: AsyncSession, project_id: uuid.UUID) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.get("", response_model=list[InsightFindingOut])
async def list_findings(
    project_id: uuid.UUID,
    category: str | None = None,
    severity: str | None = None,
    finding_status: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_project(db, project_id)
    q = select(InsightFinding).where(InsightFinding.project_id == project_id)

    if category:
        q = q.where(InsightFinding.category == InsightCategory(category))
    if severity:
        q = q.where(InsightFinding.severity == InsightSeverity(severity))
    if finding_status:
        q = q.where(InsightFinding.status == InsightStatus(finding_status))
    else:
        q = q.where(InsightFinding.status == InsightStatus.ACTIVE)

    q = q.order_by(
        InsightFinding.severity,
        InsightFinding.last_detected_at.desc(),
    )
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/summary", response_model=InsightsSummary)
async def get_summary(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_project(db, project_id)
    base = select(InsightFinding).where(
        InsightFinding.project_id == project_id,
        InsightFinding.status == InsightStatus.ACTIVE,
    )

    active = await db.execute(base)
    findings = active.scalars().all()

    critical = sum(1 for f in findings if f.severity == InsightSeverity.CRITICAL)
    warning = sum(1 for f in findings if f.severity == InsightSeverity.WARNING)
    info = sum(1 for f in findings if f.severity == InsightSeverity.INFO)

    by_category: dict[str, int] = {}
    for f in findings:
        cat = f.category.value if hasattr(f.category, "value") else str(f.category)
        by_category[cat] = by_category.get(cat, 0) + 1

    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    resolved_q = select(func.count()).select_from(InsightFinding).where(
        InsightFinding.project_id == project_id,
        InsightFinding.status == InsightStatus.RESOLVED,
        InsightFinding.resolved_at >= cutoff,
    )
    resolved_30d = (await db.execute(resolved_q)).scalar() or 0

    return InsightsSummary(
        total_active=len(findings),
        critical=critical,
        warning=warning,
        info=info,
        resolved_30d=resolved_30d,
        by_category=by_category,
    )


@router.get("/runs", response_model=list[InsightRunOut])
async def list_runs(
    project_id: uuid.UUID,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_project(db, project_id)
    q = (
        select(InsightRun)
        .where(InsightRun.project_id == project_id)
        .order_by(InsightRun.started_at.desc())
        .limit(limit)
    )
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/run", response_model=InsightRunOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_run(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_project(db, project_id)

    from datetime import timedelta
    stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    stale_q = select(InsightRun).where(
        InsightRun.project_id == project_id,
        InsightRun.status == InsightRunStatus.RUNNING,
        InsightRun.started_at < stale_cutoff,
    )
    stale_runs = (await db.execute(stale_q)).scalars().all()
    for sr in stale_runs:
        sr.status = InsightRunStatus.FAILED
        sr.error_message = "Timed out (stale run detected)"
        sr.finished_at = datetime.now(timezone.utc)
    if stale_runs:
        await db.commit()

    from app.workers.tasks import run_project_insights
    run = InsightRun(project_id=project_id, status=InsightRunStatus.RUNNING)
    db.add(run)
    await db.commit()
    await db.refresh(run)

    run_project_insights.delay(str(run.id), str(project_id))
    return run


@router.get("/runs/{run_id}/logs")
async def stream_run_logs(
    request: Request,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    token: str | None = Query(default=None),
):
    """Stream insight-run logs in real-time via Server-Sent Events."""
    from app.auth.security import decode_token as decode_jwt
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token required")
    payload = decode_jwt(token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    list_key = f"sync:logs:insights-{run_id}"
    channel_key = f"sync:logs:live:insights-{run_id}"

    return EventSourceResponse(stream_log_events(list_key, channel_key, request))


@router.patch("/{finding_id}/dismiss", response_model=InsightFindingOut)
async def dismiss_finding(
    project_id: uuid.UUID,
    finding_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(InsightFinding).where(
            InsightFinding.id == finding_id,
            InsightFinding.project_id == project_id,
        )
    )
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")

    finding.status = InsightStatus.DISMISSED
    finding.dismissed_at = datetime.now(timezone.utc)
    finding.dismissed_by_id = user.id
    await db.commit()
    await db.refresh(finding)
    return finding
