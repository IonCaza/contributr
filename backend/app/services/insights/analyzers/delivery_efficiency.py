"""Delivery Efficiency analyzers: cycle time, sprint predictability, scope creep, WIP limits."""
from __future__ import annotations

import uuid
from datetime import datetime, date, timedelta, timezone

from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.work_item import WorkItem
from app.db.models.iteration import Iteration
from app.db.models.contributor import Contributor
from app.services.insights.types import RawFinding

CATEGORY = "delivery"


async def analyze_cycle_time_trends(
    db: AsyncSession, project_id: uuid.UUID,
) -> list[RawFinding]:
    now = datetime.now(timezone.utc)

    async def _median_cycle(start: datetime, end: datetime) -> float | None:
        q = select(
            func.percentile_cont(0.5).within_group(
                extract("epoch", WorkItem.resolved_at - WorkItem.activated_at) / 3600
            )
        ).where(
            WorkItem.project_id == project_id,
            WorkItem.activated_at.isnot(None),
            WorkItem.resolved_at.isnot(None),
            WorkItem.resolved_at >= start,
            WorkItem.resolved_at < end,
        )
        val = (await db.execute(q)).scalar()
        return round(val, 1) if val else None

    current = await _median_cycle(now - timedelta(days=30), now)
    previous = await _median_cycle(now - timedelta(days=60), now - timedelta(days=30))
    three_ago = await _median_cycle(now - timedelta(days=90), now - timedelta(days=60))

    if current is None or previous is None:
        return []

    delta_pct = round(((current - previous) / previous) * 100, 1) if previous > 0 else 0

    if delta_pct <= 20:
        return []

    by_type_q = (
        select(
            WorkItem.work_item_type,
            func.percentile_cont(0.5).within_group(
                extract("epoch", WorkItem.resolved_at - WorkItem.activated_at) / 3600
            ),
        )
        .where(
            WorkItem.project_id == project_id,
            WorkItem.activated_at.isnot(None),
            WorkItem.resolved_at.isnot(None),
            WorkItem.resolved_at >= now - timedelta(days=30),
        )
        .group_by(WorkItem.work_item_type)
    )
    by_type_rows = (await db.execute(by_type_q)).all()
    by_type = {
        (row[0].value if hasattr(row[0], "value") else str(row[0])): round(row[1], 1)
        for row in by_type_rows if row[1]
    }

    severity = "critical" if delta_pct > 50 else "warning"
    three_ago_str = str(three_ago) + "h" if three_ago else "N/A"
    return [RawFinding(
        category=CATEGORY,
        severity=severity,
        slug="cycle-time-trending-up",
        title="Cycle time increased {}% month-over-month".format(delta_pct),
        description=(
            "Median work item cycle time rose from {}h to {}h this month (+{}%). "
            "Three months ago it was {}.".format(previous, current, delta_pct, three_ago_str)
        ),
        recommendation="Investigate bottlenecks in the workflow. Break large items into smaller ones and reduce WIP.",
        metric_data={
            "current_month_hours": current,
            "previous_month_hours": previous,
            "three_months_ago_hours": three_ago,
            "delta_pct": delta_pct,
            "by_type": by_type,
        },
    )]


async def analyze_sprint_predictability(
    db: AsyncSession, project_id: uuid.UUID,
) -> list[RawFinding]:
    today = date.today()
    iterations_q = (
        select(Iteration)
        .where(
            Iteration.project_id == project_id,
            Iteration.end_date.isnot(None),
            Iteration.end_date < today,
        )
        .order_by(Iteration.end_date.desc())
        .limit(5)
    )
    iterations = (await db.execute(iterations_q)).scalars().all()

    if len(iterations) < 3:
        return []

    sprint_data: list[dict] = []
    for it in iterations:
        planned_q = select(func.coalesce(func.sum(WorkItem.story_points), 0.0)).where(
            WorkItem.iteration_id == it.id,
        )
        planned = (await db.execute(planned_q)).scalar() or 0

        completed_q = select(func.coalesce(func.sum(WorkItem.story_points), 0.0)).where(
            WorkItem.iteration_id == it.id,
            WorkItem.resolved_at.isnot(None),
        )
        completed = (await db.execute(completed_q)).scalar() or 0

        rate = round((completed / planned) * 100, 1) if planned > 0 else None
        sprint_data.append({
            "name": it.name,
            "planned": float(planned),
            "completed": float(completed),
            "rate": rate,
        })

    valid_rates = [s["rate"] for s in sprint_data if s["rate"] is not None]
    if not valid_rates:
        return []

    avg_rate = round(sum(valid_rates) / len(valid_rates), 1)
    variance = round(
        sum((r - avg_rate) ** 2 for r in valid_rates) / len(valid_rates), 1
    )

    findings: list[RawFinding] = []

    if avg_rate < 70:
        severity = "critical" if avg_rate < 50 else "warning"
        findings.append(RawFinding(
            category=CATEGORY,
            severity=severity,
            slug="sprint-low-completion",
            title="Sprint completion rate averages {}%".format(avg_rate),
            description=(
                "Over the last {} sprints, the average completion rate is {}%. "
                "This suggests the team is consistently overcommitting.".format(
                    len(valid_rates), avg_rate
                )
            ),
            recommendation="Right-size sprint commitments based on historical velocity. Use the previous sprint's completed points as a guide.",
            metric_data={
                "sprints": sprint_data,
                "avg_rate": avg_rate,
                "variance": variance,
            },
        ))

    if variance > 400 and avg_rate >= 50:
        findings.append(RawFinding(
            category=CATEGORY,
            severity="warning",
            slug="sprint-unpredictable",
            title="Sprint completion is highly unpredictable",
            description=(
                "Completion rate variance is {} across recent sprints (avg {}%). "
                "High variance makes capacity planning unreliable.".format(variance, avg_rate)
            ),
            recommendation="Investigate what causes inconsistency between sprints — scope changes, blockers, or estimation issues.",
            metric_data={
                "sprints": sprint_data,
                "avg_rate": avg_rate,
                "variance": variance,
            },
        ))

    return findings


async def analyze_sprint_scope_creep(
    db: AsyncSession, project_id: uuid.UUID,
) -> list[RawFinding]:
    today = date.today()
    iterations_q = (
        select(Iteration)
        .where(
            Iteration.project_id == project_id,
            Iteration.start_date.isnot(None),
            Iteration.end_date.isnot(None),
            Iteration.end_date < today,
        )
        .order_by(Iteration.end_date.desc())
        .limit(5)
    )
    iterations = (await db.execute(iterations_q)).scalars().all()

    if not iterations:
        return []

    total_items = 0
    added_mid_sprint = 0

    for it in iterations:
        items_q = select(WorkItem).where(WorkItem.iteration_id == it.id)
        items = (await db.execute(items_q)).scalars().all()
        total_items += len(items)

        for wi in items:
            entry_date = wi.activated_at or wi.created_at
            if entry_date and it.start_date and entry_date.date() > it.start_date:
                added_mid_sprint += 1

    if total_items == 0:
        return []

    pct = round((added_mid_sprint / total_items) * 100, 1)
    if pct <= 20:
        return []

    severity = "critical" if pct > 40 else "warning"
    return [RawFinding(
        category=CATEGORY,
        severity=severity,
        slug="sprint-scope-creep",
        title="{}% of sprint items were added mid-sprint".format(pct),
        description=(
            "Across the last {} completed sprints, {} of {} items appeared "
            "to enter the sprint after its start date.".format(
                len(iterations), added_mid_sprint, total_items
            )
        ),
        recommendation="Protect sprint scope after planning. New urgent items should trigger explicit trade-off discussions.",
        metric_data={
            "total_items": total_items,
            "added_mid_sprint": added_mid_sprint,
            "pct": pct,
            "sprints_analyzed": len(iterations),
        },
    )]


async def analyze_wip_limits(
    db: AsyncSession, project_id: uuid.UUID,
) -> list[RawFinding]:
    active_states = ("Active", "In Progress", "Committed")

    wip_q = (
        select(
            WorkItem.assigned_to_id,
            func.count().label("wip"),
        )
        .where(
            WorkItem.project_id == project_id,
            WorkItem.state.in_(active_states),
            WorkItem.assigned_to_id.isnot(None),
        )
        .group_by(WorkItem.assigned_to_id)
        .having(func.count() > 5)
    )
    rows = (await db.execute(wip_q)).all()

    if not rows:
        return []

    contributor_ids = [r[0] for r in rows]
    names_q = select(Contributor.id, Contributor.canonical_name).where(
        Contributor.id.in_(contributor_ids)
    )
    name_map = {r[0]: r[1] for r in (await db.execute(names_q)).all()}

    overloaded = [
        {"name": name_map.get(r[0], "Unknown"), "wip_count": r[1]}
        for r in rows
    ]

    severity = "critical" if any(o["wip_count"] > 10 for o in overloaded) else "warning"
    top_str = ", ".join(
        "{} ({})".format(o["name"], o["wip_count"]) for o in overloaded[:5]
    )
    return [RawFinding(
        category=CATEGORY,
        severity=severity,
        slug="wip-overloaded",
        title="{} contributors have more than 5 items in progress".format(len(overloaded)),
        description=(
            "High WIP counts lead to context switching and reduced throughput. "
            "Top offenders: {}.".format(top_str)
        ),
        recommendation="Set explicit WIP limits per person (3-5 items max). Finish items before starting new ones.",
        metric_data={"overloaded_contributors": overloaded},
        affected_entities={"contributors": [str(r[0]) for r in rows]},
    )]
