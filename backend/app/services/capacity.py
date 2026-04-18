"""Team capacity vs. load analytics.

Capacity is derived from the rolling average of story points completed in the
last ``rolling_capacity_sprints`` (default 3) *closed* iterations for a team.
Load is the total planned story points in a given iteration.

Uses :class:`app.db.models.project_delivery_settings.ProjectDeliverySettings`
for the rolling window size and the ready-states list.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.iteration import Iteration
from app.db.models.project_delivery_settings import ProjectDeliverySettings
from app.db.models.team import TeamMember
from app.db.models.work_item import WorkItem


def _team_member_subq(team_id: uuid.UUID):
    return select(TeamMember.contributor_id).where(TeamMember.team_id == team_id)


async def _resolve_settings(
    db: AsyncSession, project_id: uuid.UUID,
) -> tuple[int, list[str]]:
    row = (
        await db.execute(
            select(ProjectDeliverySettings).where(
                ProjectDeliverySettings.project_id == project_id,
            )
        )
    ).scalar_one_or_none()
    rolling = row.rolling_capacity_sprints if row and row.rolling_capacity_sprints else 3
    ready_states = list(row.ready_states) if row and row.ready_states else [
        "Ready", "Approved", "Committed",
    ]
    return rolling, ready_states


async def get_team_capacity_vs_load(
    db: AsyncSession,
    project_id: uuid.UUID,
    team_id: uuid.UUID,
    *,
    iteration_id: uuid.UUID | None = None,
) -> dict:
    """Return capacity, planned load, and readiness for a team in one iteration.

    If ``iteration_id`` is not provided, the currently active iteration
    (today falls within its start/end window) is used. If none is active,
    the next upcoming iteration is used. Otherwise returns an empty response.
    """
    rolling, ready_states = await _resolve_settings(db, project_id)
    wi = WorkItem.__table__
    it = Iteration.__table__
    member_sub = _team_member_subq(team_id)

    target_iter_row = None
    if iteration_id is not None:
        target_iter_row = (await db.execute(
            select(it.c.id, it.c.name, it.c.path, it.c.start_date, it.c.end_date)
            .where(it.c.id == iteration_id, it.c.project_id == project_id)
        )).first()
    else:
        today = date.today()
        target_iter_row = (await db.execute(
            select(it.c.id, it.c.name, it.c.path, it.c.start_date, it.c.end_date)
            .where(
                it.c.project_id == project_id,
                it.c.start_date <= today,
                it.c.end_date >= today,
            )
            .order_by(it.c.start_date.desc())
            .limit(1)
        )).first()
        if target_iter_row is None:
            target_iter_row = (await db.execute(
                select(it.c.id, it.c.name, it.c.path, it.c.start_date, it.c.end_date)
                .where(
                    it.c.project_id == project_id,
                    it.c.start_date > today,
                )
                .order_by(it.c.start_date.asc())
                .limit(1)
            )).first()

    completed_iters_q = (
        select(it.c.id, it.c.name, it.c.start_date, it.c.end_date)
        .where(
            it.c.project_id == project_id,
            it.c.end_date.isnot(None),
        )
        .order_by(it.c.end_date.desc())
        .limit(rolling + 5)
    )
    if target_iter_row is not None and target_iter_row.start_date is not None:
        completed_iters_q = completed_iters_q.where(it.c.end_date < target_iter_row.start_date)
    completed_iter_rows = (await db.execute(completed_iters_q)).all()

    history: list[dict] = []
    for cit in completed_iter_rows[:rolling]:
        v_q = (
            select(func.coalesce(func.sum(wi.c.story_points), 0))
            .select_from(wi)
            .where(
                wi.c.project_id == project_id,
                wi.c.iteration_id == cit.id,
                wi.c.assigned_to_id.in_(member_sub),
                wi.c.resolved_at.isnot(None),
            )
        )
        points = (await db.execute(v_q)).scalar() or 0
        history.append({
            "iteration_id": str(cit.id),
            "iteration_name": cit.name,
            "start_date": cit.start_date.isoformat() if cit.start_date else None,
            "end_date": cit.end_date.isoformat() if cit.end_date else None,
            "completed_points": float(points),
        })

    if history:
        avg_capacity = sum(h["completed_points"] for h in history) / len(history)
    else:
        avg_capacity = 0.0

    response: dict = {
        "team_id": str(team_id),
        "rolling_window": len(history),
        "avg_capacity_points": round(avg_capacity, 1),
        "capacity_history": history,
    }

    if target_iter_row is None:
        response["target_iteration"] = None
        response["planned_points"] = 0.0
        response["ready_points"] = 0.0
        response["load_ratio"] = 0.0
        return response

    planned_q = (
        select(
            func.coalesce(func.sum(wi.c.story_points), 0).label("planned_points"),
            func.count().label("planned_items"),
            func.sum(case((wi.c.story_points.is_(None), 1), else_=0)).label("unestimated_items"),
            func.coalesce(
                func.sum(
                    case(
                        (wi.c.state.in_(tuple(ready_states)), wi.c.story_points),
                        else_=0,
                    )
                ), 0,
            ).label("ready_points"),
        )
        .select_from(wi)
        .where(
            wi.c.project_id == project_id,
            wi.c.iteration_id == target_iter_row.id,
            wi.c.assigned_to_id.in_(member_sub),
        )
    )
    planned_row = (await db.execute(planned_q)).one()
    planned_points = float(planned_row.planned_points or 0)
    ready_points = float(planned_row.ready_points or 0)
    load_ratio = (planned_points / avg_capacity) if avg_capacity else None

    response["target_iteration"] = {
        "id": str(target_iter_row.id),
        "name": target_iter_row.name,
        "path": target_iter_row.path,
        "start_date": target_iter_row.start_date.isoformat() if target_iter_row.start_date else None,
        "end_date": target_iter_row.end_date.isoformat() if target_iter_row.end_date else None,
    }
    response["planned_points"] = round(planned_points, 1)
    response["planned_items"] = int(planned_row.planned_items or 0)
    response["unestimated_items"] = int(planned_row.unestimated_items or 0)
    response["ready_points"] = round(ready_points, 1)
    response["load_ratio"] = round(load_ratio, 2) if load_ratio is not None else None

    if load_ratio is None:
        status = "unknown"
    elif load_ratio > 1.25:
        status = "overloaded"
    elif load_ratio > 1.05:
        status = "over-capacity"
    elif load_ratio < 0.75:
        status = "under-loaded"
    else:
        status = "balanced"
    response["load_status"] = status

    return response
