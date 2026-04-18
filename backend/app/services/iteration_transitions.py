"""Iteration-path transition helpers.

A "transition" is a row in ``work_item_activities`` where the
``System.IterationPath`` field changes value, representing a work item moving
from one iteration to another. This is the core primitive powering sprint
carry-over analytics.

Data source: ``azure_workitems_client.py`` already records ``System.IterationPath``
changes as ``action='field_changed'`` rows; this module only reads them.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.iteration import Iteration
from app.db.models.team import TeamMember
from app.db.models.work_item import WorkItem
from app.db.models.work_item_activity import WorkItemActivity


ITERATION_PATH_FIELD_NAMES = (
    "System.IterationPath",
    "Microsoft.VSTS.Common.IterationPath",
)


@dataclass
class IterationTransitionRow:
    """Minimal row shape returned by :func:`iteration_transitions_query`."""
    work_item_id: uuid.UUID
    from_path: str | None
    to_path: str | None
    changed_at: datetime
    from_iteration_id: uuid.UUID | None
    from_iteration_name: str | None
    to_iteration_id: uuid.UUID | None
    to_iteration_name: str | None


def iteration_transitions_query(
    project_id: uuid.UUID,
    *,
    team_id: uuid.UUID | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    work_item_ids: list[uuid.UUID] | None = None,
) -> Select:
    """Return a SQL select that yields iteration-path transitions.

    Each row represents a single change to ``System.IterationPath`` on a work
    item, enriched with the resolved ``Iteration`` rows on each side of the
    transition. ``old_value`` / ``new_value`` are left-joined to
    ``iterations.path`` (scoped to the same project).

    The returned ``Select`` can be further filtered or used as a sub-query
    / CTE in downstream analytics.
    """
    wia = WorkItemActivity.__table__
    wi = WorkItem.__table__
    it_from = Iteration.__table__.alias("it_from")
    it_to = Iteration.__table__.alias("it_to")

    where = [
        wi.c.project_id == project_id,
        wia.c.action == "field_changed",
        wia.c.field_name.in_(ITERATION_PATH_FIELD_NAMES),
        or_(wia.c.old_value.isnot(None), wia.c.new_value.isnot(None)),
        wia.c.old_value.is_distinct_from(wia.c.new_value),
    ]
    if team_id is not None:
        member_subq = select(TeamMember.contributor_id).where(
            TeamMember.team_id == team_id
        )
        where.append(wi.c.assigned_to_id.in_(member_subq))
    if from_date is not None:
        where.append(wia.c.activity_at >= from_date)
    if to_date is not None:
        where.append(wia.c.activity_at <= to_date)
    if work_item_ids:
        where.append(wia.c.work_item_id.in_(work_item_ids))

    stmt = (
        select(
            wia.c.work_item_id.label("work_item_id"),
            wia.c.old_value.label("from_path"),
            wia.c.new_value.label("to_path"),
            wia.c.activity_at.label("changed_at"),
            it_from.c.id.label("from_iteration_id"),
            it_from.c.name.label("from_iteration_name"),
            it_to.c.id.label("to_iteration_id"),
            it_to.c.name.label("to_iteration_name"),
            wia.c.revision_number.label("revision_number"),
            wia.c.contributor_id.label("contributor_id"),
        )
        .select_from(
            wia.join(wi, wia.c.work_item_id == wi.c.id)
            .outerjoin(
                it_from,
                and_(
                    it_from.c.project_id == project_id,
                    it_from.c.path == wia.c.old_value,
                ),
            )
            .outerjoin(
                it_to,
                and_(
                    it_to.c.project_id == project_id,
                    it_to.c.path == wia.c.new_value,
                ),
            )
        )
        .where(*where)
        .order_by(wia.c.work_item_id, wia.c.revision_number)
    )
    return stmt


async def list_iteration_transitions(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    team_id: uuid.UUID | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    work_item_ids: list[uuid.UUID] | None = None,
) -> list[IterationTransitionRow]:
    """Materialize :func:`iteration_transitions_query` into a list of rows."""
    stmt = iteration_transitions_query(
        project_id,
        team_id=team_id,
        from_date=from_date,
        to_date=to_date,
        work_item_ids=work_item_ids,
    )
    rows = (await db.execute(stmt)).all()
    return [
        IterationTransitionRow(
            work_item_id=r.work_item_id,
            from_path=r.from_path,
            to_path=r.to_path,
            changed_at=r.changed_at,
            from_iteration_id=r.from_iteration_id,
            from_iteration_name=r.from_iteration_name,
            to_iteration_id=r.to_iteration_id,
            to_iteration_name=r.to_iteration_name,
        )
        for r in rows
    ]


async def work_item_moved_count(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    team_id: uuid.UUID | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> dict[uuid.UUID, int]:
    """Map of ``work_item_id -> number of iteration moves`` in the window.

    A "move" is any ``System.IterationPath`` change where the old and new
    values differ.
    """
    base = iteration_transitions_query(
        project_id,
        team_id=team_id,
        from_date=from_date,
        to_date=to_date,
    ).subquery("transitions")

    q = (
        select(base.c.work_item_id, func.count().label("moves"))
        .group_by(base.c.work_item_id)
    )
    rows = (await db.execute(q)).all()
    return {r.work_item_id: r.moves for r in rows}


async def project_has_iteration_transitions(
    db: AsyncSession, project_id: uuid.UUID,
) -> bool:
    """Return True if any iteration-path change has been recorded.

    Used by the backfill task to decide whether this project needs a
    ``get_updates`` re-pull from Azure DevOps.
    """
    wia = WorkItemActivity.__table__
    wi = WorkItem.__table__
    q = (
        select(func.count())
        .select_from(wia.join(wi, wia.c.work_item_id == wi.c.id))
        .where(
            wi.c.project_id == project_id,
            wia.c.action == "field_changed",
            wia.c.field_name.in_(ITERATION_PATH_FIELD_NAMES),
        )
    )
    count = (await db.execute(q)).scalar() or 0
    return count > 0
