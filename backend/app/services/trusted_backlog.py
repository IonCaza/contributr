"""Trusted-backlog pillar scorecard.

Scores a POD's backlog against the five measurable Scrum "trusted backlog"
pillars (feedback items 3 & 4). Face-to-face PO contact is explicitly out of
scope because it cannot be measured from work-item data.

Pillars:
    1. ``priority_confidence``  — % of in-progress items at top priority tiers
    2. ``work_mix_balance``     — feature/bug/tech-debt composition
    3. ``planning_horizon``     — ready items count relative to ``planning_sprints_target``
    4. ``planned_scope_stability`` — iteration-path move rate in upcoming sprints
    5. ``current_sprint_stability`` — scope-change rate for the active iteration

Each pillar emits a ``traffic_light`` of ``green`` / ``yellow`` / ``red``
based on thresholds in
:class:`app.db.models.project_delivery_settings.ProjectDeliverySettings`.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.iteration import Iteration
from app.db.models.project_delivery_settings import (
    DEFAULT_HEALTH_THRESHOLDS,
    DEFAULT_READY_STATES,
    ProjectDeliverySettings,
)
from app.db.models.team import TeamMember
from app.db.models.work_item import WorkItem, WorkItemType
from app.db.models.work_item_activity import WorkItemActivity


ACTIVE_STATES = ("Active", "Committed", "In Progress", "Doing")
COMPLETED_STATES = ("Closed", "Done", "Completed", "Resolved")

TECH_DEBT_TAGS = frozenset({"tech-debt", "techdebt", "debt", "refactor"})
QUALITY_TYPES = frozenset({WorkItemType.BUG.value})


@dataclass
class PillarResult:
    """One pillar in the trusted-backlog scorecard."""
    key: str
    label: str
    score: float
    traffic_light: str
    details: dict
    measurable: bool = True


def _light(value: float, warn: float, crit: float, higher_is_better: bool = True) -> str:
    if higher_is_better:
        if value >= warn:
            return "green"
        if value >= crit:
            return "yellow"
        return "red"
    if value <= warn:
        return "green"
    if value <= crit:
        return "yellow"
    return "red"


async def _resolve_settings(
    db: AsyncSession, project_id: uuid.UUID,
) -> tuple[dict, list[str]]:
    row = (await db.execute(
        select(
            ProjectDeliverySettings.backlog_health_thresholds,
            ProjectDeliverySettings.ready_states,
        ).where(ProjectDeliverySettings.project_id == project_id)
    )).one_or_none()
    if row is None:
        return dict(DEFAULT_HEALTH_THRESHOLDS), list(DEFAULT_READY_STATES)
    thresholds, ready_states = row
    return dict(thresholds or DEFAULT_HEALTH_THRESHOLDS), list(ready_states or DEFAULT_READY_STATES)


def _team_member_subq(team_id: uuid.UUID):
    return select(TeamMember.contributor_id).where(TeamMember.team_id == team_id)


async def get_trusted_backlog_scorecard(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    team_id: uuid.UUID | None = None,
) -> dict:
    """Compute all five pillars and an overall roll-up."""
    thresholds, ready_states = await _resolve_settings(db, project_id)

    scope_where = [WorkItem.project_id == project_id]
    if team_id is not None:
        scope_where.append(WorkItem.assigned_to_id.in_(_team_member_subq(team_id)))

    pillars = [
        await _pillar_priority_confidence(db, scope_where, thresholds),
        await _pillar_work_mix_balance(db, scope_where, thresholds),
        await _pillar_planning_horizon(db, project_id, scope_where, ready_states, thresholds),
        await _pillar_planned_scope_stability(db, project_id, team_id, thresholds),
        await _pillar_current_sprint_stability(db, project_id, team_id, thresholds),
    ]

    pillars.append(PillarResult(
        key="po_contact",
        label="Product Owner Contact",
        score=0.0,
        traffic_light="unknown",
        details={"note": "Not measurable from work-item data. Track manually."},
        measurable=False,
    ))

    measurable_scores = [p.score for p in pillars if p.measurable]
    overall_score = round(sum(measurable_scores) / len(measurable_scores), 1) if measurable_scores else 0.0

    green = sum(1 for p in pillars if p.measurable and p.traffic_light == "green")
    yellow = sum(1 for p in pillars if p.measurable and p.traffic_light == "yellow")
    red = sum(1 for p in pillars if p.measurable and p.traffic_light == "red")

    if red:
        overall_light = "red"
    elif yellow >= 2:
        overall_light = "yellow"
    elif green >= 3:
        overall_light = "green"
    else:
        overall_light = "yellow"

    return {
        "overall_score": overall_score,
        "overall_traffic_light": overall_light,
        "pillars": [_pillar_dict(p) for p in pillars],
        "thresholds_used": thresholds,
    }


def _pillar_dict(p: PillarResult) -> dict:
    return {
        "key": p.key,
        "label": p.label,
        "score": round(p.score, 1),
        "traffic_light": p.traffic_light,
        "measurable": p.measurable,
        "details": p.details,
    }


async def _pillar_priority_confidence(
    db: AsyncSession, scope_where: list, thresholds: dict,
) -> PillarResult:
    """Highest-priority work is the work being done right now."""
    warn_pct = thresholds.get("priority_top_tier_pct_warn", 50)
    crit_pct = max(warn_pct - 20, 10)

    active_rows = (await db.execute(
        select(WorkItem.priority).where(*scope_where, WorkItem.state.in_(ACTIVE_STATES))
    )).scalars().all()

    if not active_rows:
        return PillarResult(
            key="priority_confidence",
            label="Priority Confidence",
            score=0.0,
            traffic_light="unknown",
            details={"note": "No active items to evaluate."},
        )

    top_count = sum(1 for p in active_rows if p is not None and p <= 2)
    total = len(active_rows)
    top_pct = round(top_count / total * 100, 1)

    light = _light(top_pct, warn_pct, crit_pct, higher_is_better=True)
    score = top_pct

    return PillarResult(
        key="priority_confidence",
        label="Priority Confidence",
        score=score,
        traffic_light=light,
        details={
            "active_items": total,
            "priority_1_or_2_count": top_count,
            "top_tier_pct": top_pct,
            "warn_threshold_pct": warn_pct,
            "unprioritised_count": sum(1 for p in active_rows if p is None),
        },
    )


async def _pillar_work_mix_balance(
    db: AsyncSession, scope_where: list, thresholds: dict,
) -> PillarResult:
    """Balance of features vs quality (bugs) vs tech debt."""
    rows = (await db.execute(
        select(WorkItem.work_item_type, WorkItem.tags).where(
            *scope_where,
            WorkItem.state.notin_(COMPLETED_STATES),
        )
    )).all()

    if not rows:
        return PillarResult(
            key="work_mix_balance",
            label="Work Mix Balance",
            score=0.0,
            traffic_light="unknown",
            details={"note": "No open items."},
        )

    feature_cnt = 0
    quality_cnt = 0
    debt_cnt = 0
    for wit, tags in rows:
        tagset = {t.lower() for t in (tags or [])}
        if tagset & TECH_DEBT_TAGS:
            debt_cnt += 1
        elif wit in QUALITY_TYPES:
            quality_cnt += 1
        else:
            feature_cnt += 1

    total = len(rows)
    feature_pct = round(feature_cnt / total * 100, 1)
    quality_pct = round(quality_cnt / total * 100, 1)
    debt_pct = round(debt_cnt / total * 100, 1)

    if feature_pct > 85 or feature_pct < 40:
        light = "red"
    elif feature_pct > 75 or feature_pct < 55:
        light = "yellow"
    else:
        light = "green"

    score = {"green": 85.0, "yellow": 60.0, "red": 30.0}[light]

    return PillarResult(
        key="work_mix_balance",
        label="Work Mix Balance",
        score=score,
        traffic_light=light,
        details={
            "feature_pct": feature_pct,
            "quality_pct": quality_pct,
            "tech_debt_pct": debt_pct,
            "feature_count": feature_cnt,
            "quality_count": quality_cnt,
            "tech_debt_count": debt_cnt,
            "total_open": total,
            "guideline": "Healthy mix: 55–75% features, remainder split between quality & tech debt.",
        },
    )


async def _pillar_planning_horizon(
    db: AsyncSession,
    project_id: uuid.UUID,
    scope_where: list,
    ready_states: list[str],
    thresholds: dict,
) -> PillarResult:
    """Are there enough ready items to cover the next 1–2 sprints?"""
    target = thresholds.get("planning_sprints_target", 2)
    minimum = thresholds.get("planning_sprints_min", 1)

    now = datetime.now(timezone.utc)
    upcoming_rows = (await db.execute(
        select(
            Iteration.id,
            func.count(WorkItem.id).label("planned"),
            func.coalesce(func.sum(WorkItem.story_points), 0).label("points"),
        )
        .select_from(Iteration)
        .outerjoin(WorkItem, and_(
            WorkItem.iteration_id == Iteration.id,
            *[c for c in scope_where],
        ))
        .where(
            Iteration.project_id == project_id,
            Iteration.start_date >= now.date(),
        )
        .group_by(Iteration.id)
        .order_by(Iteration.start_date.asc())
        .limit(target + 1)
    )).all()

    upcoming_points = sum(float(r.points) for r in upcoming_rows[:target])
    ready_count = (await db.execute(
        select(func.count()).where(
            *scope_where,
            WorkItem.state.in_(ready_states),
            WorkItem.iteration_id.is_(None),
        )
    )).scalar() or 0
    ready_points = (await db.execute(
        select(func.coalesce(func.sum(WorkItem.story_points), 0)).where(
            *scope_where,
            WorkItem.state.in_(ready_states),
            WorkItem.iteration_id.is_(None),
        )
    )).scalar() or 0
    ready_points = float(ready_points)

    velocity = await _rolling_velocity(db, project_id, scope_where)

    if velocity > 0:
        horizon_sprints_backed = (upcoming_points + ready_points) / velocity
    else:
        horizon_sprints_backed = 0.0
    horizon_sprints_backed = round(horizon_sprints_backed, 2)

    if horizon_sprints_backed >= target:
        light = "green"
        score = 90.0
    elif horizon_sprints_backed >= minimum:
        light = "yellow"
        score = 60.0
    else:
        light = "red"
        score = 30.0

    return PillarResult(
        key="planning_horizon",
        label="Planning Horizon",
        score=score,
        traffic_light=light,
        details={
            "target_sprints": target,
            "minimum_sprints": minimum,
            "upcoming_iterations": len(upcoming_rows),
            "upcoming_planned_points": round(upcoming_points, 1),
            "ready_items_unscheduled": ready_count,
            "ready_points_unscheduled": round(ready_points, 1),
            "rolling_velocity": round(velocity, 1),
            "sprints_backed": horizon_sprints_backed,
        },
    )


async def _rolling_velocity(
    db: AsyncSession, project_id: uuid.UUID, scope_where: list,
) -> float:
    """Average points completed per sprint across the last 3 closed iterations."""
    now = datetime.now(timezone.utc)
    closed_iters = (await db.execute(
        select(Iteration.id)
        .where(
            Iteration.project_id == project_id,
            Iteration.end_date.isnot(None),
            Iteration.end_date < now.date(),
        )
        .order_by(Iteration.end_date.desc())
        .limit(3)
    )).scalars().all()
    if not closed_iters:
        return 0.0

    row = (await db.execute(
        select(func.coalesce(func.sum(WorkItem.story_points), 0)).where(
            *scope_where,
            WorkItem.iteration_id.in_(closed_iters),
            WorkItem.state.in_(COMPLETED_STATES),
        )
    )).scalar()
    total = float(row or 0)
    return total / len(closed_iters)


async def _pillar_planned_scope_stability(
    db: AsyncSession,
    project_id: uuid.UUID,
    team_id: uuid.UUID | None,
    thresholds: dict,
) -> PillarResult:
    """How often do items leave a planned iteration before it starts?"""
    now = datetime.now(timezone.utc)
    lookback = now - timedelta(days=30)

    wi_scope = [WorkItem.project_id == project_id]
    if team_id is not None:
        wi_scope.append(WorkItem.assigned_to_id.in_(_team_member_subq(team_id)))

    moves_total = (await db.execute(
        select(func.count())
        .select_from(WorkItemActivity)
        .join(WorkItem, WorkItem.id == WorkItemActivity.work_item_id)
        .where(
            *wi_scope,
            WorkItemActivity.field_name.in_((
                "System.IterationPath", "Microsoft.VSTS.Common.IterationPath",
            )),
            WorkItemActivity.activity_at >= lookback,
            WorkItemActivity.activity_at <= now,
            WorkItemActivity.old_value.isnot(None),
            WorkItemActivity.new_value.isnot(None),
            WorkItemActivity.old_value != WorkItemActivity.new_value,
        )
    )).scalar() or 0

    open_count = (await db.execute(
        select(func.count()).where(*wi_scope, WorkItem.state.notin_(COMPLETED_STATES))
    )).scalar() or 1

    move_rate_pct = round(moves_total / open_count * 100, 1)

    warn = thresholds.get("sprint_scope_change_pct_warn", 10)
    crit = thresholds.get("sprint_scope_change_pct_crit", 25)

    light = _light(move_rate_pct, warn, crit, higher_is_better=False)
    score = max(100 - move_rate_pct, 0.0)

    return PillarResult(
        key="planned_scope_stability",
        label="Planned Scope Stability",
        score=score,
        traffic_light=light,
        details={
            "moves_last_30d": moves_total,
            "open_items": open_count,
            "move_rate_pct": move_rate_pct,
            "warn_threshold_pct": warn,
            "critical_threshold_pct": crit,
        },
    )


async def _pillar_current_sprint_stability(
    db: AsyncSession,
    project_id: uuid.UUID,
    team_id: uuid.UUID | None,
    thresholds: dict,
) -> PillarResult:
    """Scope of the active iteration should stay fixed once the sprint starts."""
    now = datetime.now(timezone.utc).date()
    active_it = (await db.execute(
        select(Iteration).where(
            Iteration.project_id == project_id,
            Iteration.start_date <= now,
            or_(Iteration.end_date.is_(None), Iteration.end_date >= now),
        )
        .order_by(Iteration.start_date.desc())
        .limit(1)
    )).scalar_one_or_none()

    if active_it is None or active_it.start_date is None:
        return PillarResult(
            key="current_sprint_stability",
            label="Current Sprint Stability",
            score=0.0,
            traffic_light="unknown",
            details={"note": "No active iteration."},
        )

    wi_scope = [WorkItem.project_id == project_id, WorkItem.iteration_id == active_it.id]
    if team_id is not None:
        wi_scope.append(WorkItem.assigned_to_id.in_(_team_member_subq(team_id)))

    total = (await db.execute(select(func.count()).where(*wi_scope))).scalar() or 0
    added_after_start = (await db.execute(
        select(func.count()).where(
            *wi_scope,
            func.date(WorkItem.created_at) > active_it.start_date,
        )
    )).scalar() or 0

    original = max(total - added_after_start, 0)
    creep_pct = round(added_after_start / original * 100, 1) if original else 0.0

    warn = thresholds.get("sprint_scope_change_pct_warn", 10)
    crit = thresholds.get("sprint_scope_change_pct_crit", 25)

    light = _light(creep_pct, warn, crit, higher_is_better=False)
    score = max(100 - creep_pct, 0.0)

    return PillarResult(
        key="current_sprint_stability",
        label="Current Sprint Stability",
        score=score,
        traffic_light=light,
        details={
            "iteration_name": active_it.name,
            "iteration_start": active_it.start_date.isoformat() if active_it.start_date else None,
            "original_scope": original,
            "items_added_after_start": added_after_start,
            "current_total": total,
            "creep_pct": creep_pct,
            "warn_threshold_pct": warn,
            "critical_threshold_pct": crit,
        },
    )
