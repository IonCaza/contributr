"""Feature-level backlog rollup.

Aggregates children of each ``feature`` work item by counting leaf stories/tasks,
summing story points, and bucketing them by t-shirt size. T-shirt size is read
from ``custom_fields[tshirt_custom_field]`` (configurable via
:class:`app.db.models.project_delivery_settings.ProjectDeliverySettings`), and
points are summed separately.

This powers the POD-level "feature size" view (feedback item 5).
"""
from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project_delivery_settings import ProjectDeliverySettings
from app.db.models.team import TeamMember
from app.db.models.work_item import WorkItem, WorkItemRelation


COMPLETED_STATES_DEFAULT = ("Closed", "Done", "Completed", "Resolved")
TSHIRT_CANONICAL = ("XS", "S", "M", "L", "XL", "XXL", "3XL")


def _normalize_tshirt(raw) -> str:
    if raw is None:
        return "Unsized"
    s = str(raw).strip().upper()
    if not s:
        return "Unsized"
    aliases = {
        "EXTRA SMALL": "XS",
        "SMALL": "S",
        "MEDIUM": "M",
        "LARGE": "L",
        "EXTRA LARGE": "XL",
        "XX-LARGE": "XXL",
        "XX LARGE": "XXL",
        "XXX-LARGE": "3XL",
    }
    return aliases.get(s, s)


async def _load_tshirt_field(db: AsyncSession, project_id: uuid.UUID) -> str | None:
    row = (await db.execute(
        select(ProjectDeliverySettings.tshirt_custom_field).where(
            ProjectDeliverySettings.project_id == project_id,
        )
    )).scalar_one_or_none()
    return row or None


async def get_feature_rollup(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    team_id: uuid.UUID | None = None,
    completed_states: tuple[str, ...] = COMPLETED_STATES_DEFAULT,
    limit: int = 100,
    include_completed_features: bool = False,
) -> dict:
    """Feature-level backlog rollup.

    Returns one entry per ``feature`` work item in the project (or scoped to
    the given team). Each entry contains aggregated child-item counts, total
    points, completed points, and t-shirt-size distribution.
    """
    tshirt_field = await _load_tshirt_field(db, project_id)

    member_subq = None
    if team_id is not None:
        member_subq = select(TeamMember.contributor_id).where(TeamMember.team_id == team_id)

    feat_where = [
        WorkItem.project_id == project_id,
        WorkItem.work_item_type == "feature",
    ]
    if not include_completed_features:
        feat_where.append(WorkItem.state.notin_(completed_states))
    if team_id is not None:
        feat_where.append(
            (WorkItem.assigned_to_id.in_(member_subq))
            | WorkItem.id.in_(
                select(WorkItemRelation.source_work_item_id).where(
                    WorkItemRelation.relation_type == "parent",
                    WorkItemRelation.target_work_item_id.in_(
                        select(WorkItem.id).where(
                            WorkItem.assigned_to_id.in_(member_subq),
                            WorkItem.project_id == project_id,
                        )
                    ),
                )
            )
        )

    features = (await db.execute(
        select(WorkItem).where(*feat_where).order_by(WorkItem.priority.asc().nullslast(), WorkItem.created_at.desc()).limit(limit)
    )).scalars().all()

    if not features:
        return {"features": [], "totals": _empty_totals(), "tshirt_custom_field": tshirt_field}

    feature_ids = [f.id for f in features]
    child_subq = (
        select(WorkItemRelation.target_work_item_id, WorkItemRelation.source_work_item_id)
        .where(
            WorkItemRelation.source_work_item_id.in_(feature_ids),
            WorkItemRelation.relation_type == "parent",
        )
    )
    child_rows = (await db.execute(child_subq)).all()

    children_by_feature: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for target_id, source_id in child_rows:
        children_by_feature[source_id].append(target_id)

    all_child_ids = [cid for ids in children_by_feature.values() for cid in ids]

    child_map: dict[uuid.UUID, WorkItem] = {}
    if all_child_ids:
        rows = (await db.execute(
            select(WorkItem).where(WorkItem.id.in_(all_child_ids))
        )).scalars().all()
        child_map = {w.id: w for w in rows}

    feature_summaries: list[dict] = []
    totals_tshirt: dict[str, int] = defaultdict(int)
    totals_points = 0.0
    totals_completed = 0.0
    totals_items = 0
    totals_completed_items = 0

    for feat in features:
        child_ids = children_by_feature.get(feat.id, [])
        children = [child_map[cid] for cid in child_ids if cid in child_map]

        total_points = sum((c.story_points or 0) for c in children)
        completed_points = sum(
            (c.story_points or 0) for c in children
            if c.state in completed_states
        )
        total_items = len(children)
        completed_items = sum(1 for c in children if c.state in completed_states)

        tshirt_counts: dict[str, int] = defaultdict(int)
        for c in children:
            raw = None
            if tshirt_field and c.custom_fields:
                raw = c.custom_fields.get(tshirt_field)
            label = _normalize_tshirt(raw)
            tshirt_counts[label] += 1
            totals_tshirt[label] += 1

        feature_summaries.append({
            "feature_id": str(feat.id),
            "platform_work_item_id": feat.platform_work_item_id,
            "title": feat.title,
            "state": feat.state,
            "priority": feat.priority,
            "assigned_to_id": str(feat.assigned_to_id) if feat.assigned_to_id else None,
            "iteration_id": str(feat.iteration_id) if feat.iteration_id else None,
            "total_items": total_items,
            "completed_items": completed_items,
            "total_points": round(total_points, 1),
            "completed_points": round(completed_points, 1),
            "completion_pct": round(completed_points / total_points * 100, 1) if total_points else 0,
            "tshirt_counts": _order_tshirt(tshirt_counts),
        })

        totals_points += total_points
        totals_completed += completed_points
        totals_items += total_items
        totals_completed_items += completed_items

    return {
        "features": feature_summaries,
        "totals": {
            "feature_count": len(features),
            "total_items": totals_items,
            "completed_items": totals_completed_items,
            "total_points": round(totals_points, 1),
            "completed_points": round(totals_completed, 1),
            "tshirt_counts": _order_tshirt(totals_tshirt),
        },
        "tshirt_custom_field": tshirt_field,
    }


def _empty_totals() -> dict:
    return {
        "feature_count": 0,
        "total_items": 0,
        "completed_items": 0,
        "total_points": 0,
        "completed_points": 0,
        "tshirt_counts": _order_tshirt({}),
    }


def _order_tshirt(counts: dict[str, int]) -> list[dict]:
    present = dict(counts)
    ordered: list[dict] = []
    for size in TSHIRT_CANONICAL:
        ordered.append({"size": size, "count": present.pop(size, 0)})
    for size in sorted(present.keys()):
        ordered.append({"size": size, "count": present[size]})
    return ordered
