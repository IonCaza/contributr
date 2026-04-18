"""Long-running stories detection + "why is this stuck?" analysis.

A work item is "long-running" when the number of calendar days between
``activated_at`` and now exceeds the project's configured threshold
(default 14, see ``ProjectDeliverySettings.long_running_threshold_days``).

Each long-running item is annotated with signals that explain *why* it might
be dragging:

* ``stalled``            — days since last activity above staleness threshold
* ``no_updates``         — never had any revisions logged
* ``iteration_hopping``  — changed iteration path more than once
* ``reassigned_often``   — changed assignee more than once since activation
* ``oversized``          — story points above a heuristic upper bound (13)
* ``state_loop``         — bounced between states (e.g. Active→Review→Active)
* ``unestimated``        — active but has no story points
* ``unassigned``         — active but no one is assigned

This powers feedback item 6. The AI "why" enhancement is layered on top by
surfacing this structured data to the delivery-analyst agent, which can then
describe the signals in natural language.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.contributor import Contributor
from app.db.models.iteration import Iteration
from app.db.models.project_delivery_settings import ProjectDeliverySettings
from app.db.models.team import TeamMember
from app.db.models.work_item import WorkItem, WorkItemType
from app.db.models.work_item_activity import WorkItemActivity


ACTIVE_STATES = ("Active", "Committed", "In Progress", "Doing", "In Review", "Code Review", "Testing", "QA")
COMPLETED_STATES = ("Closed", "Done", "Completed", "Resolved")

STALE_DAYS_DEFAULT = 5
OVERSIZED_POINTS = 13.0


async def _resolve_threshold(db: AsyncSession, project_id: uuid.UUID) -> int:
    row = (await db.execute(
        select(ProjectDeliverySettings.long_running_threshold_days).where(
            ProjectDeliverySettings.project_id == project_id,
        )
    )).scalar_one_or_none()
    if row is None or row <= 0:
        return 14
    return int(row)


async def get_long_running_stories(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    team_id: uuid.UUID | None = None,
    min_days_active: int | None = None,
    limit: int = 50,
    include_bugs: bool = True,
) -> dict:
    """Return active items running longer than the threshold, with "why" signals."""
    threshold_days = min_days_active or await _resolve_threshold(db, project_id)

    now = datetime.now(timezone.utc)
    activated_cutoff = now - timedelta(days=threshold_days)

    where = [
        WorkItem.project_id == project_id,
        WorkItem.activated_at.isnot(None),
        WorkItem.activated_at <= activated_cutoff,
        WorkItem.state.in_(ACTIVE_STATES),
    ]
    if team_id is not None:
        member_subq = select(TeamMember.contributor_id).where(
            TeamMember.team_id == team_id,
        )
        where.append(WorkItem.assigned_to_id.in_(member_subq))
    if not include_bugs:
        where.append(WorkItem.work_item_type != WorkItemType.BUG.value)

    rows = (await db.execute(
        select(WorkItem)
        .where(*where)
        .order_by(WorkItem.activated_at.asc())
        .limit(limit)
    )).scalars().all()

    if not rows:
        return {
            "threshold_days": threshold_days,
            "count": 0,
            "items": [],
            "summary_signals": {},
        }

    wi_ids = [r.id for r in rows]
    activity_counts = (await db.execute(
        select(
            WorkItemActivity.work_item_id,
            WorkItemActivity.field_name,
            func.count(WorkItemActivity.id),
        )
        .where(
            WorkItemActivity.work_item_id.in_(wi_ids),
            WorkItemActivity.field_name.in_((
                "System.IterationPath", "System.AssignedTo", "System.State",
            )),
        )
        .group_by(WorkItemActivity.work_item_id, WorkItemActivity.field_name)
    )).all()

    # Historical data contains rows with ``activity_at = 9999-01-01`` (the
    # Azure DevOps sentinel for "latest revision"). Exclude anything in the
    # future so ``MAX(activity_at)`` represents a real last-activity timestamp.
    last_activity = dict((await db.execute(
        select(
            WorkItemActivity.work_item_id,
            func.max(WorkItemActivity.activity_at),
        )
        .where(
            WorkItemActivity.work_item_id.in_(wi_ids),
            WorkItemActivity.activity_at <= now,
        )
        .group_by(WorkItemActivity.work_item_id)
    )).all())

    counts_by_item: dict[uuid.UUID, dict[str, int]] = {}
    for wi_id, field, cnt in activity_counts:
        counts_by_item.setdefault(wi_id, {})[field] = int(cnt)

    assignee_map: dict[uuid.UUID, str] = {}
    assignee_ids = [r.assigned_to_id for r in rows if r.assigned_to_id]
    if assignee_ids:
        contributor_rows = (await db.execute(
            select(Contributor.id, Contributor.canonical_name).where(
                Contributor.id.in_(assignee_ids),
            )
        )).all()
        assignee_map = {cid: name for cid, name in contributor_rows}

    iteration_ids = [r.iteration_id for r in rows if r.iteration_id]
    iteration_map: dict[uuid.UUID, str] = {}
    if iteration_ids:
        iter_rows = (await db.execute(
            select(Iteration.id, Iteration.name).where(Iteration.id.in_(iteration_ids))
        )).all()
        iteration_map = {iid: name for iid, name in iter_rows}

    items: list[dict] = []
    summary_signals: dict[str, int] = {}

    for wi in rows:
        days_active = max((now - wi.activated_at).days, 0) if wi.activated_at else 0
        last_at = last_activity.get(wi.id)
        days_since_update = (
            max((now - last_at).days, 0) if last_at else days_active
        )
        counts = counts_by_item.get(wi.id, {})

        signals: list[str] = []
        if days_since_update > STALE_DAYS_DEFAULT:
            signals.append("stalled")
        if not counts:
            signals.append("no_updates")
        if counts.get("System.IterationPath", 0) > 1:
            signals.append("iteration_hopping")
        if counts.get("System.AssignedTo", 0) > 1:
            signals.append("reassigned_often")
        if counts.get("System.State", 0) >= 3:
            signals.append("state_loop")
        if wi.story_points and wi.story_points >= OVERSIZED_POINTS:
            signals.append("oversized")
        if wi.story_points is None:
            signals.append("unestimated")
        if wi.assigned_to_id is None:
            signals.append("unassigned")

        for s in signals:
            summary_signals[s] = summary_signals.get(s, 0) + 1

        items.append({
            "work_item_id": str(wi.id),
            "platform_work_item_id": wi.platform_work_item_id,
            "title": wi.title,
            "state": wi.state,
            "priority": wi.priority,
            "assigned_to_id": str(wi.assigned_to_id) if wi.assigned_to_id else None,
            "assigned_to_name": assignee_map.get(wi.assigned_to_id),
            "iteration_id": str(wi.iteration_id) if wi.iteration_id else None,
            "iteration_name": iteration_map.get(wi.iteration_id),
            "story_points": wi.story_points,
            "activated_at": wi.activated_at.isoformat() if wi.activated_at else None,
            "last_activity_at": last_at.isoformat() if last_at else None,
            "days_active": days_active,
            "days_since_update": days_since_update,
            "iteration_moves": counts.get("System.IterationPath", 0),
            "state_changes": counts.get("System.State", 0),
            "assignee_changes": counts.get("System.AssignedTo", 0),
            "signals": signals,
            "summary": _summarize(signals, days_active, days_since_update),
        })

    items.sort(key=lambda x: (-x["days_active"], -len(x["signals"])))
    return {
        "threshold_days": threshold_days,
        "count": len(items),
        "items": items,
        "summary_signals": summary_signals,
    }


def _summarize(signals: list[str], days_active: int, days_since_update: int) -> str:
    """Short, human-readable one-liner describing probable cause."""
    if not signals:
        return f"Running {days_active}d with no obvious blocker — may just be large scope."
    if "iteration_hopping" in signals and "stalled" in signals:
        return f"Moved between sprints and has had no activity for {days_since_update}d — likely abandoned or blocked."
    if "iteration_hopping" in signals:
        return f"Bounced between sprints — likely consistently deprioritised."
    if "state_loop" in signals:
        return f"State has flipped back and forth — review/testing likely failing repeatedly."
    if "reassigned_often" in signals:
        return f"Reassigned multiple times — owner churn may be the root cause."
    if "oversized" in signals:
        return f"Large story ({days_active}d active) — probably needs to be split."
    if "stalled" in signals and "unassigned" in signals:
        return f"Unassigned and stalled for {days_since_update}d."
    if "stalled" in signals:
        return f"No updates for {days_since_update}d — check with assignee."
    if "unestimated" in signals:
        return f"Active but unestimated — scope unclear."
    if "no_updates" in signals:
        return f"Activated {days_active}d ago but no revisions recorded."
    return ", ".join(signals)
