"""Delivery analytics metrics computed from work items and iterations."""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select, func, case, and_, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.work_item import WorkItem
from app.db.models.iteration import Iteration
from app.db.models.daily_delivery_stats import DailyDeliveryStats


async def get_delivery_stats(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    team_id: uuid.UUID | None = None,
    contributor_id: uuid.UUID | None = None,
) -> dict:
    """Aggregate delivery stats for a project, optionally filtered by team or contributor."""
    wi = WorkItem.__table__
    base = wi.c.project_id == project_id

    filters = [base]
    if contributor_id:
        filters.append(wi.c.assigned_to_id == contributor_id)

    total_q = select(func.count()).select_from(wi).where(*filters)
    total = (await db.execute(total_q)).scalar() or 0

    open_states = ("New", "Active", "Committed", "In Progress", "Approved")
    open_q = select(func.count()).select_from(wi).where(*filters, wi.c.state.in_(open_states))
    open_items = (await db.execute(open_q)).scalar() or 0

    completed_q = select(func.count()).select_from(wi).where(
        *filters, wi.c.state.in_(("Resolved", "Closed", "Done", "Completed"))
    )
    completed = (await db.execute(completed_q)).scalar() or 0

    total_sp_q = select(func.coalesce(func.sum(wi.c.story_points), 0)).select_from(wi).where(*filters)
    total_sp = (await db.execute(total_sp_q)).scalar() or 0

    completed_sp_q = select(func.coalesce(func.sum(wi.c.story_points), 0)).select_from(wi).where(
        *filters, wi.c.resolved_at.isnot(None)
    )
    completed_sp = (await db.execute(completed_sp_q)).scalar() or 0

    cycle_q = select(
        func.percentile_cont(0.5).within_group(
            extract("epoch", wi.c.resolved_at - wi.c.activated_at) / 3600
        ).label("median"),
        func.percentile_cont(0.9).within_group(
            extract("epoch", wi.c.resolved_at - wi.c.activated_at) / 3600
        ).label("p90"),
    ).select_from(wi).where(
        *filters, wi.c.activated_at.isnot(None), wi.c.resolved_at.isnot(None),
    )
    cycle_row = (await db.execute(cycle_q)).one_or_none()
    avg_cycle = round(cycle_row.median or 0, 1) if cycle_row else 0

    lead_q = select(
        func.percentile_cont(0.5).within_group(
            extract("epoch", wi.c.closed_at - wi.c.created_at) / 3600
        ).label("median"),
    ).select_from(wi).where(*filters, wi.c.closed_at.isnot(None))
    lead_row = (await db.execute(lead_q)).one_or_none()
    avg_lead = round(lead_row.median or 0, 1) if lead_row else 0

    type_q = select(
        wi.c.work_item_type, func.count()
    ).select_from(wi).where(*filters).group_by(wi.c.work_item_type)
    backlog_by_type = [{"type": r[0], "count": r[1]} for r in (await db.execute(type_q)).all()]

    state_q = select(
        wi.c.state, func.count()
    ).select_from(wi).where(*filters).group_by(wi.c.state)
    backlog_by_state = [{"state": r[0], "count": r[1]} for r in (await db.execute(state_q)).all()]

    velocity_trend = await get_velocity(db, project_id, limit=10)
    throughput_trend = await get_throughput_trend(db, project_id, days=90)

    return {
        "total_work_items": total,
        "open_items": open_items,
        "completed_items": completed,
        "total_story_points": total_sp,
        "completed_story_points": completed_sp,
        "avg_cycle_time_hours": avg_cycle,
        "avg_lead_time_hours": avg_lead,
        "velocity_trend": velocity_trend,
        "throughput_trend": throughput_trend,
        "backlog_by_type": backlog_by_type,
        "backlog_by_state": backlog_by_state,
    }


async def get_velocity(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    limit: int = 10,
) -> list[dict]:
    """Story points completed per iteration."""
    wi = WorkItem.__table__
    it = Iteration.__table__
    q = (
        select(
            it.c.name.label("iteration"),
            it.c.start_date,
            func.coalesce(func.sum(wi.c.story_points), 0).label("points"),
        )
        .select_from(wi.join(it, wi.c.iteration_id == it.c.id))
        .where(
            wi.c.project_id == project_id,
            wi.c.resolved_at.isnot(None),
        )
        .group_by(it.c.name, it.c.start_date)
        .order_by(it.c.start_date.desc())
        .limit(limit)
    )
    rows = (await db.execute(q)).all()
    return [{"iteration": r.iteration, "points": round(r.points, 1)} for r in reversed(rows)]


async def get_throughput_trend(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    days: int = 90,
) -> list[dict]:
    """Daily created vs. completed item counts."""
    wi = WorkItem.__table__
    cutoff = date.today() - timedelta(days=days)

    created_q = (
        select(
            func.date_trunc("day", wi.c.created_at).cast(func.current_date().type).label("d"),
            func.count().label("created"),
        )
        .where(wi.c.project_id == project_id, func.date(wi.c.created_at) >= cutoff)
        .group_by("d")
    )
    created_rows = {str(r.d): r.created for r in (await db.execute(created_q)).all()}

    completed_q = (
        select(
            func.date_trunc("day", wi.c.resolved_at).cast(func.current_date().type).label("d"),
            func.count().label("completed"),
        )
        .where(wi.c.project_id == project_id, wi.c.resolved_at.isnot(None), func.date(wi.c.resolved_at) >= cutoff)
        .group_by("d")
    )
    completed_rows = {str(r.d): r.completed for r in (await db.execute(completed_q)).all()}

    all_dates = sorted(set(list(created_rows.keys()) + list(completed_rows.keys())))
    return [
        {"date": d, "created": created_rows.get(d, 0), "completed": completed_rows.get(d, 0)}
        for d in all_dates
    ]


async def get_iteration_detail(
    db: AsyncSession,
    iteration_id: uuid.UUID,
) -> dict:
    """Stats for a single iteration."""
    wi = WorkItem.__table__
    base = wi.c.iteration_id == iteration_id

    total = (await db.execute(select(func.count()).where(base))).scalar() or 0
    completed = (await db.execute(
        select(func.count()).where(base, wi.c.resolved_at.isnot(None))
    )).scalar() or 0
    total_sp = (await db.execute(
        select(func.coalesce(func.sum(wi.c.story_points), 0)).where(base)
    )).scalar() or 0
    completed_sp = (await db.execute(
        select(func.coalesce(func.sum(wi.c.story_points), 0)).where(base, wi.c.resolved_at.isnot(None))
    )).scalar() or 0

    return {
        "total_items": total,
        "completed_items": completed,
        "total_points": round(total_sp, 1),
        "completed_points": round(completed_sp, 1),
    }
