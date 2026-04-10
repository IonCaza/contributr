import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.db.base import get_db
from app.db.models import User, Contributor
from app.db.models.contributor_insight import ContributorInsightRun, ContributorInsightFinding
from app.auth.dependencies import get_current_user
from app.services.sync_logger import stream_log_events

router = APIRouter(
    prefix="/api/contributors/{contributor_id}/insights",
    tags=["contributor-insights"],
)


class ContributorInsightRunOut(BaseModel):
    id: uuid.UUID
    contributor_id: uuid.UUID
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    findings_count: int
    error_message: str | None = None
    model_config = {"from_attributes": True}


class ContributorInsightFindingOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    contributor_id: uuid.UUID
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


class ContributorInsightsSummary(BaseModel):
    total_active: int
    critical: int
    warning: int
    info: int
    resolved_30d: int
    by_category: dict[str, int]


async def _get_contributor(db: AsyncSession, contributor_id: uuid.UUID) -> Contributor:
    result = await db.execute(select(Contributor).where(Contributor.id == contributor_id))
    contributor = result.scalar_one_or_none()
    if not contributor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contributor not found")
    return contributor


@router.get("", response_model=list[ContributorInsightFindingOut])
async def list_findings(
    contributor_id: uuid.UUID,
    category: str | None = None,
    severity: str | None = None,
    finding_status: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_contributor(db, contributor_id)
    q = select(ContributorInsightFinding).where(
        ContributorInsightFinding.contributor_id == contributor_id,
    )

    if category:
        q = q.where(ContributorInsightFinding.category == category)
    if severity:
        q = q.where(ContributorInsightFinding.severity == severity)
    if finding_status:
        q = q.where(ContributorInsightFinding.status == finding_status)
    else:
        q = q.where(ContributorInsightFinding.status == "active")

    q = q.order_by(
        ContributorInsightFinding.severity,
        ContributorInsightFinding.last_detected_at.desc(),
    )
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/summary", response_model=ContributorInsightsSummary)
async def get_summary(
    contributor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_contributor(db, contributor_id)
    base = select(ContributorInsightFinding).where(
        ContributorInsightFinding.contributor_id == contributor_id,
        ContributorInsightFinding.status == "active",
    )
    active = await db.execute(base)
    findings = active.scalars().all()

    critical = sum(1 for f in findings if f.severity == "critical")
    warning = sum(1 for f in findings if f.severity == "warning")
    info = sum(1 for f in findings if f.severity == "info")

    by_category: dict[str, int] = {}
    for f in findings:
        by_category[f.category] = by_category.get(f.category, 0) + 1

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    resolved_q = select(func.count()).select_from(ContributorInsightFinding).where(
        ContributorInsightFinding.contributor_id == contributor_id,
        ContributorInsightFinding.status == "resolved",
        ContributorInsightFinding.resolved_at >= cutoff,
    )
    resolved_30d = (await db.execute(resolved_q)).scalar() or 0

    return ContributorInsightsSummary(
        total_active=len(findings),
        critical=critical,
        warning=warning,
        info=info,
        resolved_30d=resolved_30d,
        by_category=by_category,
    )


@router.get("/runs", response_model=list[ContributorInsightRunOut])
async def list_runs(
    contributor_id: uuid.UUID,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_contributor(db, contributor_id)
    q = (
        select(ContributorInsightRun)
        .where(ContributorInsightRun.contributor_id == contributor_id)
        .order_by(ContributorInsightRun.started_at.desc())
        .limit(limit)
    )
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/run", response_model=ContributorInsightRunOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_run(
    contributor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_contributor(db, contributor_id)

    stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    stale_q = select(ContributorInsightRun).where(
        ContributorInsightRun.contributor_id == contributor_id,
        ContributorInsightRun.status == "running",
        ContributorInsightRun.started_at < stale_cutoff,
    )
    stale_runs = (await db.execute(stale_q)).scalars().all()
    for sr in stale_runs:
        sr.status = "failed"
        sr.error_message = "Timed out (stale run detected)"
        sr.finished_at = datetime.now(timezone.utc)
    if stale_runs:
        await db.commit()

    from app.workers.tasks import run_contributor_insights
    run = ContributorInsightRun(contributor_id=contributor_id, status="running")
    db.add(run)
    await db.commit()
    await db.refresh(run)

    run_contributor_insights.delay(str(run.id), str(contributor_id))
    return run


@router.get("/runs/{run_id}/logs")
async def stream_run_logs(
    request: Request,
    contributor_id: uuid.UUID,
    run_id: uuid.UUID,
    token: str | None = Query(default=None),
):
    """Stream contributor insight-run logs via SSE."""
    from app.auth.security import decode_token as decode_jwt
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token required")
    payload = decode_jwt(token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    list_key = f"sync:logs:contributor-insights-{run_id}"
    channel_key = f"sync:logs:live:contributor-insights-{run_id}"

    return EventSourceResponse(stream_log_events(list_key, channel_key, request))


@router.patch("/{finding_id}/dismiss", response_model=ContributorInsightFindingOut)
async def dismiss_finding(
    contributor_id: uuid.UUID,
    finding_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ContributorInsightFinding).where(
            ContributorInsightFinding.id == finding_id,
            ContributorInsightFinding.contributor_id == contributor_id,
        )
    )
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")

    finding.status = "dismissed"
    finding.dismissed_at = datetime.now(timezone.utc)
    finding.dismissed_by_id = user.id
    await db.commit()
    await db.refresh(finding)
    return finding
