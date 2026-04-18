"""Sprint carry-over analytics.

A work item "carries over" from iteration A to iteration B when its
``System.IterationPath`` changes while it is still incomplete.

This module builds on :mod:`app.services.iteration_transitions` and exposes
higher-level aggregations used by the `/delivery/carryover/*` endpoints and
the matching AI agent tools.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.contributor import Contributor
from app.db.models.iteration import Iteration
from app.db.models.team import TeamMember
from app.db.models.work_item import WorkItem
from app.db.models.work_item_activity import WorkItemActivity
from app.services.iteration_transitions import (
    ITERATION_PATH_FIELD_NAMES,
    iteration_transitions_query,
)


COMPLETED_STATES_DEFAULT = ("Closed", "Done", "Completed", "Resolved")


def _team_member_subq(team_id: uuid.UUID | None):
    if team_id is None:
        return None
    return select(TeamMember.contributor_id).where(TeamMember.team_id == team_id)


async def get_carryover_summary(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    team_id: uuid.UUID | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> dict:
    """Summary stats for iteration-path moves in a window.

    ``carryover_rate_pct`` = percentage of work items in the project (or
    team scope) that were moved at least once during the window.
    """
    wi = WorkItem.__table__
    base_where = [wi.c.project_id == project_id]
    if team_id is not None:
        base_where.append(wi.c.assigned_to_id.in_(_team_member_subq(team_id)))

    total_wi_q = select(func.count()).select_from(wi).where(*base_where)
    total_wi = (await db.execute(total_wi_q)).scalar() or 0

    transitions = iteration_transitions_query(
        project_id,
        team_id=team_id,
        from_date=from_date,
        to_date=to_date,
    ).subquery("transitions")

    total_moves_q = select(func.count()).select_from(transitions)
    total_moves = (await db.execute(total_moves_q)).scalar() or 0

    unique_items_q = select(func.count(func.distinct(transitions.c.work_item_id))).select_from(transitions)
    unique_items = (await db.execute(unique_items_q)).scalar() or 0

    rate = round((unique_items / total_wi * 100), 1) if total_wi else 0.0
    avg_moves = round((total_moves / unique_items), 2) if unique_items else 0.0

    offender_counts = (
        select(
            transitions.c.work_item_id,
            func.count().label("moves"),
        )
        .group_by(transitions.c.work_item_id)
        .order_by(func.count().desc())
        .limit(10)
        .subquery("offender_counts")
    )
    offender_rows = (
        await db.execute(
            select(
                offender_counts.c.work_item_id,
                offender_counts.c.moves,
                wi.c.platform_work_item_id,
                wi.c.title,
                wi.c.state,
                wi.c.work_item_type,
                wi.c.story_points,
                Contributor.canonical_name.label("assignee"),
            )
            .select_from(
                offender_counts
                .join(wi, offender_counts.c.work_item_id == wi.c.id)
                .outerjoin(Contributor, wi.c.assigned_to_id == Contributor.id)
            )
            .order_by(offender_counts.c.moves.desc())
        )
    ).all()
    top_offenders = [
        {
            "work_item_id": str(r.work_item_id),
            "platform_work_item_id": r.platform_work_item_id,
            "title": r.title,
            "state": r.state,
            "work_item_type": r.work_item_type,
            "story_points": r.story_points,
            "assignee": r.assignee,
            "move_count": r.moves,
        }
        for r in offender_rows
    ]

    return {
        "total_work_items": total_wi,
        "carried_work_items": unique_items,
        "total_moves": total_moves,
        "unique_work_items_moved": unique_items,
        "carryover_rate_pct": rate,
        "avg_moves_per_item": avg_moves,
        "top_offenders": top_offenders,
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
    }


async def get_carryover_by_sprint(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    team_id: uuid.UUID | None = None,
    limit: int = 12,
    completed_states: tuple[str, ...] = COMPLETED_STATES_DEFAULT,
) -> list[dict]:
    """Per-iteration carry-over: items-out (moved to another sprint during this sprint's window) and items-in (arrived from an earlier sprint).

    The result is ordered by iteration start date descending, most recent first.
    """
    wi = WorkItem.__table__
    it = Iteration.__table__

    iter_q = (
        select(
            it.c.id, it.c.name, it.c.path, it.c.start_date, it.c.end_date,
        )
        .where(
            it.c.project_id == project_id,
            it.c.start_date.isnot(None),
            it.c.end_date.isnot(None),
        )
        .order_by(it.c.start_date.desc())
        .limit(limit)
    )
    iterations = (await db.execute(iter_q)).all()
    results: list[dict] = []

    for it_row in iterations:
        it_start = datetime.combine(it_row.start_date, datetime.min.time(), tzinfo=timezone.utc)
        it_end = datetime.combine(it_row.end_date, datetime.max.time(), tzinfo=timezone.utc)

        items_in_q = select(func.count()).select_from(wi).where(
            wi.c.iteration_id == it_row.id,
            wi.c.project_id == project_id,
        )
        if team_id is not None:
            items_in_q = items_in_q.where(wi.c.assigned_to_id.in_(_team_member_subq(team_id)))
        total_items = (await db.execute(items_in_q)).scalar() or 0

        completed_q = select(func.count()).select_from(wi).where(
            wi.c.iteration_id == it_row.id,
            wi.c.project_id == project_id,
            wi.c.state.in_(completed_states),
        )
        if team_id is not None:
            completed_q = completed_q.where(wi.c.assigned_to_id.in_(_team_member_subq(team_id)))
        completed_items = (await db.execute(completed_q)).scalar() or 0

        wia = WorkItemActivity.__table__
        out_q = (
            select(func.count(func.distinct(wia.c.work_item_id)))
            .select_from(wia.join(wi, wia.c.work_item_id == wi.c.id))
            .where(
                wi.c.project_id == project_id,
                wia.c.action == "field_changed",
                wia.c.field_name.in_(ITERATION_PATH_FIELD_NAMES),
                wia.c.old_value == it_row.path,
                wia.c.new_value.is_distinct_from(it_row.path),
                wia.c.activity_at >= it_start,
                wia.c.activity_at <= it_end + timedelta(days=1),
            )
        )
        if team_id is not None:
            out_q = out_q.where(wi.c.assigned_to_id.in_(_team_member_subq(team_id)))
        moved_out = (await db.execute(out_q)).scalar() or 0

        in_q = (
            select(func.count(func.distinct(wia.c.work_item_id)))
            .select_from(wia.join(wi, wia.c.work_item_id == wi.c.id))
            .where(
                wi.c.project_id == project_id,
                wia.c.action == "field_changed",
                wia.c.field_name.in_(ITERATION_PATH_FIELD_NAMES),
                wia.c.new_value == it_row.path,
                wia.c.old_value.is_distinct_from(it_row.path),
                wia.c.activity_at >= it_start - timedelta(days=1),
                wia.c.activity_at <= it_end + timedelta(days=1),
            )
        )
        if team_id is not None:
            in_q = in_q.where(wi.c.assigned_to_id.in_(_team_member_subq(team_id)))
        moved_in = (await db.execute(in_q)).scalar() or 0

        results.append({
            "iteration_id": str(it_row.id),
            "iteration_name": it_row.name,
            "iteration_path": it_row.path,
            "start_date": it_row.start_date.isoformat(),
            "end_date": it_row.end_date.isoformat(),
            "total_items": total_items,
            "completed_items": completed_items,
            "moved_out": moved_out,
            "moved_in": moved_in,
            "carryover_rate_pct": round((moved_out / total_items * 100), 1) if total_items else 0.0,
        })

    return results


async def get_work_item_iteration_history(
    db: AsyncSession,
    project_id: uuid.UUID,
    work_item_id: uuid.UUID,
) -> list[dict]:
    """Timeline of every iteration-path change for a single work item."""
    stmt = iteration_transitions_query(
        project_id,
        work_item_ids=[work_item_id],
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "changed_at": r.changed_at.isoformat(),
            "from_path": r.from_path,
            "to_path": r.to_path,
            "from_iteration": {
                "id": str(r.from_iteration_id) if r.from_iteration_id else None,
                "name": r.from_iteration_name,
            },
            "to_iteration": {
                "id": str(r.to_iteration_id) if r.to_iteration_id else None,
                "name": r.to_iteration_name,
            },
            "revision_number": r.revision_number,
            "contributor_id": str(r.contributor_id) if r.contributor_id else None,
        }
        for r in rows
    ]


async def list_moved_work_items(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    team_id: uuid.UUID | None = None,
    min_moves: int = 1,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """Paginated list of work items with their iteration-move counts."""
    transitions = iteration_transitions_query(
        project_id,
        team_id=team_id,
        from_date=from_date,
        to_date=to_date,
    ).subquery("transitions")

    counts = (
        select(
            transitions.c.work_item_id.label("wi_id"),
            func.count().label("move_count"),
            func.max(transitions.c.changed_at).label("last_moved_at"),
        )
        .group_by(transitions.c.work_item_id)
        .having(func.count() >= min_moves)
        .subquery("counts")
    )

    wi = WorkItem.__table__

    total_q = select(func.count()).select_from(counts)
    total = (await db.execute(total_q)).scalar() or 0

    q = (
        select(
            counts.c.wi_id,
            counts.c.move_count,
            counts.c.last_moved_at,
            wi.c.platform_work_item_id,
            wi.c.title,
            wi.c.state,
            wi.c.work_item_type,
            wi.c.story_points,
            Contributor.canonical_name.label("assignee"),
        )
        .select_from(
            counts
            .join(wi, counts.c.wi_id == wi.c.id)
            .outerjoin(Contributor, wi.c.assigned_to_id == Contributor.id)
        )
        .order_by(counts.c.move_count.desc(), counts.c.last_moved_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(q)).all()

    items = [
        {
            "work_item_id": str(r.wi_id),
            "platform_work_item_id": r.platform_work_item_id,
            "title": r.title,
            "state": r.state,
            "work_item_type": r.work_item_type,
            "story_points": r.story_points,
            "assignee": r.assignee,
            "move_count": r.move_count,
            "last_moved_at": r.last_moved_at.isoformat() if r.last_moved_at else None,
        }
        for r in rows
    ]
    return {"total": total, "items": items, "limit": limit, "offset": offset}
