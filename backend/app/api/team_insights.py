import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.db.base import get_db
from app.db.models import User, Team
from app.db.models.team_insight import TeamInsightRun, TeamInsightFinding
from app.auth.dependencies import get_current_user
from app.services.sync_logger import stream_log_events

router = APIRouter(
    prefix="/api/projects/{project_id}/teams/{team_id}/insights",
    tags=["team-insights"],
)


class TeamInsightRunOut(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    project_id: uuid.UUID
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    findings_count: int
    error_message: str | None = None
    model_config = {"from_attributes": True}


class TeamInsightFindingOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    team_id: uuid.UUID
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


class TeamInsightsSummary(BaseModel):
    total_active: int
    critical: int
    warning: int
    info: int
    resolved_30d: int
    by_category: dict[str, int]


async def _get_team(db: AsyncSession, project_id: uuid.UUID, team_id: uuid.UUID) -> Team:
    result = await db.execute(
        select(Team).where(Team.id == team_id, Team.project_id == project_id)
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


@router.get("", response_model=list[TeamInsightFindingOut])
async def list_findings(
    project_id: uuid.UUID,
    team_id: uuid.UUID,
    category: str | None = None,
    severity: str | None = None,
    finding_status: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_team(db, project_id, team_id)
    q = select(TeamInsightFinding).where(TeamInsightFinding.team_id == team_id)

    if category:
        q = q.where(TeamInsightFinding.category == category)
    if severity:
        q = q.where(TeamInsightFinding.severity == severity)
    if finding_status:
        q = q.where(TeamInsightFinding.status == finding_status)
    else:
        q = q.where(TeamInsightFinding.status == "active")

    q = q.order_by(
        TeamInsightFinding.severity,
        TeamInsightFinding.last_detected_at.desc(),
    )
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/summary", response_model=TeamInsightsSummary)
async def get_summary(
    project_id: uuid.UUID,
    team_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_team(db, project_id, team_id)
    base = select(TeamInsightFinding).where(
        TeamInsightFinding.team_id == team_id,
        TeamInsightFinding.status == "active",
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
    resolved_q = select(func.count()).select_from(TeamInsightFinding).where(
        TeamInsightFinding.team_id == team_id,
        TeamInsightFinding.status == "resolved",
        TeamInsightFinding.resolved_at >= cutoff,
    )
    resolved_30d = (await db.execute(resolved_q)).scalar() or 0

    return TeamInsightsSummary(
        total_active=len(findings),
        critical=critical,
        warning=warning,
        info=info,
        resolved_30d=resolved_30d,
        by_category=by_category,
    )


@router.get("/runs", response_model=list[TeamInsightRunOut])
async def list_runs(
    project_id: uuid.UUID,
    team_id: uuid.UUID,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_team(db, project_id, team_id)
    q = (
        select(TeamInsightRun)
        .where(TeamInsightRun.team_id == team_id)
        .order_by(TeamInsightRun.started_at.desc())
        .limit(limit)
    )
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/run", response_model=TeamInsightRunOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_run(
    project_id: uuid.UUID,
    team_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_team(db, project_id, team_id)

    stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    stale_q = select(TeamInsightRun).where(
        TeamInsightRun.team_id == team_id,
        TeamInsightRun.status == "running",
        TeamInsightRun.started_at < stale_cutoff,
    )
    stale_runs = (await db.execute(stale_q)).scalars().all()
    for sr in stale_runs:
        sr.status = "failed"
        sr.error_message = "Timed out (stale run detected)"
        sr.finished_at = datetime.now(timezone.utc)
    if stale_runs:
        await db.commit()

    from app.workers.tasks import run_team_insights
    run = TeamInsightRun(team_id=team_id, project_id=project_id, status="running")
    db.add(run)
    await db.commit()
    await db.refresh(run)

    run_team_insights.delay(str(run.id), str(team_id), str(project_id))
    return run


@router.get("/runs/{run_id}/logs")
async def stream_run_logs(
    request: Request,
    project_id: uuid.UUID,
    team_id: uuid.UUID,
    run_id: uuid.UUID,
    token: str | None = Query(default=None),
):
    """Stream team insight-run logs via SSE."""
    from app.auth.security import decode_token as decode_jwt
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token required")
    payload = decode_jwt(token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    list_key = f"sync:logs:team-insights-{run_id}"
    channel_key = f"sync:logs:live:team-insights-{run_id}"

    return EventSourceResponse(stream_log_events(list_key, channel_key, request))


@router.patch("/{finding_id}/dismiss", response_model=TeamInsightFindingOut)
async def dismiss_finding(
    project_id: uuid.UUID,
    team_id: uuid.UUID,
    finding_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TeamInsightFinding).where(
            TeamInsightFinding.id == finding_id,
            TeamInsightFinding.team_id == team_id,
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
