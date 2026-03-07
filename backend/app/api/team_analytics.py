"""Team-scoped analytics API — code stats, delivery metrics, and insights."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.db.base import get_db
from app.db.models.user import User
from app.db.models.team import Team, TeamMember
from app.db.models.work_item import WorkItem
from app.db.models.contributor import Contributor
from app.db.models.iteration import Iteration
from app.db.models.insight import InsightFinding, InsightStatus, InsightCategory
from app.services.metrics import (
    get_team_code_stats,
    get_team_code_activity,
    get_team_member_stats,
)
from app.services.delivery_metrics import (
    DeliveryFilters,
    get_delivery_stats,
    get_velocity,
    get_cycle_time_distribution,
    get_wip_by_state,
    get_cumulative_flow,
    get_stale_backlog,
    get_backlog_age_distribution,
    get_backlog_growth,
    get_bug_trend,
    get_bug_resolution_time,
    get_defect_density,
    get_intersection_metrics,
)

router = APIRouter(
    prefix="/api/projects/{project_id}/teams/{team_id}/analytics",
    tags=["team-analytics"],
)


async def _get_team_member_ids(
    db: AsyncSession, project_id: uuid.UUID, team_id: uuid.UUID,
) -> list[uuid.UUID]:
    team_q = select(Team).where(Team.id == team_id, Team.project_id == project_id)
    team = (await db.execute(team_q)).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    member_q = select(TeamMember.contributor_id).where(TeamMember.team_id == team_id)
    rows = (await db.execute(member_q)).scalars().all()
    return list(rows)


def _parse_date(val: str | None) -> date | None:
    if not val:
        return None
    return date.fromisoformat(val)


# ── Code endpoints ───────────────────────────────────────────────────

@router.get("/code")
async def team_code_stats(
    project_id: uuid.UUID,
    team_id: uuid.UUID,
    from_date: str | None = None,
    to_date: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    member_ids = await _get_team_member_ids(db, project_id, team_id)
    return await get_team_code_stats(
        db, project_id, member_ids,
        from_date=_parse_date(from_date),
        to_date=_parse_date(to_date),
    )


@router.get("/code/activity")
async def team_code_activity(
    project_id: uuid.UUID,
    team_id: uuid.UUID,
    from_date: str | None = None,
    to_date: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    member_ids = await _get_team_member_ids(db, project_id, team_id)
    return await get_team_code_activity(
        db, project_id, member_ids,
        from_date=_parse_date(from_date),
        to_date=_parse_date(to_date),
    )


@router.get("/code/members")
async def team_code_members(
    project_id: uuid.UUID,
    team_id: uuid.UUID,
    from_date: str | None = None,
    to_date: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    member_ids = await _get_team_member_ids(db, project_id, team_id)
    return await get_team_member_stats(
        db, project_id, member_ids,
        from_date=_parse_date(from_date),
        to_date=_parse_date(to_date),
    )


# ── Delivery endpoints ──────────────────────────────────────────────

def _delivery_filters(
    team_id: uuid.UUID,
    from_date: str | None = None,
    to_date: str | None = None,
) -> DeliveryFilters:
    return DeliveryFilters(
        team_id=team_id,
        from_date=_parse_date(from_date),
        to_date=_parse_date(to_date),
    )


@router.get("/delivery")
async def team_delivery_stats(
    project_id: uuid.UUID,
    team_id: uuid.UUID,
    from_date: str | None = None,
    to_date: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_team_member_ids(db, project_id, team_id)
    filters = _delivery_filters(team_id, from_date, to_date)
    return await get_delivery_stats(db, project_id, filters=filters)


@router.get("/delivery/velocity")
async def team_delivery_velocity(
    project_id: uuid.UUID,
    team_id: uuid.UUID,
    from_date: str | None = None,
    to_date: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_team_member_ids(db, project_id, team_id)
    filters = _delivery_filters(team_id, from_date, to_date)
    return await get_velocity(db, project_id, filters=filters)


@router.get("/delivery/flow")
async def team_delivery_flow(
    project_id: uuid.UUID,
    team_id: uuid.UUID,
    from_date: str | None = None,
    to_date: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_team_member_ids(db, project_id, team_id)
    filters = _delivery_filters(team_id, from_date, to_date)
    return {
        "cycle_time_distribution": await get_cycle_time_distribution(db, project_id, filters=filters),
        "wip_by_state": await get_wip_by_state(db, project_id, filters=filters),
        "cumulative_flow": await get_cumulative_flow(db, project_id, filters=filters),
    }


@router.get("/delivery/backlog")
async def team_delivery_backlog(
    project_id: uuid.UUID,
    team_id: uuid.UUID,
    from_date: str | None = None,
    to_date: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_team_member_ids(db, project_id, team_id)
    filters = _delivery_filters(team_id, from_date, to_date)
    return {
        "stale_items": await get_stale_backlog(db, project_id, filters=filters),
        "age_distribution": await get_backlog_age_distribution(db, project_id, filters=filters),
        "growth": await get_backlog_growth(db, project_id, filters=filters),
    }


@router.get("/delivery/quality")
async def team_delivery_quality(
    project_id: uuid.UUID,
    team_id: uuid.UUID,
    from_date: str | None = None,
    to_date: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_team_member_ids(db, project_id, team_id)
    filters = _delivery_filters(team_id, from_date, to_date)
    res_time = await get_bug_resolution_time(db, project_id, filters=filters)
    density = await get_defect_density(db, project_id, filters=filters)
    return {
        "bug_trend": await get_bug_trend(db, project_id, filters=filters),
        "resolution_time": res_time,
        "defect_density": {
            "bugs": density["bug_count"],
            "total": density["total_items"],
            "ratio": density["defect_density_pct"],
        },
    }


@router.get("/delivery/intersection")
async def team_delivery_intersection(
    project_id: uuid.UUID,
    team_id: uuid.UUID,
    from_date: str | None = None,
    to_date: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_team_member_ids(db, project_id, team_id)
    filters = _delivery_filters(team_id, from_date, to_date)
    return await get_intersection_metrics(db, project_id, filters=filters)


@router.get("/delivery/work-items")
async def team_work_items(
    project_id: uuid.UUID,
    team_id: uuid.UUID,
    state: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    member_ids = await _get_team_member_ids(db, project_id, team_id)
    if not member_ids:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    q = (
        select(WorkItem)
        .where(
            WorkItem.project_id == project_id,
            WorkItem.assigned_to_id.in_(member_ids),
        )
        .options(
            selectinload(WorkItem.assigned_to),
            selectinload(WorkItem.iteration),
        )
    )
    if state:
        q = q.where(WorkItem.state == state)
    if search:
        q = q.where(
            or_(
                WorkItem.title.ilike(f"%{search}%"),
                WorkItem.platform_work_item_id.ilike(f"%{search}%"),
            )
        )

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = q.order_by(WorkItem.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()

    return {
        "items": [
            {
                "id": str(wi.id),
                "platform_work_item_id": wi.platform_work_item_id,
                "title": wi.title,
                "work_item_type": wi.work_item_type,
                "state": wi.state,
                "story_points": wi.story_points,
                "priority": wi.priority,
                "assigned_to": {"id": str(wi.assigned_to.id), "name": wi.assigned_to.canonical_name} if wi.assigned_to else None,
                "iteration_name": wi.iteration.name if wi.iteration else None,
                "platform_url": wi.platform_url,
                "updated_at": wi.updated_at.isoformat() if wi.updated_at else None,
            }
            for wi in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ── Insights endpoint ────────────────────────────────────────────────

@router.get("/insights")
async def team_insights(
    project_id: uuid.UUID,
    team_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    member_ids = await _get_team_member_ids(db, project_id, team_id)
    member_id_strs = [str(mid) for mid in member_ids]

    q = (
        select(InsightFinding)
        .where(
            InsightFinding.project_id == project_id,
            InsightFinding.status == InsightStatus.ACTIVE,
        )
    )

    if member_id_strs:
        q = q.where(
            or_(
                InsightFinding.category == InsightCategory.TEAM_BALANCE,
                *[
                    InsightFinding.affected_entities["contributors"].astext.contains(mid)
                    for mid in member_id_strs
                ],
            )
        )
    else:
        q = q.where(InsightFinding.category == InsightCategory.TEAM_BALANCE)

    q = q.order_by(InsightFinding.severity, InsightFinding.last_detected_at.desc())
    result = await db.execute(q)
    findings = result.scalars().all()

    return [
        {
            "id": str(f.id),
            "run_id": str(f.run_id),
            "project_id": str(f.project_id),
            "category": f.category.value if hasattr(f.category, "value") else f.category,
            "severity": f.severity.value if hasattr(f.severity, "value") else f.severity,
            "slug": f.slug,
            "title": f.title,
            "description": f.description,
            "recommendation": f.recommendation,
            "metric_data": f.metric_data,
            "affected_entities": f.affected_entities,
            "status": f.status.value if hasattr(f.status, "value") else f.status,
            "first_detected_at": f.first_detected_at.isoformat() if f.first_detected_at else None,
            "last_detected_at": f.last_detected_at.isoformat() if f.last_detected_at else None,
        }
        for f in findings
    ]
