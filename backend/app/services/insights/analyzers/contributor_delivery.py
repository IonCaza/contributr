"""Contributor Delivery analyzers: throughput, cycle time, estimation, WIP, sprint commitment, bug ratio."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.work_item import WorkItem, WorkItemType
from app.db.models.iteration import Iteration
from app.db.models.daily_delivery_stats import DailyDeliveryStats
from app.services.insights.types import RawFinding

CATEGORY = "delivery"


async def analyze_throughput_trends(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Compare items resolved in current 30d vs prior 30d."""
    now = datetime.now(timezone.utc)
    recent_start = now - timedelta(days=30)
    prior_start = now - timedelta(days=60)

    async def _resolved_count(start: datetime, end: datetime) -> int:
        q = select(func.count()).select_from(WorkItem).where(
            WorkItem.assigned_to_id == contributor_id,
            WorkItem.resolved_at >= start,
            WorkItem.resolved_at < end,
        )
        return (await db.execute(q)).scalar() or 0

    recent = await _resolved_count(recent_start, now)
    prior = await _resolved_count(prior_start, recent_start)

    if prior < 3 and recent < 3:
        return []

    findings: list[RawFinding] = []

    if prior >= 3 and recent < prior * 0.5:
        delta_pct = round(((recent - prior) / prior) * 100, 1) if prior else 0
        findings.append(RawFinding(
            category=CATEGORY,
            severity="warning",
            slug="delivery-throughput-declining",
            title=f"Work item throughput down {abs(delta_pct)}% ({recent} vs {prior} items resolved)",
            description=(
                f"This contributor resolved {recent} items in the last 30 days compared to "
                f"{prior} in the prior period. A significant drop may indicate blockers, "
                f"shifting priorities, or items stuck in review."
            ),
            recommendation=(
                "Check if items are stuck in a particular state (e.g. In Review, Waiting). "
                "Discuss blockers in standup and consider breaking large items into smaller deliverables."
            ),
            metric_data={
                "recent_resolved": recent,
                "prior_resolved": prior,
                "delta_pct": delta_pct,
            },
        ))

    if prior >= 3 and recent > prior * 1.5:
        delta_pct = round(((recent - prior) / prior) * 100, 1)
        findings.append(RawFinding(
            category=CATEGORY,
            severity="info",
            slug="delivery-throughput-growing",
            title=f"Work item throughput up {delta_pct}% ({recent} vs {prior} items resolved)",
            description=(
                f"Great momentum — {recent} items resolved this period vs {prior} last period. "
                f"Sustained throughput growth is a strong signal of execution velocity."
            ),
            recommendation=(
                "Keep the pace sustainable. Ensure quality isn't being sacrificed for speed — "
                "check that resolved items aren't being reopened frequently."
            ),
            metric_data={
                "recent_resolved": recent,
                "prior_resolved": prior,
                "delta_pct": delta_pct,
            },
        ))

    return findings


async def analyze_cycle_time(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Check this contributor's median cycle time vs overall project average."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    contrib_ct_q = select(
        func.percentile_cont(0.5).within_group(
            extract("epoch", WorkItem.resolved_at - WorkItem.activated_at) / 3600
        ),
        func.percentile_cont(0.9).within_group(
            extract("epoch", WorkItem.resolved_at - WorkItem.activated_at) / 3600
        ),
        func.count(),
    ).where(
        WorkItem.assigned_to_id == contributor_id,
        WorkItem.activated_at.isnot(None),
        WorkItem.resolved_at.isnot(None),
        WorkItem.resolved_at >= cutoff,
    )
    row = (await db.execute(contrib_ct_q)).one()
    median_hours = round(float(row[0] or 0), 1)
    p90_hours = round(float(row[1] or 0), 1)
    count = row[2] or 0

    if count < 5:
        return []

    project_ids_q = select(WorkItem.project_id.distinct()).where(
        WorkItem.assigned_to_id == contributor_id,
        WorkItem.resolved_at >= cutoff,
    )
    project_ids = (await db.execute(project_ids_q)).scalars().all()

    if not project_ids:
        return []

    project_avg_q = select(
        func.percentile_cont(0.5).within_group(
            extract("epoch", WorkItem.resolved_at - WorkItem.activated_at) / 3600
        ),
    ).where(
        WorkItem.project_id.in_(project_ids),
        WorkItem.activated_at.isnot(None),
        WorkItem.resolved_at.isnot(None),
        WorkItem.resolved_at >= cutoff,
    )
    project_median = round(float((await db.execute(project_avg_q)).scalar() or 0), 1)

    findings: list[RawFinding] = []

    if project_median > 0 and median_hours > project_median * 1.5 and median_hours > 24:
        ratio = round(median_hours / project_median, 1)
        findings.append(RawFinding(
            category=CATEGORY,
            severity="warning" if ratio > 2 else "info",
            slug="slow-cycle-time",
            title=f"Cycle time {ratio}x the project average ({round(median_hours)}h vs {round(project_median)}h median)",
            description=(
                f"This contributor's median cycle time (activated to resolved) is {round(median_hours)} hours "
                f"compared to the project average of {round(project_median)} hours over {count} items. "
                f"P90 is {round(p90_hours)} hours. Longer cycle times reduce feedback loops."
            ),
            recommendation=(
                "Break work into smaller slices that can move through the pipeline faster. "
                "Identify which state items spend the most time in (active, in review, blocked) "
                "and address the bottleneck."
            ),
            metric_data={
                "contributor_median_hours": median_hours,
                "contributor_p90_hours": p90_hours,
                "project_median_hours": project_median,
                "ratio": ratio,
                "items_analyzed": count,
            },
        ))

    return findings


async def analyze_estimation_accuracy(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Check if estimated vs actual work diverges significantly."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    q = select(
        WorkItem.story_points,
        WorkItem.completed_work,
        WorkItem.original_estimate,
        WorkItem.title,
    ).where(
        WorkItem.assigned_to_id == contributor_id,
        WorkItem.resolved_at >= cutoff,
        WorkItem.original_estimate.isnot(None),
        WorkItem.original_estimate > 0,
        WorkItem.completed_work.isnot(None),
        WorkItem.completed_work > 0,
    )
    rows = (await db.execute(q)).all()

    if len(rows) < 5:
        return []

    ratios = [r.completed_work / r.original_estimate for r in rows]
    avg_ratio = round(sum(ratios) / len(ratios), 2)
    overestimates = sum(1 for r in ratios if r < 0.5)
    underestimates = sum(1 for r in ratios if r > 1.5)

    findings: list[RawFinding] = []

    if avg_ratio > 1.5 or underestimates / len(ratios) > 0.4:
        findings.append(RawFinding(
            category=CATEGORY,
            severity="warning",
            slug="estimation-inaccurate",
            title=f"Work consistently takes longer than estimated (avg {avg_ratio}x original estimate)",
            description=(
                f"Across {len(rows)} completed items, actual work averaged {avg_ratio}x the original estimate. "
                f"{underestimates} items took more than 1.5x the estimate; {overestimates} finished in under half. "
                f"Inaccurate estimates undermine sprint planning and predictability."
            ),
            recommendation=(
                "Use historical actuals to calibrate future estimates. Consider estimation techniques "
                "like planning poker or reference-class forecasting. Track estimation accuracy as a "
                "personal metric to improve over time."
            ),
            metric_data={
                "items_analyzed": len(rows),
                "avg_actual_vs_estimate": avg_ratio,
                "underestimates": underestimates,
                "overestimates": overestimates,
            },
        ))

    return findings


async def analyze_wip_overload(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Count active/in-progress items right now."""
    active_states = ("Active", "In Progress", "Doing", "active", "in progress", "doing")

    q = select(
        func.count(),
        func.coalesce(func.sum(WorkItem.story_points), 0),
    ).where(
        WorkItem.assigned_to_id == contributor_id,
        WorkItem.state.in_(active_states),
        WorkItem.resolved_at.is_(None),
        WorkItem.closed_at.is_(None),
    )
    row = (await db.execute(q)).one()
    wip_count = row[0] or 0
    wip_points = float(row[1] or 0)

    if wip_count <= 3:
        return []

    findings: list[RawFinding] = []
    severity = "critical" if wip_count > 7 else "warning"

    findings.append(RawFinding(
        category=CATEGORY,
        severity=severity,
        slug="wip-overloaded",
        title=f"{wip_count} work items currently in progress ({wip_points} story points)",
        description=(
            f"This contributor has {wip_count} items in an active state simultaneously, "
            f"totalling {wip_points} story points. High WIP leads to context-switching, "
            f"longer cycle times, and more partially-done work."
        ),
        recommendation=(
            "Focus on finishing items before starting new ones. Aim for a WIP limit of 2-3 items. "
            "Move items back to the backlog if they can't be actively worked on."
        ),
        metric_data={
            "wip_count": wip_count,
            "wip_story_points": wip_points,
        },
    ))

    return findings


async def analyze_sprint_commitment(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Check completion rate on sprint-assigned items across recent iterations."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=90)

    recent_iterations_q = (
        select(Iteration.id, Iteration.name, Iteration.end_date)
        .where(
            Iteration.end_date.isnot(None),
            Iteration.end_date <= now.date(),
            Iteration.end_date >= cutoff.date(),
        )
        .order_by(Iteration.end_date.desc())
        .limit(5)
    )
    iterations = (await db.execute(recent_iterations_q)).all()

    if len(iterations) < 2:
        return []

    sprint_data: list[dict] = []
    for it in iterations:
        committed_q = select(func.count()).select_from(WorkItem).where(
            WorkItem.assigned_to_id == contributor_id,
            WorkItem.iteration_id == it.id,
        )
        committed = (await db.execute(committed_q)).scalar() or 0

        completed_q = select(func.count()).select_from(WorkItem).where(
            WorkItem.assigned_to_id == contributor_id,
            WorkItem.iteration_id == it.id,
            WorkItem.resolved_at.isnot(None) | WorkItem.closed_at.isnot(None),
        )
        completed = (await db.execute(completed_q)).scalar() or 0

        if committed > 0:
            sprint_data.append({
                "sprint": it.name,
                "committed": committed,
                "completed": completed,
                "completion_pct": round((completed / committed) * 100, 1),
            })

    if len(sprint_data) < 2:
        return []

    avg_completion = round(sum(s["completion_pct"] for s in sprint_data) / len(sprint_data), 1)

    findings: list[RawFinding] = []

    if avg_completion < 70:
        findings.append(RawFinding(
            category=CATEGORY,
            severity="warning" if avg_completion < 50 else "info",
            slug="low-sprint-completion",
            title=f"Sprint completion rate averaging {avg_completion}% across {len(sprint_data)} sprints",
            description=(
                f"This contributor completes an average of {avg_completion}% of their sprint-committed items. "
                f"Consistently incomplete sprints erode predictability and may indicate over-commitment "
                f"or unexpected blockers."
            ),
            recommendation=(
                "Commit to fewer items per sprint — it's better to finish everything and pull more "
                "than to carry over. Use velocity history to right-size sprint commitments."
            ),
            metric_data={
                "avg_completion_pct": avg_completion,
                "sprints_analyzed": len(sprint_data),
                "sprint_breakdown": sprint_data,
            },
        ))

    return findings


async def analyze_bug_ratio(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Check the ratio of bug-type items resolved by this contributor."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    total_q = select(func.count()).select_from(WorkItem).where(
        WorkItem.assigned_to_id == contributor_id,
        WorkItem.resolved_at >= cutoff,
    )
    total = (await db.execute(total_q)).scalar() or 0

    if total < 5:
        return []

    bug_q = select(func.count()).select_from(WorkItem).where(
        WorkItem.assigned_to_id == contributor_id,
        WorkItem.resolved_at >= cutoff,
        WorkItem.work_item_type == WorkItemType.BUG,
    )
    bugs = (await db.execute(bug_q)).scalar() or 0
    bug_pct = round((bugs / total) * 100, 1) if total else 0

    findings: list[RawFinding] = []

    if bug_pct > 50:
        findings.append(RawFinding(
            category=CATEGORY,
            severity="warning",
            slug="high-bug-ratio",
            title=f"{bug_pct}% of resolved items are bugs ({bugs} of {total})",
            description=(
                f"More than half of this contributor's resolved work items are bugs. "
                f"This could indicate assignment to stabilization work, or that features "
                f"they build tend to generate follow-up defects."
            ),
            recommendation=(
                "If this is intentional (stabilization sprint, bug bash), it's fine. Otherwise, "
                "investigate whether bugs originate from this contributor's prior work. "
                "Consider investing in test automation to prevent regressions."
            ),
            metric_data={
                "total_resolved": total,
                "bugs_resolved": bugs,
                "bug_pct": bug_pct,
            },
        ))

    return findings
