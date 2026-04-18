from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from langchain_core.tools import tool
from sqlalchemy import select, func, and_, case, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Project, Contributor, WorkItem, WorkItemRelation, Iteration,
    Team, TeamMember, Commit,
)
from app.db.models.work_item_commit import WorkItemCommit
from app.services.delivery_metrics import (
    DeliveryFilters,
    cycle_end_column,
    cycle_hours_expr,
    get_velocity,
    get_throughput_trend,
    get_iteration_detail as _iteration_detail,
    get_sprint_burndown as _burndown,
    get_cycle_time_distribution,
    get_wip_by_state,
    get_cumulative_flow as _cumulative_flow,
    get_stale_backlog,
    get_backlog_age_distribution,
    get_backlog_growth,
    get_bug_trend,
    get_bug_resolution_time,
    get_defect_density,
    get_intersection_metrics,
    load_cycle_time_config,
)
from app.services.carryover import (
    get_carryover_by_sprint,
    get_carryover_summary,
    get_work_item_iteration_history,
    list_moved_work_items,
)
from app.services.capacity import get_team_capacity_vs_load as _team_capacity_vs_load
from app.services.feature_rollup import get_feature_rollup as _feature_rollup
from app.services.sizing_trend import get_sizing_distribution_trend as _sizing_trend
from app.services.trusted_backlog import get_trusted_backlog_scorecard as _trusted_backlog
from app.services.long_running import get_long_running_stories as _long_running
from app.agents.tools.base import ToolDefinition
from app.agents.tools.registry import register_tool_category
from app.agents.tools.scoping import scoped_query

logger = logging.getLogger(__name__)

CATEGORY = "delivery_analytics"

DEFINITIONS = [
    # A. Lookup
    ToolDefinition("find_work_item", "Find Work Item", "Search for a work item by platform ID (#12345) or title substring", CATEGORY),
    ToolDefinition("find_iteration", "Find Iteration", "Search for a sprint/iteration by name", CATEGORY),
    ToolDefinition("find_team", "Find Team", "Search for a team by name", CATEGORY),
    # B. Sprint / Iteration Analysis
    ToolDefinition("get_sprint_overview", "Sprint Overview", "Stats for a sprint: items, points, completion %, contributors, burndown summary", CATEGORY),
    ToolDefinition("get_sprint_comparison", "Sprint Comparison", "Side-by-side comparison of two sprints", CATEGORY),
    ToolDefinition("get_sprint_burndown", "Sprint Burndown", "Daily remaining points/items for a sprint burndown chart", CATEGORY),
    ToolDefinition("get_active_sprints", "Active Sprints", "Currently active and next upcoming sprints with progress", CATEGORY),
    ToolDefinition("get_sprint_scope_change", "Sprint Scope Change", "Items added during a sprint after start — scope creep analysis", CATEGORY),
    ToolDefinition("get_sprint_carryover", "Sprint Carryover", "Incomplete items from a past sprint and their current state", CATEGORY),
    ToolDefinition("get_iteration_carryover_matrix", "Iteration Carryover Matrix", "Per-sprint move-in/move-out counts and carry-over rate for the last N iterations", CATEGORY),
    ToolDefinition("get_team_carryover_summary", "Team Carryover Summary", "Aggregate iteration-path move stats (total moves, carry-over rate, top offenders) for a team", CATEGORY),
    ToolDefinition("get_work_item_iteration_history", "Work Item Iteration History", "Every iteration-path change for a single work item", CATEGORY),
    ToolDefinition("get_iteration_detail", "Iteration Detail", "Quick stats for a single iteration: items, points, completion counts", CATEGORY),
    # C. Velocity and Throughput
    ToolDefinition("get_velocity_trend", "Velocity Trend", "Story points completed per iteration over last N sprints with rolling average", CATEGORY),
    ToolDefinition("get_delivery_throughput_trend", "Throughput Trend", "Daily items created vs completed over time", CATEGORY),
    ToolDefinition("get_velocity_forecast", "Velocity Forecast", "Estimated sprints to clear remaining backlog based on velocity", CATEGORY),
    ToolDefinition("get_team_velocity_comparison", "Team Velocity Comparison", "Compare velocity across teams in a project", CATEGORY),
    # D. Cycle Time and Flow
    ToolDefinition("get_cycle_time_stats", "Cycle Time Stats", "Median, p75, p90 cycle times (activated -> resolved) with type breakdown", CATEGORY),
    ToolDefinition("get_lead_time_stats", "Lead Time Stats", "Lead time analysis (created -> closed) with type breakdown", CATEGORY),
    ToolDefinition("get_wip_analysis", "WIP Analysis", "Current work-in-progress count by state, type, and assignee", CATEGORY),
    ToolDefinition("get_delivery_cumulative_flow", "Cumulative Flow", "Cumulative flow diagram data (daily items by state)", CATEGORY),
    ToolDefinition("get_cycle_time_histogram", "Cycle Time Distribution", "Histogram of cycle times from hours to weeks", CATEGORY),
    ToolDefinition("get_wip_snapshot", "WIP Snapshot", "Quick snapshot of work-in-progress items grouped by state", CATEGORY),
    # E. Backlog Health
    ToolDefinition("get_backlog_overview", "Backlog Overview", "Total open items, unestimated %, aging breakdown, priority distribution, health score", CATEGORY),
    ToolDefinition("get_stale_items", "Stale Items", "Work items not updated in N days, sorted by age", CATEGORY),
    ToolDefinition("get_backlog_composition", "Backlog Composition", "Breakdown by type, state, priority, assignee with unassigned/unestimated counts", CATEGORY),
    ToolDefinition("get_backlog_growth_trend", "Backlog Growth Trend", "Net backlog growth over time (created minus completed)", CATEGORY),
    ToolDefinition("get_stale_backlog_summary", "Stale Backlog Summary", "Stale backlog items grouped by type — items not updated in N days", CATEGORY),
    ToolDefinition("get_backlog_age_histogram", "Backlog Age Distribution", "Age distribution of open backlog items from days to months", CATEGORY),
    ToolDefinition("get_feature_backlog_rollup", "Feature Backlog Rollup", "Per-feature child counts, total/completed points, and t-shirt size distribution", CATEGORY),
    ToolDefinition("get_story_sizing_trend", "Story Sizing Trend", "Weekly distribution of story point sizes and trend slope of average story size", CATEGORY),
    ToolDefinition("get_trusted_backlog_scorecard", "Trusted Backlog Scorecard", "Traffic-light scorecard of the five measurable Scrum trusted-backlog pillars (priority, mix, horizon, scope stability)", CATEGORY),
    ToolDefinition("get_long_running_stories", "Long-Running Stories", "Active items past threshold days with 'why is it stuck?' signals (stalled, iteration-hopping, oversized, reassigned often, etc.)", CATEGORY),
    # F. Team Analytics
    ToolDefinition("get_team_delivery_overview", "Team Overview", "Team stats: members, velocity, active items, throughput, cycle time", CATEGORY),
    ToolDefinition("get_team_workload", "Team Workload", "Work distribution across team members — identifies imbalances", CATEGORY),
    ToolDefinition("get_team_members_delivery", "Team Members Delivery", "Per-member delivery stats: items completed, points, cycle time, bugs resolved", CATEGORY),
    ToolDefinition("get_team_capacity_vs_load", "Team Capacity vs Load", "Rolling capacity (avg completed points) vs planned load for the active iteration", CATEGORY),
    # G. Quality Metrics
    ToolDefinition("get_bug_metrics", "Bug Metrics", "Bug trend, resolution time, defect density, open bug count", CATEGORY),
    ToolDefinition("get_quality_summary", "Quality Summary", "Composite quality view: defect density, escaped defects, rework items", CATEGORY),
    ToolDefinition("get_bug_trend_data", "Bug Trend", "Daily bugs created vs resolved over time", CATEGORY),
    # H. Code-Delivery Intersection
    ToolDefinition("get_code_delivery_intersection", "Code-Delivery Intersection", "Link coverage %, commits per story point, first-commit-to-resolution time", CATEGORY),
    ToolDefinition("get_work_item_linked_commits", "Work Item Linked Commits", "Commits linked to a specific work item", CATEGORY),
    # I. Work Item Description Editing
    ToolDefinition("read_work_item_description", "Read Work Item Description", "Return the full HTML description and metadata of a work item", CATEGORY),
    ToolDefinition("propose_work_item_description", "Propose Work Item Description", "Write an agent-generated HTML description as a draft for user review", CATEGORY),
]


# ── Formatting helpers ────────────────────────────────────────────────


def _fmt(val) -> str:
    if val is None:
        return "—"
    if isinstance(val, float):
        return f"{val:,.1f}"
    if isinstance(val, int):
        return f"{val:,}"
    return str(val)


def _kv_block(data: dict, title: str = "") -> str:
    lines = []
    if title:
        lines.append(f"**{title}**")
    for k, v in data.items():
        label = k.replace("_", " ").title()
        lines.append(f"- {label}: {_fmt(v)}")
    return "\n".join(lines)


def _table(columns: list[str], rows: list[tuple | list]) -> str:
    if not rows:
        return "No results found."
    header = " | ".join(columns)
    sep = " | ".join("---" for _ in columns)
    lines = [header, sep]
    for row in rows:
        lines.append(" | ".join(_fmt(v) for v in row))
    return "\n".join(lines)


def _parse_date(val: str | None) -> date | None:
    if not val:
        return None
    return date.fromisoformat(val)


# ── Name resolution helpers ───────────────────────────────────────────


async def _resolve_project(db: AsyncSession, name: str) -> Project | None:
    result = await db.execute(
        select(Project).where(Project.name.ilike(f"%{name}%")).order_by(Project.name).limit(1)
    )
    return result.scalar_one_or_none()


async def _resolve_contributor(db: AsyncSession, name_or_email: str) -> Contributor | None:
    result = await db.execute(
        select(Contributor).where(
            Contributor.canonical_name.ilike(f"%{name_or_email}%")
            | Contributor.canonical_email.ilike(f"%{name_or_email}%")
        ).order_by(Contributor.canonical_name).limit(1)
    )
    return result.scalar_one_or_none()


async def _resolve_iteration(db: AsyncSession, name: str, project_id=None) -> Iteration | None:
    stmt = select(Iteration).where(Iteration.name.ilike(f"%{name}%"))
    if project_id:
        stmt = stmt.where(Iteration.project_id == project_id)
    stmt = stmt.order_by(Iteration.start_date.desc()).limit(1)
    stmt = scoped_query(stmt, project_col=Iteration.project_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _resolve_team(db: AsyncSession, name: str, project_id=None) -> Team | None:
    stmt = select(Team).where(Team.name.ilike(f"%{name}%"))
    if project_id:
        stmt = stmt.where(Team.project_id == project_id)
    stmt = stmt.order_by(Team.name).limit(1)
    stmt = scoped_query(stmt, project_col=Team.project_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _team_contributor_ids(db: AsyncSession, team_id) -> set:
    result = await db.execute(
        select(TeamMember.contributor_id).where(TeamMember.team_id == team_id)
    )
    return set(result.scalars().all())


async def _resolve_work_item(db: AsyncSession, id_or_platform_id: str) -> WorkItem | None:
    """Resolve a work item by its UUID, platform ID (#1234), or title substring."""
    cleaned = str(id_or_platform_id).lstrip("#").strip()
    if not cleaned:
        return None
    stmt = select(WorkItem)
    try:
        wi_uuid = uuid.UUID(cleaned)
        stmt = stmt.where(WorkItem.id == wi_uuid)
    except (ValueError, AttributeError):
        if cleaned.isdigit():
            stmt = stmt.where(WorkItem.platform_work_item_id == int(cleaned))
        else:
            stmt = stmt.where(WorkItem.title.ilike(f"%{cleaned}%"))
    stmt = scoped_query(stmt.limit(1), project_col=WorkItem.project_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _safe(db: AsyncSession, coro):
    try:
        async with db.begin_nested():
            return await coro
    except Exception as e:
        logger.warning("Delivery tool query failed: %s", e)
        return f"Error: {e}"


_COMPLETED_STATES = ("Resolved", "Closed", "Done", "Completed")
_OPEN_STATES = ("New", "Active", "Committed", "In Progress", "Approved")


# ── Tool factory ──────────────────────────────────────────────────────


def _build_delivery_tools(db: AsyncSession) -> list:

    # ================================================================
    # A. Lookup Tools
    # ================================================================

    @tool
    async def find_work_item(id_or_title: str, project_name: Optional[str] = None) -> str:
        """Search for a work item by platform ID (#12345) or title substring."""
        async def _impl():
            stmt = select(WorkItem)
            cleaned = id_or_title.lstrip("#")
            if cleaned.isdigit():
                stmt = stmt.where(WorkItem.platform_work_item_id == int(cleaned))
            else:
                stmt = stmt.where(WorkItem.title.ilike(f"%{id_or_title}%"))
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    stmt = stmt.where(WorkItem.project_id == p.id)
            stmt = scoped_query(stmt.limit(5), project_col=WorkItem.project_id)
            result = await db.execute(stmt)
            items = result.scalars().all()
            if not items:
                return f"No work items found matching '{id_or_title}'."
            rows = []
            for wi in items:
                rows.append((
                    str(wi.id)[:8], f"#{wi.platform_work_item_id}",
                    wi.work_item_type.value if hasattr(wi.work_item_type, 'value') else wi.work_item_type,
                    wi.title[:60], wi.state,
                    _fmt(wi.story_points),
                ))
            return _table(["ID", "Platform ID", "Type", "Title", "State", "Points"], rows)
        return await _safe(db, _impl())

    @tool
    async def find_iteration(name: str, project_name: Optional[str] = None) -> str:
        """Search for a sprint/iteration by name."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    project_id = p.id
            stmt = select(Iteration).where(Iteration.name.ilike(f"%{name}%"))
            if project_id:
                stmt = stmt.where(Iteration.project_id == project_id)
            stmt = stmt.order_by(Iteration.start_date.desc()).limit(5)
            stmt = scoped_query(stmt, project_col=Iteration.project_id)
            result = await db.execute(stmt)
            iters = result.scalars().all()
            if not iters:
                return f"No iterations found matching '{name}'."
            now = datetime.now(timezone.utc).date()
            rows = []
            for it in iters:
                s, e = it.start_date, it.end_date
                status = "past"
                if s and e:
                    if s <= now <= e:
                        status = "active"
                    elif s > now:
                        status = "upcoming"
                rows.append((str(it.id)[:8], it.name, str(s) if s else "—", str(e) if e else "—", status))
            return _table(["ID", "Name", "Start", "End", "Status"], rows)
        return await _safe(db, _impl())

    @tool
    async def find_team(name: str, project_name: Optional[str] = None) -> str:
        """Search for a team by name."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    project_id = p.id
            stmt = select(Team).where(Team.name.ilike(f"%{name}%"))
            if project_id:
                stmt = stmt.where(Team.project_id == project_id)
            stmt = stmt.order_by(Team.name).limit(5)
            stmt = scoped_query(stmt, project_col=Team.project_id)
            result = await db.execute(stmt)
            teams = result.scalars().all()
            if not teams:
                return f"No teams found matching '{name}'."
            rows = []
            for t in teams:
                mc = await db.execute(select(func.count()).where(TeamMember.team_id == t.id))
                member_count = mc.scalar() or 0
                rows.append((str(t.id)[:8], t.name, member_count, t.platform or "manual"))
            return _table(["ID", "Name", "Members", "Platform"], rows)
        return await _safe(db, _impl())

    # ================================================================
    # B. Sprint / Iteration Analysis
    # ================================================================

    @tool
    async def get_sprint_overview(iteration_name: str, project_name: Optional[str] = None) -> str:
        """Stats for a sprint: items, points, completion %, contributors, top contributors by points."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    project_id = p.id
            it = await _resolve_iteration(db, iteration_name, project_id)
            if not it:
                return f"Iteration '{iteration_name}' not found."
            wi = WorkItem.__table__
            base = wi.c.iteration_id == it.id
            total = (await db.execute(scoped_query(select(func.count()).where(base), project_col=WorkItem.project_id))).scalar() or 0
            completed = (await db.execute(scoped_query(select(func.count()).where(base, wi.c.resolved_at.isnot(None)), project_col=WorkItem.project_id))).scalar() or 0
            total_sp = float((await db.execute(scoped_query(select(func.coalesce(func.sum(wi.c.story_points), 0)).where(base), project_col=WorkItem.project_id))).scalar() or 0)
            completed_sp = float((await db.execute(scoped_query(select(func.coalesce(func.sum(wi.c.story_points), 0)).where(base, wi.c.resolved_at.isnot(None)), project_col=WorkItem.project_id))).scalar() or 0)
            contrib_count = (await db.execute(scoped_query(select(func.count(func.distinct(wi.c.assigned_to_id))).where(base, wi.c.assigned_to_id.isnot(None)), project_col=WorkItem.project_id))).scalar() or 0
            pct = round(completed / total * 100, 1) if total > 0 else 0
            pct_sp = round(completed_sp / total_sp * 100, 1) if total_sp > 0 else 0

            ct = Contributor.__table__
            top_q = scoped_query(
                select(ct.c.canonical_name, func.coalesce(func.sum(wi.c.story_points), 0).label("pts"))
                .select_from(wi.join(ct, wi.c.assigned_to_id == ct.c.id))
                .where(base, wi.c.resolved_at.isnot(None))
                .group_by(ct.c.canonical_name)
                .order_by(func.sum(wi.c.story_points).desc())
                .limit(5),
                project_col=WorkItem.project_id,
            )
            top_rows = (await db.execute(top_q)).all()

            lines = [
                f"**Sprint: {it.name}** ({it.start_date} → {it.end_date})",
                _kv_block({
                    "total_items": total, "completed_items": completed,
                    "completion_rate": f"{pct}%",
                    "total_story_points": total_sp, "completed_story_points": completed_sp,
                    "points_completion": f"{pct_sp}%",
                    "contributors": contrib_count,
                }),
            ]
            if top_rows:
                lines.append("\n**Top Contributors (by points completed)**")
                lines.append(_table(["Contributor", "Points"], [(r.canonical_name, round(r.pts, 1)) for r in top_rows]))
            return "\n".join(lines)
        return await _safe(db, _impl())

    @tool
    async def get_sprint_comparison(sprint_a: str, sprint_b: str, project_name: Optional[str] = None) -> str:
        """Side-by-side comparison of two sprints: velocity, completion rate, cycle time, contributors."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    project_id = p.id
            it_a = await _resolve_iteration(db, sprint_a, project_id)
            it_b = await _resolve_iteration(db, sprint_b, project_id)
            if not it_a or not it_b:
                missing = sprint_a if not it_a else sprint_b
                return f"Iteration '{missing}' not found."
            wi = WorkItem.__table__

            cycle_cfg = await load_cycle_time_config(db, project_id) if project_id else None
            cycle_expr_ab = cycle_hours_expr(wi, cycle_cfg)
            cycle_end_ab = cycle_end_column(wi, cycle_cfg)

            async def _stats(iter_id):
                base = wi.c.iteration_id == iter_id
                total = (await db.execute(scoped_query(select(func.count()).where(base), project_col=WorkItem.project_id))).scalar() or 0
                completed = (await db.execute(scoped_query(select(func.count()).where(base, wi.c.resolved_at.isnot(None)), project_col=WorkItem.project_id))).scalar() or 0
                sp = float((await db.execute(scoped_query(select(func.coalesce(func.sum(wi.c.story_points), 0)).where(base, wi.c.resolved_at.isnot(None)), project_col=WorkItem.project_id))).scalar() or 0)
                contribs = (await db.execute(scoped_query(select(func.count(func.distinct(wi.c.assigned_to_id))).where(base, wi.c.assigned_to_id.isnot(None)), project_col=WorkItem.project_id))).scalar() or 0
                cycle_q = scoped_query(
                    select(
                        func.percentile_cont(0.5).within_group(cycle_expr_ab)
                    ).where(base, wi.c.activated_at.isnot(None), cycle_end_ab.isnot(None)),
                    project_col=WorkItem.project_id,
                )
                median_ct = (await db.execute(cycle_q)).scalar()
                return {
                    "total_items": total, "completed": completed,
                    "completion_rate": f"{round(completed / total * 100, 1)}%" if total else "0%",
                    "story_points": sp, "contributors": contribs,
                    "median_cycle_time_h": round(median_ct or 0, 1),
                }

            sa = await _stats(it_a.id)
            sb = await _stats(it_b.id)
            cols = ["Metric", it_a.name, it_b.name]
            rows = [(k.replace("_", " ").title(), _fmt(sa[k]), _fmt(sb[k])) for k in sa]
            return _table(cols, rows)
        return await _safe(db, _impl())

    @tool
    async def get_sprint_burndown(iteration_name: str, project_name: Optional[str] = None) -> str:
        """Daily remaining points/items for a sprint burndown chart."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    project_id = p.id
            it = await _resolve_iteration(db, iteration_name, project_id)
            if not it:
                return f"Iteration '{iteration_name}' not found."
            data = await _burndown(db, it.id)
            if not data:
                return "No burndown data available (iteration may lack start/end dates)."
            rows = [(d["date"], d["remaining"], d["remaining_items"], d["ideal"]) for d in data]
            return f"**Burndown: {it.name}**\n" + _table(["Date", "Remaining Points", "Remaining Items", "Ideal"], rows)
        return await _safe(db, _impl())

    @tool
    async def get_active_sprints(project_name: Optional[str] = None) -> str:
        """Currently active and next upcoming sprints with progress stats. Upcoming sprints with zero items and zero points are excluded."""
        async def _impl():
            now = datetime.now(timezone.utc).date()
            stmt = select(Iteration)
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    stmt = stmt.where(Iteration.project_id == p.id)
            stmt = stmt.where(Iteration.end_date >= now).order_by(Iteration.start_date).limit(20)
            stmt = scoped_query(stmt, project_col=Iteration.project_id)
            result = await db.execute(stmt)
            iters = result.scalars().all()
            if not iters:
                return "No active or upcoming sprints found."
            wi = WorkItem.__table__
            rows = []
            for it in iters:
                is_upcoming = it.start_date and it.start_date > now
                total = (await db.execute(scoped_query(select(func.count()).where(wi.c.iteration_id == it.id), project_col=WorkItem.project_id))).scalar() or 0
                sp = float((await db.execute(scoped_query(select(func.coalesce(func.sum(wi.c.story_points), 0)).where(wi.c.iteration_id == it.id), project_col=WorkItem.project_id))).scalar() or 0)
                if is_upcoming and total == 0 and sp == 0:
                    continue
                completed = (await db.execute(scoped_query(select(func.count()).where(wi.c.iteration_id == it.id, wi.c.resolved_at.isnot(None)), project_col=WorkItem.project_id))).scalar() or 0
                status = "upcoming" if is_upcoming else "active"
                pct = round(completed / total * 100) if total else 0
                rows.append((it.name, status, str(it.start_date), str(it.end_date), total, completed, f"{pct}%", round(sp, 1)))
            if not rows:
                return "No active or upcoming sprints with assigned work found."
            return _table(["Sprint", "Status", "Start", "End", "Items", "Done", "Progress", "Points"], rows)
        return await _safe(db, _impl())

    @tool
    async def get_sprint_scope_change(iteration_name: str, project_name: Optional[str] = None) -> str:
        """Items added during a sprint after its start date — scope creep analysis."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    project_id = p.id
            it = await _resolve_iteration(db, iteration_name, project_id)
            if not it:
                return f"Iteration '{iteration_name}' not found."
            if not it.start_date:
                return "Iteration has no start date — cannot analyze scope change."
            wi = WorkItem.__table__
            base = wi.c.iteration_id == it.id
            total = (await db.execute(scoped_query(select(func.count()).where(base), project_col=WorkItem.project_id))).scalar() or 0
            added_after_start = (await db.execute(
                scoped_query(select(func.count()).where(base, func.date(wi.c.created_at) > it.start_date), project_col=WorkItem.project_id)
            )).scalar() or 0
            original = total - added_after_start
            creep_pct = round(added_after_start / original * 100, 1) if original > 0 else 0
            return _kv_block({
                "sprint": it.name,
                "original_scope": original,
                "items_added_after_start": added_after_start,
                "current_total": total,
                "scope_creep_pct": f"{creep_pct}%",
            }, "Sprint Scope Change")
        return await _safe(db, _impl())

    @tool
    async def get_sprint_carryover(iteration_name: str, project_name: Optional[str] = None) -> str:
        """Incomplete items from a sprint and their current state, plus items that were moved to a different iteration."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    project_id = p.id
            it = await _resolve_iteration(db, iteration_name, project_id)
            if not it:
                return f"Iteration '{iteration_name}' not found."
            wi = WorkItem.__table__
            ct = Contributor.__table__
            q = scoped_query(
                select(
                    wi.c.platform_work_item_id, wi.c.title, wi.c.state,
                    wi.c.story_points, ct.c.canonical_name,
                )
                .select_from(wi.outerjoin(ct, wi.c.assigned_to_id == ct.c.id))
                .where(wi.c.iteration_id == it.id, wi.c.state.notin_(_COMPLETED_STATES))
                .order_by(wi.c.priority.asc().nullslast())
                .limit(30),
                project_col=WorkItem.project_id,
            )
            rows_data = (await db.execute(q)).all()

            matrix = await get_carryover_by_sprint(db, it.project_id, limit=30)
            sprint_stats = next((m for m in matrix if m["iteration_id"] == str(it.id)), None)
            header_lines = [f"**Carryover from {it.name}**"]
            if sprint_stats:
                header_lines.append(
                    f"Moved out: {sprint_stats['moved_out']} • Moved in: {sprint_stats['moved_in']} • "
                    f"Carry-over rate: {sprint_stats['carryover_rate_pct']}%"
                )

            if not rows_data:
                header_lines.append("No incomplete items remaining in this sprint.")
                return "\n".join(header_lines)

            rows = [(f"#{r[0]}", r[1][:50], r[2], _fmt(r[3]), r[4] or "Unassigned") for r in rows_data]
            header_lines.append(f"({len(rows_data)} incomplete items)")
            return "\n".join(header_lines) + "\n" + _table(
                ["ID", "Title", "State", "Points", "Assignee"], rows
            )
        return await _safe(db, _impl())

    @tool
    async def get_iteration_carryover_matrix(
        project_name: Optional[str] = None,
        team_name: Optional[str] = None,
        limit: int = 12,
    ) -> str:
        """Per-sprint in/out move counts and carry-over rate over the last N iterations.

        Use this to answer questions like "how much work is carrying over between sprints?".
        """
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    project_id = p.id
            team_id = None
            if team_name:
                t = await _resolve_team(db, team_name, project_id)
                if t:
                    team_id = t.id
                    project_id = t.project_id
            if project_id is None:
                return "Please specify a project (or team) to compute carry-over."
            rows = await get_carryover_by_sprint(db, project_id, team_id=team_id, limit=limit)
            if not rows:
                return "No iterations with complete start/end dates found."
            table_rows = [
                (
                    r["iteration_name"],
                    r["total_items"],
                    r["completed_items"],
                    r["moved_out"],
                    r["moved_in"],
                    f"{r['carryover_rate_pct']}%",
                )
                for r in rows
            ]
            title = f"Carry-over by sprint — {team_name or 'project'}"
            return f"**{title}**\n" + _table(
                ["Sprint", "Items", "Done", "Moved Out", "Moved In", "Carry %"], table_rows,
            )
        return await _safe(db, _impl())

    @tool
    async def get_team_carryover_summary(
        team_name: Optional[str] = None,
        project_name: Optional[str] = None,
        days: int = 90,
    ) -> str:
        """Aggregate carry-over stats for a team over the last N days.

        Shows total iteration-path moves, carry-over rate, and the top repeat offenders (items with the most moves).
        """
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    project_id = p.id
            team_id = None
            if team_name:
                t = await _resolve_team(db, team_name, project_id)
                if t:
                    team_id = t.id
                    project_id = t.project_id
            if project_id is None:
                return "Please specify a project (or team) to compute carry-over."
            to_dt = datetime.now(timezone.utc)
            from_dt = to_dt - timedelta(days=days)
            summary = await get_carryover_summary(
                db, project_id, team_id=team_id, from_date=from_dt, to_date=to_dt,
            )
            header = _kv_block({
                "scope": team_name or project_name or "project",
                "window_days": days,
                "total_work_items": summary["total_work_items"],
                "unique_items_moved": summary["unique_work_items_moved"],
                "total_moves": summary["total_moves"],
                "carryover_rate_pct": f"{summary['carryover_rate_pct']}%",
                "avg_moves_per_item": summary["avg_moves_per_item"],
            }, "Carry-over summary")
            offenders = summary.get("top_offenders") or []
            if not offenders:
                return header
            rows = [
                (
                    f"#{o['platform_work_item_id']}" if o.get('platform_work_item_id') else "—",
                    (o.get('title') or '')[:50],
                    o.get('state') or '—',
                    o.get('move_count', 0),
                    o.get('assignee') or "Unassigned",
                )
                for o in offenders[:10]
            ]
            return header + "\n\n**Top repeat offenders**\n" + _table(
                ["ID", "Title", "State", "Moves", "Assignee"], rows,
            )
        return await _safe(db, _impl())

    @tool
    async def get_work_item_iteration_history(
        work_item_id_or_platform_id: str,
        project_name: Optional[str] = None,
    ) -> str:
        """Show every iteration-path change for a single work item, in chronological order."""
        async def _impl():
            wi_obj = await _resolve_work_item(db, work_item_id_or_platform_id)
            if not wi_obj:
                return f"Work item '{work_item_id_or_platform_id}' not found."
            from app.services.carryover import get_work_item_iteration_history as _history
            rows = await _history(db, wi_obj.project_id, wi_obj.id)
            if not rows:
                return f"No iteration-path moves recorded for #{wi_obj.platform_work_item_id}."
            table_rows = [
                (
                    r["changed_at"][:10],
                    (r.get("from_iteration") or {}).get("name") or r.get("from_path") or "—",
                    (r.get("to_iteration") or {}).get("name") or r.get("to_path") or "—",
                    r.get("revision_number"),
                )
                for r in rows
            ]
            return (
                f"**Iteration history for #{wi_obj.platform_work_item_id}** "
                f"({len(rows)} moves)\n"
                + _table(["Date", "From", "To", "Rev"], table_rows)
            )
        return await _safe(db, _impl())

    @tool
    async def get_iteration_detail(iteration_name: str, project_name: Optional[str] = None) -> str:
        """Quick stats for a single iteration: items, points, completion counts."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    project_id = p.id
            it = await _resolve_iteration(db, iteration_name, project_id)
            if not it:
                return f"Iteration '{iteration_name}' not found."
            data = await _iteration_detail(db, it.id)
            pct = round(data["completed_items"] / data["total_items"] * 100, 1) if data["total_items"] else 0
            pct_sp = round(data["completed_points"] / data["total_points"] * 100, 1) if data["total_points"] else 0
            return _kv_block({
                "total_items": data["total_items"],
                "completed_items": data["completed_items"],
                "item_completion": f"{pct}%",
                "total_points": data["total_points"],
                "completed_points": data["completed_points"],
                "points_completion": f"{pct_sp}%",
            }, f"Iteration: {it.name}")
        return await _safe(db, _impl())

    # ================================================================
    # C. Velocity and Throughput
    # ================================================================

    @tool
    async def get_velocity_trend(project_name: Optional[str] = None, team_name: Optional[str] = None, limit: int = 10) -> str:
        """Story points completed per iteration over last N sprints with rolling average."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."

            filters = DeliveryFilters()
            if team_name:
                t = await _resolve_team(db, team_name, project_id)
                if t:
                    member_ids = await _team_contributor_ids(db, t.id)
                    filters.contributor_id = list(member_ids)[0] if len(member_ids) == 1 else None

            data = await get_velocity(db, project_id, filters=filters, limit=limit)
            if not data:
                return "No velocity data available."
            points = [d["points"] for d in data]
            avg_3 = round(sum(points[-3:]) / min(3, len(points[-3:])), 1) if points else 0
            avg_all = round(sum(points) / len(points), 1) if points else 0
            rows = [(d["iteration"], d["points"]) for d in data]
            return (
                _table(["Sprint", "Points"], rows)
                + f"\n\n- Rolling 3-sprint avg: {avg_3}\n- Overall avg: {avg_all}"
            )
        return await _safe(db, _impl())

    @tool
    async def get_delivery_throughput_trend(project_name: Optional[str] = None, days: int = 90) -> str:
        """Daily items created vs completed over time."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."
            data = await get_throughput_trend(db, project_id, days=days)
            if not data:
                return "No throughput data available."
            total_created = sum(d["created"] for d in data)
            total_completed = sum(d["completed"] for d in data)
            last7 = data[-7:] if len(data) >= 7 else data
            week_created = sum(d["created"] for d in last7)
            week_completed = sum(d["completed"] for d in last7)
            return _kv_block({
                "period": f"Last {days} days",
                "total_created": total_created,
                "total_completed": total_completed,
                "net_change": total_created - total_completed,
                "last_7d_created": week_created,
                "last_7d_completed": week_completed,
                "data_points": len(data),
            }, "Throughput Trend")
        return await _safe(db, _impl())

    @tool
    async def get_velocity_forecast(project_name: Optional[str] = None, team_name: Optional[str] = None) -> str:
        """Estimated sprints to clear remaining backlog based on velocity."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."

            data = await get_velocity(db, project_id, limit=10)
            if not data or len(data) < 2:
                return "Not enough velocity data for forecasting (need at least 2 sprints)."
            points = [d["points"] for d in data]
            avg = sum(points) / len(points)
            min_v = min(points) if points else 0
            max_v = max(points) if points else 0

            wi = WorkItem.__table__
            remaining_q = scoped_query(
                select(func.coalesce(func.sum(wi.c.story_points), 0)).where(
                    wi.c.project_id == project_id, wi.c.state.notin_(_COMPLETED_STATES),
                ),
                project_col=WorkItem.project_id,
            )
            remaining_sp = float((await db.execute(remaining_q)).scalar() or 0)
            remaining_items = (await db.execute(
                scoped_query(
                    select(func.count()).where(wi.c.project_id == project_id, wi.c.state.notin_(_COMPLETED_STATES)),
                    project_col=WorkItem.project_id,
                )
            )).scalar() or 0

            def sprints_to_clear(velocity):
                return round(remaining_sp / velocity, 1) if velocity > 0 else float("inf")

            return _kv_block({
                "remaining_story_points": remaining_sp,
                "remaining_items": remaining_items,
                "avg_velocity": round(avg, 1),
                "min_velocity": round(min_v, 1),
                "max_velocity": round(max_v, 1),
                "sprints_at_avg_velocity": sprints_to_clear(avg),
                "sprints_at_min_velocity": sprints_to_clear(min_v),
                "sprints_at_max_velocity": sprints_to_clear(max_v),
            }, "Velocity Forecast")
        return await _safe(db, _impl())

    @tool
    async def get_team_velocity_comparison(project_name: Optional[str] = None, limit: int = 5) -> str:
        """Compare velocity across teams in a project (last 3 sprints avg)."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."

            teams_q = scoped_query(
                select(Team).where(Team.project_id == project_id).order_by(Team.name).limit(limit),
                project_col=Team.project_id,
            )
            teams = (await db.execute(teams_q)).scalars().all()
            if not teams:
                return "No teams found in this project."

            wi = WorkItem.__table__
            it = Iteration.__table__
            rows = []
            for team in teams:
                member_ids = await _team_contributor_ids(db, team.id)
                if not member_ids:
                    rows.append((team.name, 0, 0, "—"))
                    continue
                q = scoped_query(
                    select(it.c.name, func.coalesce(func.sum(wi.c.story_points), 0).label("pts"))
                    .select_from(wi.join(it, wi.c.iteration_id == it.c.id))
                    .where(
                        wi.c.project_id == project_id,
                        wi.c.assigned_to_id.in_(member_ids),
                        wi.c.resolved_at.isnot(None),
                    )
                    .group_by(it.c.name, it.c.start_date)
                    .order_by(it.c.start_date.desc())
                    .limit(3),
                    project_col=WorkItem.project_id,
                )
                sprint_data = (await db.execute(q)).all()
                pts = [float(r.pts) for r in sprint_data]
                avg_v = round(sum(pts) / len(pts), 1) if pts else 0
                mc = len(member_ids)
                rows.append((team.name, mc, avg_v, round(avg_v / mc, 1) if mc else 0))
            return _table(["Team", "Members", "Avg Velocity (3 sprints)", "Per Member"], rows)
        return await _safe(db, _impl())

    # ================================================================
    # D. Cycle Time and Flow
    # ================================================================

    @tool
    async def get_cycle_time_stats(project_name: Optional[str] = None, work_item_type: Optional[str] = None, from_date: Optional[str] = None, to_date: Optional[str] = None) -> str:
        """Median, p75, p90 cycle times with type breakdown. Cycle-time endpoints are configurable per project via ``ProjectDeliverySettings``."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."

            wi = WorkItem.__table__
            cycle_cfg = await load_cycle_time_config(db, project_id)
            hours_expr = cycle_hours_expr(wi, cycle_cfg)
            end_col = cycle_end_column(wi, cycle_cfg)
            base = [wi.c.project_id == project_id, wi.c.activated_at.isnot(None), end_col.isnot(None)]
            if work_item_type:
                base.append(wi.c.work_item_type == work_item_type)
            fd, td = _parse_date(from_date), _parse_date(to_date)
            if fd:
                base.append(end_col >= fd)
            if td:
                base.append(end_col <= td)

            q = scoped_query(
                select(
                    func.percentile_cont(0.5).within_group(hours_expr).label("p50"),
                    func.percentile_cont(0.75).within_group(hours_expr).label("p75"),
                    func.percentile_cont(0.9).within_group(hours_expr).label("p90"),
                    func.count().label("sample"),
                ).where(*base),
                project_col=WorkItem.project_id,
            )
            row = (await db.execute(q)).one_or_none()

            type_q = scoped_query(
                select(
                    wi.c.work_item_type,
                    func.percentile_cont(0.5).within_group(hours_expr).label("median"),
                    func.count().label("n"),
                )
                .where(*base)
                .group_by(wi.c.work_item_type),
                project_col=WorkItem.project_id,
            )
            type_rows = (await db.execute(type_q)).all()

            lines = [_kv_block({
                "median_hours": round(row.p50 or 0, 1),
                "p75_hours": round(row.p75 or 0, 1),
                "p90_hours": round(row.p90 or 0, 1),
                "sample_size": row.sample,
            }, "Cycle Time (Activated → Resolved)")]
            if type_rows:
                lines.append("\n**By Type**")
                lines.append(_table(["Type", "Median (h)", "Count"], [(r[0], round(r[1] or 0, 1), r[2]) for r in type_rows]))
            return "\n".join(lines)
        return await _safe(db, _impl())

    @tool
    async def get_lead_time_stats(project_name: Optional[str] = None, from_date: Optional[str] = None, to_date: Optional[str] = None) -> str:
        """Lead time analysis (created -> closed) with type breakdown."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."

            wi = WorkItem.__table__
            hours_expr = extract("epoch", wi.c.closed_at - wi.c.created_at) / 3600
            base = [wi.c.project_id == project_id, wi.c.closed_at.isnot(None)]
            fd, td = _parse_date(from_date), _parse_date(to_date)
            if fd:
                base.append(wi.c.closed_at >= fd)
            if td:
                base.append(wi.c.closed_at <= td)

            q = scoped_query(
                select(
                    func.percentile_cont(0.5).within_group(hours_expr).label("p50"),
                    func.percentile_cont(0.75).within_group(hours_expr).label("p75"),
                    func.percentile_cont(0.9).within_group(hours_expr).label("p90"),
                    func.count().label("sample"),
                ).where(*base),
                project_col=WorkItem.project_id,
            )
            row = (await db.execute(q)).one_or_none()

            type_q = scoped_query(
                select(wi.c.work_item_type, func.percentile_cont(0.5).within_group(hours_expr).label("median"), func.count().label("n"))
                .where(*base)
                .group_by(wi.c.work_item_type),
                project_col=WorkItem.project_id,
            )
            type_rows = (await db.execute(type_q)).all()

            lines = [_kv_block({
                "median_hours": round(row.p50 or 0, 1),
                "p75_hours": round(row.p75 or 0, 1),
                "p90_hours": round(row.p90 or 0, 1),
                "sample_size": row.sample,
            }, "Lead Time (Created → Closed)")]
            if type_rows:
                lines.append("\n**By Type**")
                lines.append(_table(["Type", "Median (h)", "Count"], [(r[0], round(r[1] or 0, 1), r[2]) for r in type_rows]))
            return "\n".join(lines)
        return await _safe(db, _impl())

    @tool
    async def get_wip_analysis(project_name: Optional[str] = None, team_name: Optional[str] = None) -> str:
        """Current work-in-progress count by state, type, and assignee."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."

            wi = WorkItem.__table__
            ct = Contributor.__table__
            base = [wi.c.project_id == project_id, wi.c.state.notin_(_COMPLETED_STATES)]
            if team_name:
                t = await _resolve_team(db, team_name, project_id)
                if t:
                    member_ids = await _team_contributor_ids(db, t.id)
                    if member_ids:
                        base.append(wi.c.assigned_to_id.in_(member_ids))

            total_wip = (await db.execute(scoped_query(select(func.count()).where(*base), project_col=WorkItem.project_id))).scalar() or 0
            by_state = (await db.execute(
                scoped_query(
                    select(wi.c.state, func.count()).where(*base).group_by(wi.c.state).order_by(func.count().desc()),
                    project_col=WorkItem.project_id,
                )
            )).all()
            by_type = (await db.execute(
                scoped_query(
                    select(wi.c.work_item_type, func.count()).where(*base).group_by(wi.c.work_item_type).order_by(func.count().desc()),
                    project_col=WorkItem.project_id,
                )
            )).all()
            by_assignee = (await db.execute(
                scoped_query(
                    select(ct.c.canonical_name, func.count().label("c"))
                    .select_from(wi.join(ct, wi.c.assigned_to_id == ct.c.id))
                    .where(*base).group_by(ct.c.canonical_name).order_by(func.count().desc()).limit(10),
                    project_col=WorkItem.project_id,
                )
            )).all()
            unassigned = (await db.execute(
                scoped_query(select(func.count()).where(*base, wi.c.assigned_to_id.is_(None)), project_col=WorkItem.project_id)
            )).scalar() or 0

            lines = [f"**Work In Progress: {total_wip} items**"]
            lines.append("\n**By State**\n" + _table(["State", "Count"], [(r[0], r[1]) for r in by_state]))
            lines.append("\n**By Type**\n" + _table(["Type", "Count"], [(r[0], r[1]) for r in by_type]))
            lines.append(f"\n**By Assignee** (unassigned: {unassigned})\n" + _table(["Assignee", "Count"], [(r[0], r[1]) for r in by_assignee]))
            return "\n".join(lines)
        return await _safe(db, _impl())

    @tool
    async def get_delivery_cumulative_flow(project_name: Optional[str] = None, days: int = 90) -> str:
        """Cumulative flow diagram data — daily snapshot of items by state."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."
            data = await _cumulative_flow(db, project_id, days=days)
            states = data.get("states", [])
            rows_data = data.get("data", [])
            if not rows_data:
                return "No cumulative flow data available."
            sample = rows_data[-1] if rows_data else {}
            lines = [f"**Cumulative Flow ({days} days, {len(rows_data)} data points)**"]
            lines.append("Current state distribution:")
            for s in states:
                lines.append(f"- {s}: {sample.get(s, 0)}")
            return "\n".join(lines)
        return await _safe(db, _impl())

    @tool
    async def get_cycle_time_histogram(project_name: Optional[str] = None) -> str:
        """Histogram of cycle times (activated -> resolved) from hours to weeks."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."
            data = await get_cycle_time_distribution(db, project_id)
            if not data or all(d["count"] == 0 for d in data):
                return "No cycle time data available."
            total = sum(d["count"] for d in data)
            rows = [(d["range"], d["count"], f"{round(d['count'] / total * 100, 1)}%") for d in data if d["count"] > 0]
            return "**Cycle Time Distribution**\n" + _table(["Range", "Count", "Pct"], rows)
        return await _safe(db, _impl())

    @tool
    async def get_wip_snapshot(project_name: Optional[str] = None) -> str:
        """Quick snapshot of work-in-progress items grouped by state."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."
            data = await get_wip_by_state(db, project_id)
            if not data:
                return "No work in progress."
            total = sum(d["count"] for d in data)
            rows = [(d["state"], d["count"]) for d in data]
            return f"**WIP Snapshot: {total} items**\n" + _table(["State", "Count"], rows)
        return await _safe(db, _impl())

    # ================================================================
    # E. Backlog Health
    # ================================================================

    @tool
    async def get_backlog_overview(project_name: Optional[str] = None) -> str:
        """Total open items, unestimated %, aging breakdown, priority distribution, health score."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."

            wi = WorkItem.__table__
            base = [wi.c.project_id == project_id, wi.c.state.notin_(_COMPLETED_STATES)]
            total_open = (await db.execute(scoped_query(select(func.count()).where(*base), project_col=WorkItem.project_id))).scalar() or 0
            unestimated = (await db.execute(scoped_query(select(func.count()).where(*base, wi.c.story_points.is_(None)), project_col=WorkItem.project_id))).scalar() or 0
            unassigned = (await db.execute(scoped_query(select(func.count()).where(*base, wi.c.assigned_to_id.is_(None)), project_col=WorkItem.project_id))).scalar() or 0

            stale_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            stale = (await db.execute(scoped_query(select(func.count()).where(*base, wi.c.updated_at < stale_cutoff), project_col=WorkItem.project_id))).scalar() or 0

            by_priority = (await db.execute(
                scoped_query(
                    select(wi.c.priority, func.count()).where(*base).group_by(wi.c.priority).order_by(wi.c.priority.asc().nullslast()),
                    project_col=WorkItem.project_id,
                )
            )).all()

            health_deductions = 0
            if total_open > 0:
                if unestimated / total_open > 0.3:
                    health_deductions += 20
                if unassigned / total_open > 0.3:
                    health_deductions += 15
                if stale / total_open > 0.2:
                    health_deductions += 25
            health_score = max(0, 100 - health_deductions)

            lines = [_kv_block({
                "total_open_items": total_open,
                "unestimated": f"{unestimated} ({round(unestimated / total_open * 100, 1)}%)" if total_open else "0",
                "unassigned": f"{unassigned} ({round(unassigned / total_open * 100, 1)}%)" if total_open else "0",
                "stale_30d": stale,
                "health_score": f"{health_score}/100",
            }, "Backlog Overview")]
            if by_priority:
                lines.append("\n**By Priority**")
                lines.append(_table(["Priority", "Count"], [(f"P{r[0]}" if r[0] else "None", r[1]) for r in by_priority]))
            return "\n".join(lines)
        return await _safe(db, _impl())

    @tool
    async def get_stale_items(project_name: Optional[str] = None, days: int = 30, limit: int = 20) -> str:
        """Work items not updated in N days, sorted by age."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."

            wi = WorkItem.__table__
            ct = Contributor.__table__
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            q = scoped_query(
                select(wi.c.platform_work_item_id, wi.c.title, wi.c.state, wi.c.work_item_type, wi.c.updated_at, ct.c.canonical_name)
                .select_from(wi.outerjoin(ct, wi.c.assigned_to_id == ct.c.id))
                .where(wi.c.project_id == project_id, wi.c.state.notin_(_COMPLETED_STATES), wi.c.updated_at < cutoff)
                .order_by(wi.c.updated_at.asc())
                .limit(limit),
                project_col=WorkItem.project_id,
            )
            rows_data = (await db.execute(q)).all()
            if not rows_data:
                return f"No stale items (nothing untouched for {days}+ days)."
            rows = []
            for r in rows_data:
                age = (datetime.now(timezone.utc) - r.updated_at).days if r.updated_at else 0
                rows.append((f"#{r[0]}", r[1][:45], r[2], r[3], f"{age}d", r[5] or "Unassigned"))
            return _table(["ID", "Title", "State", "Type", "Age", "Assignee"], rows)
        return await _safe(db, _impl())

    @tool
    async def get_backlog_composition(project_name: Optional[str] = None) -> str:
        """Breakdown of open backlog by type, state, priority, with unassigned/unestimated counts."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."

            wi = WorkItem.__table__
            base = [wi.c.project_id == project_id, wi.c.state.notin_(_COMPLETED_STATES)]
            by_type = (await db.execute(
                scoped_query(
                    select(wi.c.work_item_type, func.count()).where(*base).group_by(wi.c.work_item_type).order_by(func.count().desc()),
                    project_col=WorkItem.project_id,
                )
            )).all()
            by_state = (await db.execute(
                scoped_query(
                    select(wi.c.state, func.count()).where(*base).group_by(wi.c.state).order_by(func.count().desc()),
                    project_col=WorkItem.project_id,
                )
            )).all()
            by_priority = (await db.execute(
                scoped_query(
                    select(wi.c.priority, func.count()).where(*base).group_by(wi.c.priority).order_by(wi.c.priority.asc().nullslast()),
                    project_col=WorkItem.project_id,
                )
            )).all()

            lines = ["**By Type**", _table(["Type", "Count"], [(r[0], r[1]) for r in by_type])]
            lines += ["\n**By State**", _table(["State", "Count"], [(r[0], r[1]) for r in by_state])]
            lines += ["\n**By Priority**", _table(["Priority", "Count"], [(f"P{r[0]}" if r[0] else "None", r[1]) for r in by_priority])]
            return "\n".join(lines)
        return await _safe(db, _impl())

    @tool
    async def get_backlog_growth_trend(project_name: Optional[str] = None, days: int = 90) -> str:
        """Net backlog growth over time (created minus completed)."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."
            data = await get_backlog_growth(db, project_id, days=days)
            if not data:
                return "No backlog growth data available."
            total_created = sum(d["created"] for d in data)
            total_completed = sum(d["completed"] for d in data)
            net = total_created - total_completed
            return _kv_block({
                "period": f"Last {days} days ({len(data)} data points)",
                "total_created": total_created,
                "total_completed": total_completed,
                "net_growth": f"{'+' if net > 0 else ''}{net}",
                "avg_daily_net": round(net / max(len(data), 1), 1),
            }, "Backlog Growth Trend")
        return await _safe(db, _impl())

    @tool
    async def get_stale_backlog_summary(project_name: Optional[str] = None, days: int = 30) -> str:
        """Stale backlog items grouped by type — items not updated in N days."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."
            data = await get_stale_backlog(db, project_id, stale_days=days)
            if not data:
                return f"No stale items (nothing untouched for {days}+ days)."
            total = sum(d["count"] for d in data)
            rows = [(d["type"], d["count"]) for d in data]
            return f"**Stale Backlog ({days}+ days): {total} items**\n" + _table(["Type", "Count"], rows)
        return await _safe(db, _impl())

    @tool
    async def get_backlog_age_histogram(project_name: Optional[str] = None) -> str:
        """Age distribution of open backlog items from days to months."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."
            data = await get_backlog_age_distribution(db, project_id)
            if not data or all(d["count"] == 0 for d in data):
                return "No open backlog items."
            total = sum(d["count"] for d in data)
            rows = [(d["range"], d["count"], f"{round(d['count'] / total * 100, 1)}%") for d in data if d["count"] > 0]
            return "**Backlog Age Distribution**\n" + _table(["Age Range", "Count", "Pct"], rows)
        return await _safe(db, _impl())

    @tool
    async def get_feature_backlog_rollup(
        project_name: Optional[str] = None,
        team_name: Optional[str] = None,
        include_completed_features: bool = False,
        limit: int = 20,
    ) -> str:
        """Feature-level backlog: child counts, completed vs total story points, and t-shirt distribution per feature."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    project_id = p.id
            team_id = None
            if team_name:
                t = await _resolve_team(db, team_name, project_id)
                if t:
                    team_id = t.id
                    project_id = t.project_id
            if project_id is None:
                return "Please specify a project (or team)."
            data = await _feature_rollup(
                db, project_id,
                team_id=team_id,
                include_completed_features=include_completed_features,
                limit=limit,
            )
            if not data["features"]:
                return "No features in scope."
            tshirt_field = data.get("tshirt_custom_field")
            rows = [
                (
                    f"#{f['platform_work_item_id']}",
                    (f["title"] or "")[:48],
                    f["state"],
                    f["total_items"],
                    f["completed_items"],
                    f"{f['completed_points']}/{f['total_points']}",
                    f"{f['completion_pct']}%",
                )
                for f in data["features"]
            ]
            totals = data["totals"]
            prefix = f"**Feature rollup** ({totals['feature_count']} features)"
            if tshirt_field:
                prefix += f" — t-shirt field: `{tshirt_field}`"
            return prefix + "\n" + _table(
                ["ID", "Feature", "State", "Items", "Done", "Pts D/T", "%"], rows,
            )
        return await _safe(db, _impl())

    @tool
    async def get_story_sizing_trend(
        project_name: Optional[str] = None,
        team_name: Optional[str] = None,
        weeks: int = 12,
        include_unsized: bool = True,
    ) -> str:
        """Weekly distribution of story point sizes + trend slope of average story size. Negative slope means stories are shrinking."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    project_id = p.id
            team_id = None
            if team_name:
                t = await _resolve_team(db, team_name, project_id)
                if t:
                    team_id = t.id
                    project_id = t.project_id
            if project_id is None:
                return "Please specify a project (or team)."
            data = await _sizing_trend(
                db, project_id,
                team_id=team_id,
                weeks=weeks,
                include_unsized=include_unsized,
            )
            bucket_order = data["bucket_order"]
            rows = []
            for s in data["series"]:
                row = [s["week_start"], s["total"], s["avg_points"] if s["avg_points"] is not None else "-"]
                row.extend(s["buckets"].get(b, 0) for b in bucket_order)
                rows.append(row)
            totals_row = ["**totals**", sum(s["total"] for s in data["series"]), "-"]
            totals_row.extend(data["totals"].get(b, 0) for b in bucket_order)
            rows.append(totals_row)
            header = ["Week", "N", "Avg pts"] + bucket_order
            slope = data["avg_points_trend_slope"]
            direction = (
                "shrinking"
                if slope is not None and slope < -0.02
                else "growing"
                if slope is not None and slope > 0.02
                else "stable"
            )
            prefix = f"**Story sizing trend** ({data['weeks']}w, by {data['basis']}) — avg-points slope `{slope}` ({direction})"
            return prefix + "\n" + _table(header, rows)
        return await _safe(db, _impl())

    @tool
    async def get_trusted_backlog_scorecard(
        project_name: Optional[str] = None,
        team_name: Optional[str] = None,
    ) -> str:
        """Traffic-light scorecard for the five measurable trusted-backlog pillars: priority confidence, work mix, planning horizon, planned scope stability, and current sprint stability."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    project_id = p.id
            team_id = None
            if team_name:
                t = await _resolve_team(db, team_name, project_id)
                if t:
                    team_id = t.id
                    project_id = t.project_id
            if project_id is None:
                return "Please specify a project (or team)."
            data = await _trusted_backlog(db, project_id, team_id=team_id)
            light_icon = {
                "green": "🟢", "yellow": "🟡", "red": "🔴", "unknown": "⚪",
            }
            rows = [
                (
                    light_icon.get(p["traffic_light"], "⚪"),
                    p["label"],
                    p["score"] if p["measurable"] else "-",
                    p["traffic_light"],
                )
                for p in data["pillars"]
            ]
            overall = data["overall_traffic_light"]
            header = f"**Trusted Backlog Scorecard** — overall {light_icon.get(overall, '⚪')} ({data['overall_score']})"
            table = _table(["", "Pillar", "Score", "Status"], rows)
            lines = [header, table]
            for p in data["pillars"]:
                if not p["measurable"]:
                    continue
                detail_pairs = ", ".join(
                    f"{k}={_fmt(v)}" for k, v in p["details"].items()
                    if not isinstance(v, str) or len(str(v)) < 80
                )
                lines.append(f"\n**{p['label']}**: {detail_pairs}")
            return "\n".join(lines)
        return await _safe(db, _impl())

    @tool
    async def get_long_running_stories(
        project_name: Optional[str] = None,
        team_name: Optional[str] = None,
        min_days_active: Optional[int] = None,
        limit: int = 25,
        include_bugs: bool = True,
    ) -> str:
        """Active items running longer than the project's long-running threshold with 'why is it stuck?' signals like stalled, iteration-hopping, reassigned, oversized."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    project_id = p.id
            team_id = None
            if team_name:
                t = await _resolve_team(db, team_name, project_id)
                if t:
                    team_id = t.id
                    project_id = t.project_id
            if project_id is None:
                return "Please specify a project (or team)."
            data = await _long_running(
                db, project_id,
                team_id=team_id,
                min_days_active=min_days_active,
                limit=limit,
                include_bugs=include_bugs,
            )
            if data["count"] == 0:
                return f"No active items older than {data['threshold_days']}d."
            rows = [
                (
                    f"#{item['platform_work_item_id']}",
                    (item["title"] or "")[:42],
                    item["state"],
                    item["days_active"],
                    item["days_since_update"],
                    item["assigned_to_name"] or "unassigned",
                    ",".join(item["signals"]) or "-",
                )
                for item in data["items"]
            ]
            summary_lines = [f"**Long-running stories** (>{data['threshold_days']}d active, {data['count']} items)"]
            if data["summary_signals"]:
                sig_str = ", ".join(f"{k}={v}" for k, v in sorted(data["summary_signals"].items(), key=lambda x: -x[1]))
                summary_lines.append(f"Signal counts: {sig_str}")
            return "\n".join(summary_lines) + "\n" + _table(
                ["ID", "Title", "State", "Days", "Since upd.", "Owner", "Signals"], rows,
            )
        return await _safe(db, _impl())

    # ================================================================
    # F. Team Analytics
    # ================================================================

    @tool
    async def get_team_delivery_overview(team_name: str, project_name: Optional[str] = None) -> str:
        """Team stats: members, velocity, active items, throughput, cycle time."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    project_id = p.id
            t = await _resolve_team(db, team_name, project_id)
            if not t:
                return f"Team '{team_name}' not found."
            member_ids = await _team_contributor_ids(db, t.id)
            mc = len(member_ids)

            wi = WorkItem.__table__
            it = Iteration.__table__
            base = [wi.c.project_id == t.project_id]
            if member_ids:
                base.append(wi.c.assigned_to_id.in_(member_ids))

            cycle_cfg = await load_cycle_time_config(db, t.project_id)
            cycle_expr_t = cycle_hours_expr(wi, cycle_cfg)
            cycle_end_t = cycle_end_column(wi, cycle_cfg)

            active = (await db.execute(scoped_query(select(func.count()).where(*base, wi.c.state.notin_(_COMPLETED_STATES)), project_col=WorkItem.project_id))).scalar() or 0
            completed_30d = (await db.execute(
                scoped_query(
                    select(func.count()).where(*base, wi.c.resolved_at.isnot(None), wi.c.resolved_at >= datetime.now(timezone.utc) - timedelta(days=30)),
                    project_col=WorkItem.project_id,
                )
            )).scalar() or 0

            velocity_q = scoped_query(
                select(func.coalesce(func.sum(wi.c.story_points), 0).label("pts"))
                .select_from(wi.join(it, wi.c.iteration_id == it.c.id))
                .where(*base, wi.c.resolved_at.isnot(None))
                .group_by(it.c.id, it.c.start_date)
                .order_by(it.c.start_date.desc())
                .limit(3),
                project_col=WorkItem.project_id,
            )
            vel_rows = (await db.execute(velocity_q)).all()
            pts = [float(r.pts) for r in vel_rows]
            avg_vel = round(sum(pts) / len(pts), 1) if pts else 0

            cycle_q = scoped_query(
                select(
                    func.percentile_cont(0.5).within_group(cycle_expr_t)
                ).where(*base, wi.c.activated_at.isnot(None), cycle_end_t.isnot(None)),
                project_col=WorkItem.project_id,
            )
            median_ct = (await db.execute(cycle_q)).scalar()

            return _kv_block({
                "team": t.name,
                "members": mc,
                "active_items": active,
                "completed_last_30d": completed_30d,
                "avg_velocity_3_sprints": avg_vel,
                "median_cycle_time_h": round(median_ct or 0, 1),
            }, "Team Overview")
        return await _safe(db, _impl())

    @tool
    async def get_team_workload(team_name: str, project_name: Optional[str] = None) -> str:
        """Work distribution across team members — identifies imbalances."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    project_id = p.id
            t = await _resolve_team(db, team_name, project_id)
            if not t:
                return f"Team '{team_name}' not found."
            member_ids = await _team_contributor_ids(db, t.id)
            if not member_ids:
                return f"Team '{t.name}' has no members."

            wi = WorkItem.__table__
            ct = Contributor.__table__
            q = scoped_query(
                select(
                    ct.c.canonical_name,
                    func.count().filter(wi.c.state.notin_(_COMPLETED_STATES)).label("active"),
                    func.count().filter(wi.c.resolved_at.isnot(None)).label("completed"),
                    func.coalesce(func.sum(wi.c.story_points).filter(wi.c.resolved_at.isnot(None)), 0).label("pts"),
                )
                .select_from(wi.join(ct, wi.c.assigned_to_id == ct.c.id))
                .where(wi.c.project_id == t.project_id, wi.c.assigned_to_id.in_(member_ids))
                .group_by(ct.c.canonical_name)
                .order_by(func.count().filter(wi.c.state.notin_(_COMPLETED_STATES)).desc()),
                project_col=WorkItem.project_id,
            )
            rows_data = (await db.execute(q)).all()
            if not rows_data:
                return "No workload data for this team."
            rows = [(r[0], r.active, r.completed, round(float(r.pts), 1)) for r in rows_data]
            return f"**Workload: {t.name}**\n" + _table(["Member", "Active", "Completed", "Points Delivered"], rows)
        return await _safe(db, _impl())

    @tool
    async def get_team_members_delivery(team_name: str, project_name: Optional[str] = None) -> str:
        """Per-member delivery stats: items completed, points, cycle time, bugs resolved."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    project_id = p.id
            t = await _resolve_team(db, team_name, project_id)
            if not t:
                return f"Team '{team_name}' not found."
            member_ids = await _team_contributor_ids(db, t.id)
            if not member_ids:
                return f"Team '{t.name}' has no members."

            wi = WorkItem.__table__
            ct = Contributor.__table__
            cycle_cfg = await load_cycle_time_config(db, t.project_id)
            cycle_expr_m = cycle_hours_expr(wi, cycle_cfg)
            cycle_end_m = cycle_end_column(wi, cycle_cfg)
            q = scoped_query(
                select(
                    ct.c.canonical_name,
                    func.count().filter(wi.c.resolved_at.isnot(None)).label("completed"),
                    func.coalesce(func.sum(wi.c.story_points).filter(wi.c.resolved_at.isnot(None)), 0).label("pts"),
                    func.percentile_cont(0.5).within_group(cycle_expr_m)
                        .filter(wi.c.activated_at.isnot(None), cycle_end_m.isnot(None)).label("med_ct"),
                    func.count().filter(wi.c.work_item_type == "bug", wi.c.resolved_at.isnot(None)).label("bugs"),
                )
                .select_from(wi.join(ct, wi.c.assigned_to_id == ct.c.id))
                .where(wi.c.project_id == t.project_id, wi.c.assigned_to_id.in_(member_ids))
                .group_by(ct.c.canonical_name)
                .order_by(func.coalesce(func.sum(wi.c.story_points).filter(wi.c.resolved_at.isnot(None)), 0).desc()),
                project_col=WorkItem.project_id,
            )
            rows_data = (await db.execute(q)).all()
            if not rows_data:
                return "No delivery data for this team."
            rows = [(r[0], r.completed, round(float(r.pts), 1), round(r.med_ct or 0, 1), r.bugs) for r in rows_data]
            return f"**Team Members: {t.name}**\n" + _table(["Member", "Completed", "Points", "Median CT (h)", "Bugs Resolved"], rows)
        return await _safe(db, _impl())

    @tool
    async def get_team_capacity_vs_load(
        team_name: str,
        project_name: Optional[str] = None,
        iteration_name: Optional[str] = None,
    ) -> str:
        """Show rolling capacity vs. planned load for a team for the active (or specified) iteration."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    project_id = p.id
            t = await _resolve_team(db, team_name, project_id)
            if not t:
                return f"Team '{team_name}' not found."
            iteration_id = None
            if iteration_name:
                it = await _resolve_iteration(db, iteration_name, t.project_id)
                if it:
                    iteration_id = it.id
            data = await _team_capacity_vs_load(
                db, t.project_id, t.id, iteration_id=iteration_id,
            )

            hdr = {
                "team": t.name,
                "rolling_window_sprints": data["rolling_window"],
                "avg_capacity_points": data["avg_capacity_points"],
            }
            if data.get("target_iteration"):
                hdr["iteration"] = data["target_iteration"]["name"]
                hdr["planned_points"] = data["planned_points"]
                hdr["ready_points"] = data["ready_points"]
                hdr["planned_items"] = data.get("planned_items")
                hdr["unestimated_items"] = data.get("unestimated_items")
                hdr["load_ratio"] = data.get("load_ratio")
                hdr["load_status"] = data.get("load_status")
            return _kv_block(hdr, f"Capacity vs. Load — {t.name}")
        return await _safe(db, _impl())

    # ================================================================
    # G. Quality Metrics
    # ================================================================

    @tool
    async def get_bug_metrics(project_name: Optional[str] = None, from_date: Optional[str] = None, to_date: Optional[str] = None) -> str:
        """Bug trend, resolution time, defect density, open bug count."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."

            wi = WorkItem.__table__
            base = [wi.c.project_id == project_id, wi.c.work_item_type == "bug"]
            open_bugs = (await db.execute(scoped_query(select(func.count()).where(*base, wi.c.state.notin_(_COMPLETED_STATES)), project_col=WorkItem.project_id))).scalar() or 0
            total_bugs = (await db.execute(scoped_query(select(func.count()).where(*base), project_col=WorkItem.project_id))).scalar() or 0

            res = await get_bug_resolution_time(db, project_id)
            density = await get_defect_density(db, project_id)

            return _kv_block({
                "total_bugs": total_bugs,
                "open_bugs": open_bugs,
                "resolved_bugs": total_bugs - open_bugs,
                "median_resolution_hours": res["median_hours"],
                "p90_resolution_hours": res["p90_hours"],
                "defect_density": f"{density['defect_density_pct']}%",
            }, "Bug Metrics")
        return await _safe(db, _impl())

    @tool
    async def get_quality_summary(project_name: Optional[str] = None) -> str:
        """Composite quality view: defect density, escaped defects, rework items."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."

            wi = WorkItem.__table__
            density = await get_defect_density(db, project_id)
            res = await get_bug_resolution_time(db, project_id)

            base = [wi.c.project_id == project_id, wi.c.work_item_type == "bug"]
            recent_bugs = (await db.execute(
                scoped_query(
                    select(func.count()).where(*base, wi.c.created_at >= datetime.now(timezone.utc) - timedelta(days=30)),
                    project_col=WorkItem.project_id,
                )
            )).scalar() or 0

            rework_q = scoped_query(
                select(func.count()).where(
                    wi.c.project_id == project_id,
                    wi.c.state.in_(("Active", "New", "In Progress")),
                    wi.c.resolved_at.isnot(None),
                ),
                project_col=WorkItem.project_id,
            )
            rework = (await db.execute(rework_q)).scalar() or 0

            return _kv_block({
                "defect_density": f"{density['defect_density_pct']}%",
                "total_bugs": density["bug_count"],
                "bugs_created_last_30d": recent_bugs,
                "median_bug_resolution_h": res["median_hours"],
                "p90_bug_resolution_h": res["p90_hours"],
                "rework_items": rework,
            }, "Quality Summary")
        return await _safe(db, _impl())

    @tool
    async def get_bug_trend_data(project_name: Optional[str] = None, days: int = 90) -> str:
        """Daily bugs created vs resolved over time."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."
            data = await get_bug_trend(db, project_id, days=days)
            if not data:
                return "No bug trend data available."
            total_created = sum(d["created"] for d in data)
            total_resolved = sum(d["resolved"] for d in data)
            net = total_created - total_resolved
            return _kv_block({
                "period": f"Last {days} days ({len(data)} data points)",
                "bugs_created": total_created,
                "bugs_resolved": total_resolved,
                "net_open": f"{'+' if net > 0 else ''}{net}",
            }, "Bug Trend")
        return await _safe(db, _impl())

    # ================================================================
    # H. Code-Delivery Intersection
    # ================================================================

    @tool
    async def get_code_delivery_intersection(project_name: Optional[str] = None) -> str:
        """Link coverage %, commits per story point, first-commit-to-resolution time."""
        async def _impl():
            project_id = None
            if project_name:
                p = await _resolve_project(db, project_name)
                if not p:
                    return f"Project '{project_name}' not found."
                project_id = p.id
            else:
                first = (await db.execute(select(Project).limit(1))).scalar_one_or_none()
                if first:
                    project_id = first.id
                else:
                    return "No projects found."
            data = await get_intersection_metrics(db, project_id)
            return _kv_block({
                "work_items_with_linked_commits": data["total_linked_items"],
                "total_work_items": data["total_items"],
                "link_coverage": f"{data['link_coverage_pct']}%",
                "commits_per_story_point": data["commits_per_story_point"],
                "avg_first_commit_to_resolution_h": data["avg_first_commit_to_resolution_hours"],
            }, "Code-Delivery Intersection")
        return await _safe(db, _impl())

    @tool
    async def get_work_item_linked_commits(work_item_id_or_title: str, project_name: Optional[str] = None) -> str:
        """Commits linked to a specific work item."""
        async def _impl():
            stmt = select(WorkItem)
            cleaned = work_item_id_or_title.lstrip("#")
            if cleaned.isdigit():
                stmt = stmt.where(WorkItem.platform_work_item_id == int(cleaned))
            else:
                stmt = stmt.where(WorkItem.title.ilike(f"%{work_item_id_or_title}%"))
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    stmt = stmt.where(WorkItem.project_id == p.id)
            stmt = scoped_query(stmt.limit(1), project_col=WorkItem.project_id)
            wi_obj = (await db.execute(stmt)).scalar_one_or_none()
            if not wi_obj:
                return f"Work item '{work_item_id_or_title}' not found."

            wic = WorkItemCommit.__table__
            cm = Commit.__table__
            ct = Contributor.__table__
            q = scoped_query(
                select(cm.c.sha, cm.c.message, ct.c.canonical_name, cm.c.authored_at, wic.c.link_type)
                .select_from(
                    wic.join(cm, wic.c.commit_id == cm.c.id)
                    .join(WorkItem, WorkItem.id == wic.c.work_item_id)
                    .outerjoin(ct, cm.c.contributor_id == ct.c.id)
                )
                .where(wic.c.work_item_id == wi_obj.id)
                .order_by(cm.c.authored_at.desc())
                .limit(25),
                project_col=WorkItem.project_id,
            )
            rows_data = (await db.execute(q)).all()
            if not rows_data:
                return f"No commits linked to #{wi_obj.platform_work_item_id} — {wi_obj.title}"
            rows = [(r[0][:8], (r[1] or "")[:50], r[2] or "—", str(r[3])[:10] if r[3] else "—", r[4]) for r in rows_data]
            return f"**Commits for #{wi_obj.platform_work_item_id}: {wi_obj.title[:50]}**\n" + _table(
                ["SHA", "Message", "Author", "Date", "Link Type"], rows
            )
        return await _safe(db, _impl())

    # ================================================================
    # I. Work Item Description Editing
    # ================================================================

    @tool
    async def read_work_item_description(work_item_id: str, project_name: Optional[str] = None) -> str:
        """Return the full HTML description and metadata of a work item.

        Args:
            work_item_id: Platform work item ID (#12345) or title substring.
            project_name: Optional project name to narrow the search.
        """
        async def _impl():
            stmt = select(WorkItem)
            cleaned = work_item_id.lstrip("#")
            if cleaned.isdigit():
                stmt = stmt.where(WorkItem.platform_work_item_id == int(cleaned))
            else:
                stmt = stmt.where(WorkItem.title.ilike(f"%{work_item_id}%"))
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    stmt = stmt.where(WorkItem.project_id == p.id)
            stmt = scoped_query(stmt.limit(1), project_col=WorkItem.project_id)
            wi = (await db.execute(stmt)).scalar_one_or_none()
            if not wi:
                return f"Work item not found: {work_item_id}"
            desc = wi.description or "(no description)"
            draft_note = ""
            if wi.draft_description:
                draft_note = f"\n\n**Draft proposal currently pending review.**\nDraft:\n{wi.draft_description}"
            return (
                f"**#{wi.platform_work_item_id}: {wi.title}**\n"
                f"Type: {wi.work_item_type.value if hasattr(wi.work_item_type, 'value') else wi.work_item_type} | "
                f"State: {wi.state}\n\n"
                f"## Current Description\n{desc}{draft_note}"
            )
        return await _safe(db, _impl())

    @tool
    async def propose_work_item_description(work_item_id: str, proposed_html: str) -> str:
        """Write an agent-generated HTML description as a draft for user review.

        The draft is stored on the work item and displayed side-by-side with the
        original in the UI. The user decides whether to accept or discard.

        Args:
            work_item_id: Platform work item ID (#12345).
            proposed_html: The full proposed description as valid HTML.
        """
        from app.db.base import async_session as _session_factory

        async with _session_factory() as s:
            cleaned = work_item_id.lstrip("#")
            if not cleaned.isdigit():
                return f"work_item_id must be a numeric platform ID, got: {work_item_id}"
            stmt = select(WorkItem).where(
                WorkItem.platform_work_item_id == int(cleaned)
            ).limit(1)
            stmt = scoped_query(stmt, project_col=WorkItem.project_id)
            wi = (await s.execute(stmt)).scalar_one_or_none()
            if not wi:
                return f"Work item #{cleaned} not found."
            wi.draft_description = proposed_html
            await s.commit()
            return (
                f"Draft description proposed for #{wi.platform_work_item_id}: {wi.title}. "
                f"The user can now see it side-by-side with the original and choose to accept or discard."
            )

    # ================================================================
    # Return all tools
    # ================================================================

    return [
        find_work_item, find_iteration, find_team,
        get_sprint_overview, get_sprint_comparison, get_sprint_burndown,
        get_active_sprints, get_sprint_scope_change, get_sprint_carryover,
        get_iteration_carryover_matrix, get_team_carryover_summary,
        get_work_item_iteration_history,
        get_iteration_detail,
        get_velocity_trend, get_delivery_throughput_trend,
        get_velocity_forecast, get_team_velocity_comparison,
        get_cycle_time_stats, get_lead_time_stats,
        get_wip_analysis, get_delivery_cumulative_flow,
        get_cycle_time_histogram, get_wip_snapshot,
        get_backlog_overview, get_stale_items,
        get_backlog_composition, get_backlog_growth_trend,
        get_stale_backlog_summary, get_backlog_age_histogram,
        get_feature_backlog_rollup, get_story_sizing_trend,
        get_trusted_backlog_scorecard, get_long_running_stories,
        get_team_delivery_overview, get_team_workload, get_team_members_delivery,
        get_team_capacity_vs_load,
        get_bug_metrics, get_quality_summary, get_bug_trend_data,
        get_code_delivery_intersection, get_work_item_linked_commits,
        read_work_item_description, propose_work_item_description,
    ]


register_tool_category(CATEGORY, DEFINITIONS, _build_delivery_tools, concurrency_safe=True)
