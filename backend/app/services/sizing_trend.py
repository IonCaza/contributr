"""Story-sizing distribution trend.

Answers "are stories getting sized smaller over time?" by bucketing work items
into story-point ranges (or t-shirt sizes) and aggregating counts per week.

This powers feedback item 8 — size-distribution trend on the POD Backlog tab.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.team import TeamMember
from app.db.models.work_item import WorkItem, WorkItemType

POINT_BUCKETS: list[tuple[str, float | None, float | None]] = [
    ("Unsized", None, None),
    ("1", 0.0, 1.5),
    ("2-3", 1.5, 3.5),
    ("5", 3.5, 6.5),
    ("8", 6.5, 10.5),
    ("13+", 10.5, None),
]


def _bucket_for_points(pts: float | None) -> str:
    if pts is None:
        return "Unsized"
    for name, low, high in POINT_BUCKETS:
        if name == "Unsized":
            continue
        if low is not None and pts < low:
            continue
        if high is not None and pts >= high:
            continue
        return name
    return "Unsized"


def _iso_week_start(d: datetime) -> date:
    """Return Monday of the ISO week containing d."""
    d = d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc)
    return (d - timedelta(days=d.weekday())).date()


async def get_sizing_distribution_trend(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    team_id: uuid.UUID | None = None,
    weeks: int = 12,
    include_unsized: bool = True,
    story_only: bool = True,
    basis: str = "created_at",
) -> dict:
    """Return per-week sizing distribution plus summary stats.

    Args:
        weeks: number of most-recent weeks to include (inclusive of this week).
        basis: which timestamp to bucket by — ``created_at`` (default, when
            the item entered the backlog) or ``activated_at``.
    """
    if basis not in ("created_at", "activated_at"):
        basis = "created_at"
    ts_col = getattr(WorkItem, basis)

    now = datetime.now(timezone.utc)
    window_start_week = _iso_week_start(now) - timedelta(weeks=weeks - 1)

    where = [
        WorkItem.project_id == project_id,
        ts_col.isnot(None),
        ts_col >= datetime.combine(window_start_week, datetime.min.time(), tzinfo=timezone.utc),
    ]
    if story_only:
        where.append(WorkItem.work_item_type == WorkItemType.USER_STORY.value)
    if team_id is not None:
        member_subq = select(TeamMember.contributor_id).where(
            TeamMember.team_id == team_id,
        )
        where.append(WorkItem.assigned_to_id.in_(member_subq))

    rows = (await db.execute(
        select(WorkItem.story_points, ts_col).where(*where)
    )).all()

    week_counts: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    week_points_sum: dict[date, float] = defaultdict(float)
    week_sized_items: dict[date, int] = defaultdict(int)

    for pts, ts in rows:
        if ts is None:
            continue
        wk = _iso_week_start(ts)
        bucket = _bucket_for_points(pts)
        if not include_unsized and bucket == "Unsized":
            continue
        week_counts[wk][bucket] += 1
        if pts is not None:
            week_points_sum[wk] += float(pts)
            week_sized_items[wk] += 1

    bucket_names = [b[0] for b in POINT_BUCKETS if include_unsized or b[0] != "Unsized"]

    series: list[dict] = []
    for i in range(weeks):
        wk_start = _iso_week_start(now) - timedelta(weeks=(weeks - 1 - i))
        bucket_counts = week_counts.get(wk_start, {})
        total = sum(bucket_counts.get(b, 0) for b in bucket_names)
        avg_points = (
            round(week_points_sum[wk_start] / week_sized_items[wk_start], 2)
            if week_sized_items.get(wk_start) else None
        )
        series.append({
            "week_start": wk_start.isoformat(),
            "total": total,
            "avg_points": avg_points,
            "buckets": {b: bucket_counts.get(b, 0) for b in bucket_names},
        })

    totals = {b: sum(s["buckets"][b] for s in series) for b in bucket_names}

    trend_slope = _linear_slope(
        [s["avg_points"] for s in series if s["avg_points"] is not None]
    )

    return {
        "weeks": weeks,
        "basis": basis,
        "series": series,
        "bucket_order": bucket_names,
        "totals": totals,
        "avg_points_trend_slope": trend_slope,
    }


def _linear_slope(values: list[float]) -> float | None:
    """Best-fit slope of y = a + b*x for equally spaced x."""
    n = len(values)
    if n < 2:
        return None
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    num = sum((xs[i] - mean_x) * (values[i] - mean_y) for i in range(n))
    den = sum((xs[i] - mean_x) ** 2 for i in range(n))
    if den == 0:
        return None
    return round(num / den, 4)
