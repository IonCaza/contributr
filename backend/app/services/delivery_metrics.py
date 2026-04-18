"""Delivery analytics metrics computed from work items and iterations."""
from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Date, select, func, case, and_, extract, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.work_item import WorkItem
from app.db.models.iteration import Iteration
from app.db.models.commit import Commit
from app.db.models.contributor import Contributor
from app.db.models.daily_delivery_stats import DailyDeliveryStats
from app.db.models.work_item_commit import WorkItemCommit
from app.db.models.team import TeamMember
from app.db.models.project_delivery_settings import (
    DEFAULT_CYCLE_END_STATES,
    DEFAULT_CYCLE_START_STATES,
    ProjectDeliverySettings,
)


# Lower-cased canonical state names that map to ``WorkItem.closed_at`` vs
# ``WorkItem.resolved_at`` when picking the cycle-time end timestamp.
_CLOSED_TIMESTAMP_ALIASES = frozenset({"closed", "done", "completed"})
_RESOLVED_TIMESTAMP_ALIASES = frozenset({"resolved"})


@dataclass
class CycleTimeConfig:
    """Per-project rule for how cycle time is measured.

    ``start_states`` / ``end_states`` mirror ``ProjectDeliverySettings``.
    The concrete SQL end-timestamp column is picked by :func:`cycle_end_column`
    based on which canonical state names appear in ``end_states``.
    """
    start_states: list[str] = field(default_factory=lambda: list(DEFAULT_CYCLE_START_STATES))
    end_states: list[str] = field(default_factory=lambda: list(DEFAULT_CYCLE_END_STATES))

    @property
    def end_uses_closed(self) -> bool:
        lower = {s.lower() for s in self.end_states}
        return bool(lower & _CLOSED_TIMESTAMP_ALIASES)

    @property
    def end_uses_resolved(self) -> bool:
        lower = {s.lower() for s in self.end_states}
        return bool(lower & _RESOLVED_TIMESTAMP_ALIASES)


DEFAULT_CYCLE_CONFIG = CycleTimeConfig()


def cycle_end_column(wi_table, cycle_config: CycleTimeConfig | None):
    """Return the SQL column/expression that marks cycle-time end.

    If configured end states include a "closed" equivalent we prefer
    ``closed_at`` (coalescing ``resolved_at`` for data synced before
    ``closed_at`` was populated). Otherwise the legacy ``resolved_at``
    behaviour is kept.
    """
    if cycle_config is None or (not cycle_config.end_uses_closed and not cycle_config.end_uses_resolved):
        return wi_table.c.resolved_at
    if cycle_config.end_uses_closed and cycle_config.end_uses_resolved:
        return func.coalesce(wi_table.c.closed_at, wi_table.c.resolved_at)
    if cycle_config.end_uses_closed:
        return func.coalesce(wi_table.c.closed_at, wi_table.c.resolved_at)
    return wi_table.c.resolved_at


def cycle_hours_expr(wi_table, cycle_config: CycleTimeConfig | None):
    """`extract(epoch, end - activated) / 3600` using the configured end column."""
    end_col = cycle_end_column(wi_table, cycle_config)
    return extract("epoch", end_col - wi_table.c.activated_at) / 3600


def cycle_complete_filter(wi_table, cycle_config: CycleTimeConfig | None):
    """SQL predicate that selects items whose cycle has completed."""
    end_col = cycle_end_column(wi_table, cycle_config)
    return end_col.isnot(None)


async def load_cycle_time_config(
    db: AsyncSession, project_id: uuid.UUID,
) -> CycleTimeConfig:
    """Fetch the per-project ``CycleTimeConfig``, falling back to defaults."""
    row = (
        await db.execute(
            select(ProjectDeliverySettings).where(
                ProjectDeliverySettings.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return CycleTimeConfig()
    return CycleTimeConfig(
        start_states=list(row.cycle_time_start_states or DEFAULT_CYCLE_START_STATES),
        end_states=list(row.cycle_time_end_states or DEFAULT_CYCLE_END_STATES),
    )


@dataclass
class DeliveryFilters:
    iteration_ids: list[uuid.UUID] | None = None
    from_date: date | None = None
    to_date: date | None = None
    team_id: uuid.UUID | None = None
    contributor_id: uuid.UUID | None = None
    cycle_config: CycleTimeConfig | None = None


def _apply_filters(filters: DeliveryFilters | None, wi_table, base_filters: list):
    """Append optional filter clauses to *base_filters* in place."""
    if filters is None:
        return base_filters
    if filters.iteration_ids:
        base_filters.append(wi_table.c.iteration_id.in_(filters.iteration_ids))
    if filters.from_date is not None:
        base_filters.append(wi_table.c.created_at >= filters.from_date)
    if filters.to_date is not None:
        base_filters.append(wi_table.c.created_at <= filters.to_date)
    if filters.contributor_id is not None:
        base_filters.append(wi_table.c.assigned_to_id == filters.contributor_id)
    if filters.team_id is not None:
        member_subq = select(TeamMember.contributor_id).where(
            TeamMember.team_id == filters.team_id
        )
        base_filters.append(wi_table.c.assigned_to_id.in_(member_subq))
    return base_filters


async def get_delivery_stats(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    filters: DeliveryFilters | None = None,
) -> dict:
    """Aggregate delivery stats for a project with optional filters."""
    wi = WorkItem.__table__
    base = wi.c.project_id == project_id

    cycle_config = (filters.cycle_config if filters else None) or await load_cycle_time_config(db, project_id)
    cycle_expr = cycle_hours_expr(wi, cycle_config)
    cycle_end_filter = cycle_complete_filter(wi, cycle_config)

    where = _apply_filters(filters, wi, [base])

    total_q = select(func.count()).select_from(wi).where(*where)
    total = (await db.execute(total_q)).scalar() or 0

    open_states = ("New", "Active", "Committed", "In Progress", "Approved")
    open_q = select(func.count()).select_from(wi).where(*where, wi.c.state.in_(open_states))
    open_items = (await db.execute(open_q)).scalar() or 0

    completed_q = select(func.count()).select_from(wi).where(
        *where, wi.c.state.in_(("Resolved", "Closed", "Done", "Completed"))
    )
    completed = (await db.execute(completed_q)).scalar() or 0

    total_sp_q = select(func.coalesce(func.sum(wi.c.story_points), 0)).select_from(wi).where(*where)
    total_sp = (await db.execute(total_sp_q)).scalar() or 0

    completed_sp_q = select(func.coalesce(func.sum(wi.c.story_points), 0)).select_from(wi).where(
        *where, wi.c.resolved_at.isnot(None)
    )
    completed_sp = (await db.execute(completed_sp_q)).scalar() or 0

    cycle_q = select(
        func.percentile_cont(0.5).within_group(cycle_expr).label("median"),
        func.percentile_cont(0.9).within_group(cycle_expr).label("p90"),
    ).select_from(wi).where(
        *where, wi.c.activated_at.isnot(None), cycle_end_filter,
    )
    cycle_row = (await db.execute(cycle_q)).one_or_none()
    avg_cycle = round(cycle_row.median or 0, 1) if cycle_row else 0

    lead_q = select(
        func.percentile_cont(0.5).within_group(
            extract("epoch", wi.c.closed_at - wi.c.created_at) / 3600
        ).label("median"),
    ).select_from(wi).where(*where, wi.c.closed_at.isnot(None))
    lead_row = (await db.execute(lead_q)).one_or_none()
    avg_lead = round(lead_row.median or 0, 1) if lead_row else 0

    type_q = select(
        wi.c.work_item_type, func.count()
    ).select_from(wi).where(*where).group_by(wi.c.work_item_type)
    backlog_by_type = [{"type": r[0], "count": r[1]} for r in (await db.execute(type_q)).all()]

    state_q = select(
        wi.c.state, func.count()
    ).select_from(wi).where(*where).group_by(wi.c.state)
    backlog_by_state = [{"state": r[0], "count": r[1]} for r in (await db.execute(state_q)).all()]

    resolved_filters = filters
    if resolved_filters is None:
        resolved_filters = DeliveryFilters(cycle_config=cycle_config)
    elif resolved_filters.cycle_config is None:
        resolved_filters.cycle_config = cycle_config
    velocity_trend = await get_velocity(db, project_id, filters=resolved_filters, limit=10)
    throughput_trend = await get_throughput_trend(db, project_id, filters=resolved_filters, days=90)
    cycle_time_trend = await get_cycle_time_trend(db, project_id, filters=resolved_filters, weeks=12)
    lead_time_trend = await get_lead_time_trend(db, project_id, filters=resolved_filters, weeks=12)

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
        "cycle_time_trend": cycle_time_trend,
        "lead_time_trend": lead_time_trend,
        "backlog_by_type": backlog_by_type,
        "backlog_by_state": backlog_by_state,
    }


async def get_velocity(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    filters: DeliveryFilters | None = None,
    limit: int = 10,
) -> list[dict]:
    """Story points completed per iteration."""
    wi = WorkItem.__table__
    it = Iteration.__table__

    where = _apply_filters(filters, wi, [
        wi.c.project_id == project_id,
        wi.c.resolved_at.isnot(None),
    ])

    q = (
        select(
            it.c.name.label("iteration"),
            it.c.start_date,
            func.coalesce(func.sum(wi.c.story_points), 0).label("points"),
        )
        .select_from(wi.join(it, wi.c.iteration_id == it.c.id))
        .where(*where)
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
    filters: DeliveryFilters | None = None,
    days: int = 90,
) -> list[dict]:
    """Daily created vs. completed item counts."""
    wi = WorkItem.__table__
    cutoff = date.today() - timedelta(days=days)

    created_where = _apply_filters(filters, wi, [
        wi.c.project_id == project_id,
        func.date(wi.c.created_at) >= cutoff,
    ])
    created_q = (
        select(
            func.date_trunc("day", wi.c.created_at).cast(func.current_date().type).label("d"),
            func.count().label("created"),
        )
        .where(*created_where)
        .group_by("d")
    )
    created_rows = {str(r.d): r.created for r in (await db.execute(created_q)).all()}

    completed_where = _apply_filters(filters, wi, [
        wi.c.project_id == project_id,
        wi.c.resolved_at.isnot(None),
        func.date(wi.c.resolved_at) >= cutoff,
    ])
    completed_q = (
        select(
            func.date_trunc("day", wi.c.resolved_at).cast(func.current_date().type).label("d"),
            func.count().label("completed"),
        )
        .where(*completed_where)
        .group_by("d")
    )
    completed_rows = {str(r.d): r.completed for r in (await db.execute(completed_q)).all()}

    all_dates = sorted(set(list(created_rows.keys()) + list(completed_rows.keys())))
    return [
        {"date": d, "created": created_rows.get(d, 0), "completed": completed_rows.get(d, 0)}
        for d in all_dates
    ]


async def get_cycle_time_trend(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    filters: DeliveryFilters | None = None,
    weeks: int = 12,
) -> list[dict]:
    """Median cycle time per week, for sparkline. End timestamp honours ``ProjectDeliverySettings``."""
    wi = WorkItem.__table__
    cutoff = date.today() - timedelta(weeks=weeks)

    cycle_config = (filters.cycle_config if filters else None) or await load_cycle_time_config(db, project_id)
    cycle_expr = cycle_hours_expr(wi, cycle_config)
    end_col = cycle_end_column(wi, cycle_config)

    where = _apply_filters(filters, wi, [
        wi.c.project_id == project_id,
        wi.c.activated_at.isnot(None),
        end_col.isnot(None),
        func.date(end_col) >= cutoff,
    ])

    week_expr = func.date_trunc("week", end_col).cast(Date)
    q = (
        select(
            week_expr.label("week"),
            func.percentile_cont(0.5).within_group(cycle_expr).label("median_hours"),
        )
        .where(*where)
        .group_by(week_expr)
        .order_by(week_expr)
    )
    rows = (await db.execute(q)).all()
    return [{"week": str(r.week), "median_hours": round(r.median_hours or 0, 1)} for r in rows]


async def get_lead_time_trend(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    filters: DeliveryFilters | None = None,
    weeks: int = 12,
) -> list[dict]:
    """Median lead time (created -> closed) per week, for sparkline."""
    wi = WorkItem.__table__
    cutoff = date.today() - timedelta(weeks=weeks)
    lead_expr = extract("epoch", wi.c.closed_at - wi.c.created_at) / 3600

    where = _apply_filters(filters, wi, [
        wi.c.project_id == project_id,
        wi.c.closed_at.isnot(None),
        func.date(wi.c.closed_at) >= cutoff,
    ])

    week_expr = func.date_trunc("week", wi.c.closed_at).cast(Date)
    q = (
        select(
            week_expr.label("week"),
            func.percentile_cont(0.5).within_group(lead_expr).label("median_hours"),
        )
        .where(*where)
        .group_by(week_expr)
        .order_by(week_expr)
    )
    rows = (await db.execute(q)).all()
    return [{"week": str(r.week), "median_hours": round(r.median_hours or 0, 1)} for r in rows]


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


# ---------------------------------------------------------------------------
# Flow metrics
# ---------------------------------------------------------------------------


async def get_cycle_time_distribution(
    db: AsyncSession, project_id: uuid.UUID, *, filters=None,
) -> list[dict]:
    """Histogram of cycle time in hours, bucketed. End timestamp honours ``ProjectDeliverySettings``."""
    wi = WorkItem.__table__

    cycle_config = (filters.cycle_config if filters else None) or await load_cycle_time_config(db, project_id)
    hours_expr = cycle_hours_expr(wi, cycle_config)
    end_col = cycle_end_column(wi, cycle_config)

    bucket = case(
        (hours_expr < 4, "0-4h"),
        (hours_expr < 8, "4-8h"),
        (hours_expr < 24, "8-24h"),
        (hours_expr < 72, "1-3d"),
        (hours_expr < 168, "3-7d"),
        (hours_expr < 336, "1-2w"),
        (hours_expr < 672, "2-4w"),
        else_="4w+",
    ).label("bucket")

    base = [
        wi.c.project_id == project_id,
        wi.c.activated_at.isnot(None),
        end_col.isnot(None),
    ]
    _apply_filters(filters, wi, base)

    q = (
        select(bucket, func.count().label("count"))
        .select_from(wi)
        .where(*base)
        .group_by(bucket)
    )
    rows = (await db.execute(q)).all()

    order = ["0-4h", "4-8h", "8-24h", "1-3d", "3-7d", "1-2w", "2-4w", "4w+"]
    result_map = {r.bucket: r.count for r in rows}
    return [{"range": b, "count": result_map.get(b, 0)} for b in order]


async def get_wip_by_state(
    db: AsyncSession, project_id: uuid.UUID, *, filters=None,
) -> list[dict]:
    """Count of items in each active (non-closed/resolved) state."""
    wi = WorkItem.__table__
    closed_states = ("Closed", "Done", "Completed", "Resolved")

    base = [
        wi.c.project_id == project_id,
        wi.c.state.notin_(closed_states),
    ]
    _apply_filters(filters, wi, base)

    q = (
        select(wi.c.state, func.count().label("count"))
        .select_from(wi)
        .where(*base)
        .group_by(wi.c.state)
        .order_by(func.count().desc())
    )
    rows = (await db.execute(q)).all()
    return [{"state": r.state, "count": r.count} for r in rows]


async def get_cumulative_flow(
    db: AsyncSession, project_id: uuid.UUID, *, filters=None, days: int = 90,
) -> dict:
    """Daily snapshot of items by state for CFD.

    Returns ``{states: [...], data: [{date, State1: n, ...}]}``.
    Approximation: for each date counts items where ``created_at <= date``
    grouped by current state.
    """
    wi = WorkItem.__table__
    today = date.today()
    cutoff = today - timedelta(days=days)

    base = [wi.c.project_id == project_id]
    _apply_filters(filters, wi, base)

    states_q = select(wi.c.state.distinct()).select_from(wi).where(*base)
    states = sorted(r[0] for r in (await db.execute(states_q)).all())

    items_q = (
        select(wi.c.state, func.date(wi.c.created_at).label("created_date"))
        .select_from(wi)
        .where(*base)
        .order_by(func.date(wi.c.created_at))
    )
    items = (await db.execute(items_q)).all()

    date_counts: dict[date, Counter] = {}
    for item in items:
        d = item.created_date
        if d not in date_counts:
            date_counts[d] = Counter()
        date_counts[d][item.state] += 1

    running: Counter = Counter()
    for d in sorted(date_counts):
        if d < cutoff:
            running += date_counts[d]

    data: list[dict] = []
    current = cutoff
    while current <= today:
        if current in date_counts:
            running += date_counts[current]
        entry: dict = {"date": str(current)}
        for s in states:
            entry[s] = running.get(s, 0)
        data.append(entry)
        current += timedelta(days=1)

    return {"states": states, "data": data}


# ---------------------------------------------------------------------------
# Backlog health
# ---------------------------------------------------------------------------

_COMPLETED_STATES = ("Closed", "Done", "Completed", "Resolved")


async def get_stale_backlog(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    filters=None,
    stale_days: int = 30,
) -> list[dict]:
    """Items not updated in *stale_days*, grouped by type."""
    wi = WorkItem.__table__
    stale_cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)

    base = [
        wi.c.project_id == project_id,
        wi.c.updated_at < stale_cutoff,
        wi.c.state.notin_(_COMPLETED_STATES),
    ]
    _apply_filters(filters, wi, base)

    q = (
        select(wi.c.work_item_type, func.count().label("count"))
        .select_from(wi)
        .where(*base)
        .group_by(wi.c.work_item_type)
        .order_by(func.count().desc())
    )
    rows = (await db.execute(q)).all()
    return [{"type": r.work_item_type, "count": r.count} for r in rows]


async def get_backlog_age_distribution(
    db: AsyncSession, project_id: uuid.UUID, *, filters=None,
) -> list[dict]:
    """Histogram of open item ages in days."""
    wi = WorkItem.__table__
    age_days = extract("epoch", func.now() - wi.c.created_at) / 86400

    bucket = case(
        (age_days < 7, "0-7d"),
        (age_days < 14, "1-2w"),
        (age_days < 28, "2-4w"),
        (age_days < 60, "1-2m"),
        (age_days < 90, "2-3m"),
        (age_days < 180, "3-6m"),
        else_="6m+",
    ).label("bucket")

    base = [
        wi.c.project_id == project_id,
        wi.c.state.notin_(_COMPLETED_STATES),
    ]
    _apply_filters(filters, wi, base)

    q = (
        select(bucket, func.count().label("count"))
        .select_from(wi)
        .where(*base)
        .group_by(bucket)
    )
    rows = (await db.execute(q)).all()

    order = ["0-7d", "1-2w", "2-4w", "1-2m", "2-3m", "3-6m", "6m+"]
    result_map = {r.bucket: r.count for r in rows}
    return [{"range": b, "count": result_map.get(b, 0)} for b in order]


async def get_backlog_growth(
    db: AsyncSession, project_id: uuid.UUID, *, filters=None, days: int = 90,
) -> list[dict]:
    """Daily net change: created minus completed."""
    wi = WorkItem.__table__
    cutoff = date.today() - timedelta(days=days)

    base = [wi.c.project_id == project_id]
    _apply_filters(filters, wi, base)

    created_q = (
        select(
            func.date_trunc("day", wi.c.created_at).cast(func.current_date().type).label("d"),
            func.count().label("created"),
        )
        .select_from(wi)
        .where(*base, func.date(wi.c.created_at) >= cutoff)
        .group_by("d")
    )
    created_rows = {str(r.d): r.created for r in (await db.execute(created_q)).all()}

    completed_q = (
        select(
            func.date_trunc("day", wi.c.resolved_at).cast(func.current_date().type).label("d"),
            func.count().label("completed"),
        )
        .select_from(wi)
        .where(*base, wi.c.resolved_at.isnot(None), func.date(wi.c.resolved_at) >= cutoff)
        .group_by("d")
    )
    completed_rows = {str(r.d): r.completed for r in (await db.execute(completed_q)).all()}

    all_dates = sorted(set(list(created_rows.keys()) + list(completed_rows.keys())))
    return [
        {
            "date": d,
            "created": created_rows.get(d, 0),
            "completed": completed_rows.get(d, 0),
            "net": created_rows.get(d, 0) - completed_rows.get(d, 0),
        }
        for d in all_dates
    ]


# ---------------------------------------------------------------------------
# Quality metrics
# ---------------------------------------------------------------------------


async def get_bug_trend(
    db: AsyncSession, project_id: uuid.UUID, *, filters=None, days: int = 90,
) -> list[dict]:
    """Daily bugs created vs resolved."""
    wi = WorkItem.__table__
    cutoff = date.today() - timedelta(days=days)

    base = [wi.c.project_id == project_id, wi.c.work_item_type == "bug"]
    _apply_filters(filters, wi, base)

    created_q = (
        select(
            func.date_trunc("day", wi.c.created_at).cast(func.current_date().type).label("d"),
            func.count().label("created"),
        )
        .select_from(wi)
        .where(*base, func.date(wi.c.created_at) >= cutoff)
        .group_by("d")
    )
    created_rows = {str(r.d): r.created for r in (await db.execute(created_q)).all()}

    resolved_q = (
        select(
            func.date_trunc("day", wi.c.resolved_at).cast(func.current_date().type).label("d"),
            func.count().label("resolved"),
        )
        .select_from(wi)
        .where(*base, wi.c.resolved_at.isnot(None), func.date(wi.c.resolved_at) >= cutoff)
        .group_by("d")
    )
    resolved_rows = {str(r.d): r.resolved for r in (await db.execute(resolved_q)).all()}

    all_dates = sorted(set(list(created_rows.keys()) + list(resolved_rows.keys())))
    return [
        {
            "date": d,
            "created": created_rows.get(d, 0),
            "resolved": resolved_rows.get(d, 0),
        }
        for d in all_dates
    ]


async def get_bug_resolution_time(
    db: AsyncSession, project_id: uuid.UUID, *, filters=None,
) -> dict:
    """Median and p90 resolution time for bugs in hours. Respects ``ProjectDeliverySettings`` cycle-end mapping."""
    wi = WorkItem.__table__

    cycle_config = (filters.cycle_config if filters else None) or await load_cycle_time_config(db, project_id)
    hours_expr = cycle_hours_expr(wi, cycle_config)
    end_col = cycle_end_column(wi, cycle_config)

    base = [
        wi.c.project_id == project_id,
        wi.c.work_item_type == "bug",
        wi.c.activated_at.isnot(None),
        end_col.isnot(None),
    ]
    _apply_filters(filters, wi, base)

    q = select(
        func.percentile_cont(0.5).within_group(hours_expr).label("median"),
        func.percentile_cont(0.9).within_group(hours_expr).label("p90"),
        func.count().label("sample_size"),
    ).select_from(wi).where(*base)

    row = (await db.execute(q)).one_or_none()
    return {
        "median_hours": round(row.median or 0, 1) if row else 0,
        "p90_hours": round(row.p90 or 0, 1) if row else 0,
        "sample_size": row.sample_size if row else 0,
    }


async def get_defect_density(
    db: AsyncSession, project_id: uuid.UUID, *, filters=None,
) -> dict:
    """Ratio of bugs to total items."""
    wi = WorkItem.__table__

    base = [wi.c.project_id == project_id]
    _apply_filters(filters, wi, base)

    q = select(
        func.count().label("total"),
        func.count().filter(wi.c.work_item_type == "bug").label("bugs"),
    ).select_from(wi).where(*base)

    row = (await db.execute(q)).one()
    total = row.total or 0
    bugs = row.bugs or 0
    return {
        "total_items": total,
        "bug_count": bugs,
        "defect_density_pct": round(bugs / total * 100, 2) if total > 0 else 0.0,
    }


# ---------------------------------------------------------------------------
# Sprint burndown
# ---------------------------------------------------------------------------


async def get_sprint_burndown(
    db: AsyncSession, iteration_id: uuid.UUID,
) -> list[dict]:
    """Daily remaining story points/items for a sprint.

    Returns ``[{date, remaining_points, remaining_items, ideal}]``.
    """
    it = Iteration.__table__
    wi = WorkItem.__table__

    iter_q = select(it.c.start_date, it.c.end_date).where(it.c.id == iteration_id)
    iter_row = (await db.execute(iter_q)).one_or_none()
    if not iter_row or not iter_row.start_date or not iter_row.end_date:
        return []

    start = iter_row.start_date
    end = iter_row.end_date

    total_q = select(
        func.coalesce(func.sum(wi.c.story_points), 0).label("total_points"),
        func.count().label("total_items"),
    ).select_from(wi).where(wi.c.iteration_id == iteration_id)
    totals = (await db.execute(total_q)).one()
    total_points = float(totals.total_points)
    total_items = totals.total_items

    resolved_q = (
        select(
            func.date(wi.c.resolved_at).label("d"),
            func.coalesce(func.sum(wi.c.story_points), 0).label("points"),
            func.count().label("items"),
        )
        .select_from(wi)
        .where(wi.c.iteration_id == iteration_id, wi.c.resolved_at.isnot(None))
        .group_by("d")
    )
    resolved_by_date = {
        str(r.d): {"points": float(r.points), "items": r.items}
        for r in (await db.execute(resolved_q)).all()
    }

    sprint_days = (end - start).days or 1
    result: list[dict] = []
    cumulative_points = 0.0
    cumulative_items = 0
    current = start
    day_idx = 0

    while current <= end:
        day_str = str(current)
        if day_str in resolved_by_date:
            cumulative_points += resolved_by_date[day_str]["points"]
            cumulative_items += resolved_by_date[day_str]["items"]

        ideal = round(total_points - (total_points * day_idx / sprint_days), 1)
        remaining = round(total_points - cumulative_points, 1)

        result.append({
            "date": day_str,
            "remaining": remaining,
            "remaining_items": total_items - cumulative_items,
            "ideal": ideal,
        })
        current += timedelta(days=1)
        day_idx += 1

    return result


# ---------------------------------------------------------------------------
# Intersection (cross-domain) metrics
# ---------------------------------------------------------------------------


async def get_intersection_metrics(
    db: AsyncSession, project_id: uuid.UUID, *, filters=None,
) -> dict:
    """Cross-domain metrics: commits per SP, % items with linked commits, etc."""
    wi = WorkItem.__table__
    wic = WorkItemCommit.__table__
    cm = Commit.__table__

    base = [wi.c.project_id == project_id]
    _apply_filters(filters, wi, base)

    total_items = (
        await db.execute(select(func.count()).select_from(wi).where(*base))
    ).scalar() or 0

    linked_q = (
        select(func.count(func.distinct(wic.c.work_item_id)))
        .select_from(wic.join(wi, wic.c.work_item_id == wi.c.id))
        .where(*base)
    )
    total_linked = (await db.execute(linked_q)).scalar() or 0

    commit_count_q = (
        select(func.count(func.distinct(wic.c.commit_id)))
        .select_from(wic.join(wi, wic.c.work_item_id == wi.c.id))
        .where(*base)
    )
    total_commits = (await db.execute(commit_count_q)).scalar() or 0

    completed_sp = float(
        (
            await db.execute(
                select(func.coalesce(func.sum(wi.c.story_points), 0))
                .select_from(wi)
                .where(*base, wi.c.resolved_at.isnot(None))
            )
        ).scalar()
        or 0
    )

    first_commit_sq = (
        select(
            wic.c.work_item_id,
            func.min(cm.c.authored_at).label("first_commit_at"),
        )
        .select_from(wic.join(cm, wic.c.commit_id == cm.c.id))
        .group_by(wic.c.work_item_id)
        .subquery()
    )

    avg_fc_hours = (
        await db.execute(
            select(
                func.avg(
                    extract("epoch", wi.c.resolved_at - first_commit_sq.c.first_commit_at) / 3600
                ).label("avg_hours")
            )
            .select_from(
                wi.join(first_commit_sq, wi.c.id == first_commit_sq.c.work_item_id)
            )
            .where(*base, wi.c.resolved_at.isnot(None))
        )
    ).scalar()

    return {
        "total_linked_items": total_linked,
        "total_items": total_items,
        "link_coverage_pct": round(total_linked / total_items * 100, 1) if total_items > 0 else 0.0,
        "commits_per_story_point": round(total_commits / completed_sp, 2) if completed_sp > 0 else 0.0,
        "avg_first_commit_to_resolution_hours": round(avg_fc_hours or 0, 1),
    }


# ---------------------------------------------------------------------------
# Drill-down detail data
# ---------------------------------------------------------------------------


async def get_work_item_details(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    filters: DeliveryFilters | None = None,
) -> list[dict]:
    """Per-item detail rows with computed timing and link data for drill-down sheets."""
    wi = WorkItem.__table__
    ct = Contributor.__table__
    wic = WorkItemCommit.__table__
    cm = Commit.__table__
    it = Iteration.__table__

    cycle_config = (filters.cycle_config if filters else None) or await load_cycle_time_config(db, project_id)

    base = [wi.c.project_id == project_id]
    _apply_filters(filters, wi, base)

    link_sq = (
        select(
            wic.c.work_item_id,
            func.count().label("linked_commit_count"),
            func.min(cm.c.authored_at).label("first_commit_at"),
        )
        .select_from(wic.join(cm, wic.c.commit_id == cm.c.id))
        .group_by(wic.c.work_item_id)
        .subquery("link_sq")
    )

    cycle_expr = cycle_hours_expr(wi, cycle_config)
    cycle_end = cycle_end_column(wi, cycle_config)
    lead_expr = extract("epoch", wi.c.closed_at - wi.c.created_at) / 3600
    fc_res_expr = extract("epoch", cycle_end - link_sq.c.first_commit_at) / 3600

    q = (
        select(
            wi.c.id,
            wi.c.platform_work_item_id,
            wi.c.title,
            wi.c.work_item_type,
            wi.c.state,
            wi.c.story_points,
            wi.c.priority,
            wi.c.created_at,
            wi.c.activated_at,
            wi.c.resolved_at,
            wi.c.closed_at,
            wi.c.updated_at,
            wi.c.platform_url,
            ct.c.id.label("assigned_to_id"),
            ct.c.canonical_name.label("assigned_to_name"),
            wi.c.iteration_id.label("iteration_id"),
            it.c.name.label("iteration_name"),
            cycle_expr.label("cycle_time_hours"),
            lead_expr.label("lead_time_hours"),
            func.coalesce(link_sq.c.linked_commit_count, 0).label("linked_commit_count"),
            fc_res_expr.label("first_commit_to_resolution_hours"),
        )
        .select_from(
            wi
            .outerjoin(ct, wi.c.assigned_to_id == ct.c.id)
            .outerjoin(it, wi.c.iteration_id == it.c.id)
            .outerjoin(link_sq, wi.c.id == link_sq.c.work_item_id)
        )
        .where(*base)
        .order_by(wi.c.updated_at.desc())
    )

    rows = (await db.execute(q)).all()
    return [
        {
            "id": str(r.id),
            "platform_work_item_id": r.platform_work_item_id,
            "title": r.title,
            "work_item_type": r.work_item_type.value if hasattr(r.work_item_type, "value") else r.work_item_type,
            "state": r.state,
            "story_points": r.story_points,
            "priority": r.priority,
            "assigned_to_id": str(r.assigned_to_id) if r.assigned_to_id else None,
            "assigned_to_name": r.assigned_to_name,
            "iteration_id": str(r.iteration_id) if r.iteration_id else None,
            "iteration_name": r.iteration_name,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "activated_at": r.activated_at.isoformat() if r.activated_at else None,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            "closed_at": r.closed_at.isoformat() if r.closed_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "platform_url": r.platform_url,
            "cycle_time_hours": round(r.cycle_time_hours, 1) if r.cycle_time_hours is not None else None,
            "lead_time_hours": round(r.lead_time_hours, 1) if r.lead_time_hours is not None else None,
            "linked_commit_count": r.linked_commit_count,
            "first_commit_to_resolution_hours": round(r.first_commit_to_resolution_hours, 1) if r.first_commit_to_resolution_hours is not None else None,
        }
        for r in rows
    ]


async def get_contributor_delivery_summary(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    filters: DeliveryFilters | None = None,
) -> list[dict]:
    """Work item stats aggregated by contributor for drill-down tables."""
    wi = WorkItem.__table__
    ct = Contributor.__table__

    cycle_config = (filters.cycle_config if filters else None) or await load_cycle_time_config(db, project_id)
    cycle_expr = cycle_hours_expr(wi, cycle_config)
    cycle_end = cycle_end_column(wi, cycle_config)

    base = [wi.c.project_id == project_id, wi.c.assigned_to_id.isnot(None)]
    _apply_filters(filters, wi, base)

    open_states = ("New", "Active", "Committed", "In Progress", "Approved")

    q = (
        select(
            wi.c.assigned_to_id.label("contributor_id"),
            ct.c.canonical_name.label("contributor_name"),
            func.count().label("total_items"),
            func.sum(case((wi.c.state.in_(_COMPLETED_STATES), 1), else_=0)).label("completed_items"),
            func.sum(case((wi.c.state.in_(open_states), 1), else_=0)).label("open_items"),
            func.coalesce(func.sum(wi.c.story_points), 0).label("total_sp"),
            func.coalesce(
                func.sum(case((wi.c.resolved_at.isnot(None), wi.c.story_points), else_=literal_column("0"))),
                0,
            ).label("completed_sp"),
            func.avg(
                case((and_(wi.c.activated_at.isnot(None), cycle_end.isnot(None)), cycle_expr), else_=None)
            ).label("avg_cycle_time_hours"),
        )
        .select_from(wi.outerjoin(ct, wi.c.assigned_to_id == ct.c.id))
        .where(*base)
        .group_by(wi.c.assigned_to_id, ct.c.canonical_name)
        .order_by(func.count().desc())
    )

    rows = (await db.execute(q)).all()
    return [
        {
            "contributor_id": str(r.contributor_id),
            "contributor_name": r.contributor_name,
            "total_items": r.total_items,
            "completed_items": r.completed_items,
            "open_items": r.open_items,
            "total_sp": round(float(r.total_sp), 1),
            "completed_sp": round(float(r.completed_sp), 1),
            "avg_cycle_time_hours": round(r.avg_cycle_time_hours, 1) if r.avg_cycle_time_hours else None,
        }
        for r in rows
    ]
