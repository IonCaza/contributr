from __future__ import annotations

import logging
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
)
from app.agents.tools.base import ToolDefinition
from app.agents.tools.registry import register_tool_category

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
    # F. Team Analytics
    ToolDefinition("get_team_delivery_overview", "Team Overview", "Team stats: members, velocity, active items, throughput, cycle time", CATEGORY),
    ToolDefinition("get_team_workload", "Team Workload", "Work distribution across team members — identifies imbalances", CATEGORY),
    ToolDefinition("get_team_members_delivery", "Team Members Delivery", "Per-member delivery stats: items completed, points, cycle time, bugs resolved", CATEGORY),
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
    result = await db.execute(stmt.order_by(Iteration.start_date.desc()).limit(1))
    return result.scalar_one_or_none()


async def _resolve_team(db: AsyncSession, name: str, project_id=None) -> Team | None:
    stmt = select(Team).where(Team.name.ilike(f"%{name}%"))
    if project_id:
        stmt = stmt.where(Team.project_id == project_id)
    result = await db.execute(stmt.order_by(Team.name).limit(1))
    return result.scalar_one_or_none()


async def _team_contributor_ids(db: AsyncSession, team_id) -> set:
    result = await db.execute(
        select(TeamMember.contributor_id).where(TeamMember.team_id == team_id)
    )
    return set(result.scalars().all())


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
            result = await db.execute(stmt.limit(5))
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
            result = await db.execute(stmt.order_by(Iteration.start_date.desc()).limit(5))
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
            result = await db.execute(stmt.order_by(Team.name).limit(5))
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
            total = (await db.execute(select(func.count()).where(base))).scalar() or 0
            completed = (await db.execute(select(func.count()).where(base, wi.c.resolved_at.isnot(None)))).scalar() or 0
            total_sp = float((await db.execute(select(func.coalesce(func.sum(wi.c.story_points), 0)).where(base))).scalar() or 0)
            completed_sp = float((await db.execute(select(func.coalesce(func.sum(wi.c.story_points), 0)).where(base, wi.c.resolved_at.isnot(None)))).scalar() or 0)
            contrib_count = (await db.execute(select(func.count(func.distinct(wi.c.assigned_to_id))).where(base, wi.c.assigned_to_id.isnot(None)))).scalar() or 0
            pct = round(completed / total * 100, 1) if total > 0 else 0
            pct_sp = round(completed_sp / total_sp * 100, 1) if total_sp > 0 else 0

            ct = Contributor.__table__
            top_q = (
                select(ct.c.canonical_name, func.coalesce(func.sum(wi.c.story_points), 0).label("pts"))
                .select_from(wi.join(ct, wi.c.assigned_to_id == ct.c.id))
                .where(base, wi.c.resolved_at.isnot(None))
                .group_by(ct.c.canonical_name)
                .order_by(func.sum(wi.c.story_points).desc())
                .limit(5)
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

            async def _stats(iter_id):
                base = wi.c.iteration_id == iter_id
                total = (await db.execute(select(func.count()).where(base))).scalar() or 0
                completed = (await db.execute(select(func.count()).where(base, wi.c.resolved_at.isnot(None)))).scalar() or 0
                sp = float((await db.execute(select(func.coalesce(func.sum(wi.c.story_points), 0)).where(base, wi.c.resolved_at.isnot(None)))).scalar() or 0)
                contribs = (await db.execute(select(func.count(func.distinct(wi.c.assigned_to_id))).where(base, wi.c.assigned_to_id.isnot(None)))).scalar() or 0
                cycle_q = select(
                    func.percentile_cont(0.5).within_group(extract("epoch", wi.c.resolved_at - wi.c.activated_at) / 3600)
                ).where(base, wi.c.activated_at.isnot(None), wi.c.resolved_at.isnot(None))
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
        """Currently active and next 3 upcoming sprints with progress stats."""
        async def _impl():
            now = datetime.now(timezone.utc).date()
            stmt = select(Iteration)
            if project_name:
                p = await _resolve_project(db, project_name)
                if p:
                    stmt = stmt.where(Iteration.project_id == p.id)
            stmt = stmt.where(Iteration.end_date >= now).order_by(Iteration.start_date)
            result = await db.execute(stmt.limit(10))
            iters = result.scalars().all()
            if not iters:
                return "No active or upcoming sprints found."
            wi = WorkItem.__table__
            rows = []
            for it in iters:
                status = "upcoming"
                if it.start_date and it.start_date <= now:
                    status = "active"
                total = (await db.execute(select(func.count()).where(wi.c.iteration_id == it.id))).scalar() or 0
                completed = (await db.execute(select(func.count()).where(wi.c.iteration_id == it.id, wi.c.resolved_at.isnot(None)))).scalar() or 0
                sp = float((await db.execute(select(func.coalesce(func.sum(wi.c.story_points), 0)).where(wi.c.iteration_id == it.id))).scalar() or 0)
                pct = round(completed / total * 100) if total else 0
                rows.append((it.name, status, str(it.start_date), str(it.end_date), total, completed, f"{pct}%", round(sp, 1)))
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
            total = (await db.execute(select(func.count()).where(base))).scalar() or 0
            added_after_start = (await db.execute(
                select(func.count()).where(base, func.date(wi.c.created_at) > it.start_date)
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
        """Incomplete items from a sprint and their current state."""
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
            q = (
                select(
                    wi.c.platform_work_item_id, wi.c.title, wi.c.state,
                    wi.c.story_points, ct.c.canonical_name,
                )
                .select_from(wi.outerjoin(ct, wi.c.assigned_to_id == ct.c.id))
                .where(wi.c.iteration_id == it.id, wi.c.state.notin_(_COMPLETED_STATES))
                .order_by(wi.c.priority.asc().nullslast())
                .limit(30)
            )
            rows_data = (await db.execute(q)).all()
            if not rows_data:
                return f"No incomplete items in sprint '{it.name}' — all items were completed."
            rows = [(f"#{r[0]}", r[1][:50], r[2], _fmt(r[3]), r[4] or "Unassigned") for r in rows_data]
            return f"**Carryover from {it.name}** ({len(rows_data)} items)\n" + _table(
                ["ID", "Title", "State", "Points", "Assignee"], rows
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
            remaining_q = select(func.coalesce(func.sum(wi.c.story_points), 0)).where(
                wi.c.project_id == project_id, wi.c.state.notin_(_COMPLETED_STATES),
            )
            remaining_sp = float((await db.execute(remaining_q)).scalar() or 0)
            remaining_items = (await db.execute(
                select(func.count()).where(wi.c.project_id == project_id, wi.c.state.notin_(_COMPLETED_STATES))
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

            teams_q = select(Team).where(Team.project_id == project_id).order_by(Team.name).limit(limit)
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
                q = (
                    select(it.c.name, func.coalesce(func.sum(wi.c.story_points), 0).label("pts"))
                    .select_from(wi.join(it, wi.c.iteration_id == it.c.id))
                    .where(
                        wi.c.project_id == project_id,
                        wi.c.assigned_to_id.in_(member_ids),
                        wi.c.resolved_at.isnot(None),
                    )
                    .group_by(it.c.name, it.c.start_date)
                    .order_by(it.c.start_date.desc())
                    .limit(3)
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
        """Median, p75, p90 cycle times (activated -> resolved) with type breakdown."""
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
            hours_expr = extract("epoch", wi.c.resolved_at - wi.c.activated_at) / 3600
            base = [wi.c.project_id == project_id, wi.c.activated_at.isnot(None), wi.c.resolved_at.isnot(None)]
            if work_item_type:
                base.append(wi.c.work_item_type == work_item_type)
            fd, td = _parse_date(from_date), _parse_date(to_date)
            if fd:
                base.append(wi.c.resolved_at >= fd)
            if td:
                base.append(wi.c.resolved_at <= td)

            q = select(
                func.percentile_cont(0.5).within_group(hours_expr).label("p50"),
                func.percentile_cont(0.75).within_group(hours_expr).label("p75"),
                func.percentile_cont(0.9).within_group(hours_expr).label("p90"),
                func.count().label("sample"),
            ).where(*base)
            row = (await db.execute(q)).one_or_none()

            type_q = (
                select(
                    wi.c.work_item_type,
                    func.percentile_cont(0.5).within_group(hours_expr).label("median"),
                    func.count().label("n"),
                )
                .where(*base)
                .group_by(wi.c.work_item_type)
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

            q = select(
                func.percentile_cont(0.5).within_group(hours_expr).label("p50"),
                func.percentile_cont(0.75).within_group(hours_expr).label("p75"),
                func.percentile_cont(0.9).within_group(hours_expr).label("p90"),
                func.count().label("sample"),
            ).where(*base)
            row = (await db.execute(q)).one_or_none()

            type_q = (
                select(wi.c.work_item_type, func.percentile_cont(0.5).within_group(hours_expr).label("median"), func.count().label("n"))
                .where(*base)
                .group_by(wi.c.work_item_type)
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

            total_wip = (await db.execute(select(func.count()).where(*base))).scalar() or 0
            by_state = (await db.execute(
                select(wi.c.state, func.count()).where(*base).group_by(wi.c.state).order_by(func.count().desc())
            )).all()
            by_type = (await db.execute(
                select(wi.c.work_item_type, func.count()).where(*base).group_by(wi.c.work_item_type).order_by(func.count().desc())
            )).all()
            by_assignee = (await db.execute(
                select(ct.c.canonical_name, func.count().label("c"))
                .select_from(wi.join(ct, wi.c.assigned_to_id == ct.c.id))
                .where(*base).group_by(ct.c.canonical_name).order_by(func.count().desc()).limit(10)
            )).all()
            unassigned = (await db.execute(
                select(func.count()).where(*base, wi.c.assigned_to_id.is_(None))
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
            total_open = (await db.execute(select(func.count()).where(*base))).scalar() or 0
            unestimated = (await db.execute(select(func.count()).where(*base, wi.c.story_points.is_(None)))).scalar() or 0
            unassigned = (await db.execute(select(func.count()).where(*base, wi.c.assigned_to_id.is_(None)))).scalar() or 0

            stale_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            stale = (await db.execute(select(func.count()).where(*base, wi.c.updated_at < stale_cutoff))).scalar() or 0

            by_priority = (await db.execute(
                select(wi.c.priority, func.count()).where(*base).group_by(wi.c.priority).order_by(wi.c.priority.asc().nullslast())
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
            q = (
                select(wi.c.platform_work_item_id, wi.c.title, wi.c.state, wi.c.work_item_type, wi.c.updated_at, ct.c.canonical_name)
                .select_from(wi.outerjoin(ct, wi.c.assigned_to_id == ct.c.id))
                .where(wi.c.project_id == project_id, wi.c.state.notin_(_COMPLETED_STATES), wi.c.updated_at < cutoff)
                .order_by(wi.c.updated_at.asc())
                .limit(limit)
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
            by_type = (await db.execute(select(wi.c.work_item_type, func.count()).where(*base).group_by(wi.c.work_item_type).order_by(func.count().desc()))).all()
            by_state = (await db.execute(select(wi.c.state, func.count()).where(*base).group_by(wi.c.state).order_by(func.count().desc()))).all()
            by_priority = (await db.execute(select(wi.c.priority, func.count()).where(*base).group_by(wi.c.priority).order_by(wi.c.priority.asc().nullslast()))).all()

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

            active = (await db.execute(select(func.count()).where(*base, wi.c.state.notin_(_COMPLETED_STATES)))).scalar() or 0
            completed_30d = (await db.execute(
                select(func.count()).where(*base, wi.c.resolved_at.isnot(None), wi.c.resolved_at >= datetime.now(timezone.utc) - timedelta(days=30))
            )).scalar() or 0

            velocity_q = (
                select(func.coalesce(func.sum(wi.c.story_points), 0).label("pts"))
                .select_from(wi.join(it, wi.c.iteration_id == it.c.id))
                .where(*base, wi.c.resolved_at.isnot(None))
                .group_by(it.c.id, it.c.start_date)
                .order_by(it.c.start_date.desc())
                .limit(3)
            )
            vel_rows = (await db.execute(velocity_q)).all()
            pts = [float(r.pts) for r in vel_rows]
            avg_vel = round(sum(pts) / len(pts), 1) if pts else 0

            cycle_q = select(
                func.percentile_cont(0.5).within_group(extract("epoch", wi.c.resolved_at - wi.c.activated_at) / 3600)
            ).where(*base, wi.c.activated_at.isnot(None), wi.c.resolved_at.isnot(None))
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
            q = (
                select(
                    ct.c.canonical_name,
                    func.count().filter(wi.c.state.notin_(_COMPLETED_STATES)).label("active"),
                    func.count().filter(wi.c.resolved_at.isnot(None)).label("completed"),
                    func.coalesce(func.sum(wi.c.story_points).filter(wi.c.resolved_at.isnot(None)), 0).label("pts"),
                )
                .select_from(wi.join(ct, wi.c.assigned_to_id == ct.c.id))
                .where(wi.c.project_id == t.project_id, wi.c.assigned_to_id.in_(member_ids))
                .group_by(ct.c.canonical_name)
                .order_by(func.count().filter(wi.c.state.notin_(_COMPLETED_STATES)).desc())
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
            q = (
                select(
                    ct.c.canonical_name,
                    func.count().filter(wi.c.resolved_at.isnot(None)).label("completed"),
                    func.coalesce(func.sum(wi.c.story_points).filter(wi.c.resolved_at.isnot(None)), 0).label("pts"),
                    func.percentile_cont(0.5).within_group(
                        extract("epoch", wi.c.resolved_at - wi.c.activated_at) / 3600
                    ).filter(wi.c.activated_at.isnot(None), wi.c.resolved_at.isnot(None)).label("med_ct"),
                    func.count().filter(wi.c.work_item_type == "bug", wi.c.resolved_at.isnot(None)).label("bugs"),
                )
                .select_from(wi.join(ct, wi.c.assigned_to_id == ct.c.id))
                .where(wi.c.project_id == t.project_id, wi.c.assigned_to_id.in_(member_ids))
                .group_by(ct.c.canonical_name)
                .order_by(func.coalesce(func.sum(wi.c.story_points).filter(wi.c.resolved_at.isnot(None)), 0).desc())
            )
            rows_data = (await db.execute(q)).all()
            if not rows_data:
                return "No delivery data for this team."
            rows = [(r[0], r.completed, round(float(r.pts), 1), round(r.med_ct or 0, 1), r.bugs) for r in rows_data]
            return f"**Team Members: {t.name}**\n" + _table(["Member", "Completed", "Points", "Median CT (h)", "Bugs Resolved"], rows)
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
            open_bugs = (await db.execute(select(func.count()).where(*base, wi.c.state.notin_(_COMPLETED_STATES)))).scalar() or 0
            total_bugs = (await db.execute(select(func.count()).where(*base))).scalar() or 0

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
                select(func.count()).where(*base, wi.c.created_at >= datetime.now(timezone.utc) - timedelta(days=30))
            )).scalar() or 0

            rework_q = select(func.count()).where(
                wi.c.project_id == project_id,
                wi.c.state.in_(("Active", "New", "In Progress")),
                wi.c.resolved_at.isnot(None),
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
            wi_obj = (await db.execute(stmt.limit(1))).scalar_one_or_none()
            if not wi_obj:
                return f"Work item '{work_item_id_or_title}' not found."

            wic = WorkItemCommit.__table__
            cm = Commit.__table__
            ct = Contributor.__table__
            q = (
                select(cm.c.sha, cm.c.message, ct.c.canonical_name, cm.c.authored_at, wic.c.link_type)
                .select_from(wic.join(cm, wic.c.commit_id == cm.c.id).outerjoin(ct, cm.c.contributor_id == ct.c.id))
                .where(wic.c.work_item_id == wi_obj.id)
                .order_by(cm.c.authored_at.desc())
                .limit(25)
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
            wi = (await db.execute(stmt.limit(1))).scalar_one_or_none()
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
        get_iteration_detail,
        get_velocity_trend, get_delivery_throughput_trend,
        get_velocity_forecast, get_team_velocity_comparison,
        get_cycle_time_stats, get_lead_time_stats,
        get_wip_analysis, get_delivery_cumulative_flow,
        get_cycle_time_histogram, get_wip_snapshot,
        get_backlog_overview, get_stale_items,
        get_backlog_composition, get_backlog_growth_trend,
        get_stale_backlog_summary, get_backlog_age_histogram,
        get_team_delivery_overview, get_team_workload, get_team_members_delivery,
        get_bug_metrics, get_quality_summary, get_bug_trend_data,
        get_code_delivery_intersection, get_work_item_linked_commits,
        read_work_item_description, propose_work_item_description,
    ]


register_tool_category(CATEGORY, DEFINITIONS, _build_delivery_tools)
