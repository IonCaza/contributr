from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from langchain_core.tools import tool
from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.models import (
    Project, Repository, Contributor, Commit, PullRequest,
    Review, DailyContributorStats, CommitFile, Branch, SyncJob,
)
from app.db.models.branch import commit_branches
from app.db.models.project import project_contributors
from app.db.models.pull_request import PRState
from app.db.models.review import ReviewState
from app.services.metrics import get_trends, get_bus_factor, get_top_contributors
from app.agents.tools.base import ToolDefinition
from app.agents.tools.registry import register_tool_category
from app.agents.tools.scoping import scoped_query

logger = logging.getLogger(__name__)

CATEGORY = "contribution_analytics"

DEFINITIONS = [
    ToolDefinition("find_project", "Find Project", "Search for a project by name", CATEGORY),
    ToolDefinition("find_contributor", "Find Contributor", "Search for a contributor by name or email", CATEGORY),
    ToolDefinition("find_repository", "Find Repository", "Search for a repository by name", CATEGORY),
    ToolDefinition("get_project_overview", "Project Overview", "Comprehensive project stats including commits, churn, PR cycle time", CATEGORY),
    ToolDefinition("get_top_contributors", "Top Contributors", "Top contributors ranked by metric", CATEGORY),
    ToolDefinition("get_contributor_profile", "Contributor Profile", "Detailed contributor profile with streak, impact, trends", CATEGORY),
    ToolDefinition("get_repository_overview", "Repository Overview", "Repo stats including bus factor, churn, trends", CATEGORY),
    ToolDefinition("get_pr_activity", "PR Activity", "Pull request activity with cycle and review times", CATEGORY),
    ToolDefinition("get_contribution_trends", "Contribution Trends", "7d/30d averages and week-over-week deltas", CATEGORY),
    ToolDefinition("get_code_hotspots", "Code Hotspots", "Most frequently changed files in a repository", CATEGORY),
    ToolDefinition("get_pr_review_cycle", "PR Review Cycle", "Median/p90 cycle time, first-review time, iterations, approval rate", CATEGORY),
    ToolDefinition("get_reviewer_leaderboard", "Reviewer Leaderboard", "Top reviewers by volume, turnaround, and thoroughness", CATEGORY),
    ToolDefinition("get_review_network", "Review Network", "Who reviews whose code — author-reviewer pairs", CATEGORY),
    ToolDefinition("get_pr_size_analysis", "PR Size Analysis", "PR size distribution and impact on review speed", CATEGORY),
    ToolDefinition("get_contributor_pr_summary", "Contributor PR Summary", "Detailed PR authoring and review stats per contributor", CATEGORY),
    ToolDefinition("get_file_ownership", "File Ownership", "Primary code owners of top files in a repository", CATEGORY),
    ToolDefinition("get_contributor_file_focus", "Contributor File Focus", "Which directories a contributor touches most", CATEGORY),
    ToolDefinition("get_file_collaboration", "File Collaboration", "Contributors who co-edit the same files", CATEGORY),
    ToolDefinition("compare_contributors", "Compare Contributors", "Side-by-side comparison of 2-5 contributors", CATEGORY),
    ToolDefinition("get_work_patterns", "Work Patterns", "Day-of-week and hour-of-day commit distribution", CATEGORY),
    ToolDefinition("get_contributor_cross_repo", "Contributor Cross-Repo", "Which repos a contributor works on", CATEGORY),
    ToolDefinition("get_inactive_contributors", "Inactive Contributors", "Previously active contributors who have gone quiet", CATEGORY),
    ToolDefinition("list_pull_requests", "List Pull Requests", "Search and filter pull requests across project repositories", CATEGORY),
    ToolDefinition("get_branch_summary", "Branch Summary", "Active branches with recent commit activity", CATEGORY),
    ToolDefinition("get_branch_comparison", "Branch Comparison", "Compare two branches by commits and contributors", CATEGORY),
    ToolDefinition("get_data_freshness", "Data Freshness", "How current the synced data is for a project or repo", CATEGORY),
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


# ── Name resolution ───────────────────────────────────────────────────


async def _resolve_project(db: AsyncSession, name: str) -> Project | None:
    result = await db.execute(
        select(Project).where(Project.name.ilike(f"%{name}%")).order_by(Project.name).limit(1)
    )
    return result.scalar_one_or_none()


async def _resolve_contributor(db: AsyncSession, name_or_email: str) -> Contributor | None:
    result = await db.execute(
        scoped_query(
            select(Contributor).where(
                Contributor.canonical_name.ilike(f"%{name_or_email}%")
                | Contributor.canonical_email.ilike(f"%{name_or_email}%")
            ).order_by(Contributor.canonical_name).limit(1),
            contributor_col=Contributor.id,
        )
    )
    return result.scalar_one_or_none()


async def _resolve_repository(
    db: AsyncSession, name: str, project_name: str | None = None,
) -> Repository | None:
    stmt = select(Repository).where(Repository.name.ilike(f"%{name}%"))
    if project_name:
        project = await _resolve_project(db, project_name)
        if project:
            stmt = stmt.where(Repository.project_id == project.id)
    stmt = scoped_query(stmt, project_col=Repository.project_id)
    result = await db.execute(stmt.order_by(Repository.name).limit(1))
    return result.scalar_one_or_none()


def _parse_date(val: str | None) -> date | None:
    if not val:
        return None
    return date.fromisoformat(val)


async def _safe(db: AsyncSession, coro):
    """Run a coroutine inside a SAVEPOINT so failures don't poison the session."""
    try:
        async with db.begin_nested():
            return await coro
    except Exception as e:
        logger.warning("Tool query failed: %s", e)
        return f"Error: {e}"


def _compute_gini(values: list[int]) -> float:
    if not values or sum(values) == 0:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    cumulative = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(sorted_vals))
    return round(cumulative / (n * sum(sorted_vals)), 2)


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = f + 1
    if c >= len(sorted_vals):
        return sorted_vals[f]
    return sorted_vals[f] + (k - f) * (sorted_vals[c] - sorted_vals[f])


# ── Tool factory ──────────────────────────────────────────────────────


def _build_contribution_tools(db: AsyncSession) -> list:
    """Build all contribution analytics LangChain tools."""

    @tool
    async def find_project(name: str) -> str:
        """Search for a project by name. Returns matching projects with their
        repository and contributor counts.
        Use this tool first when the user mentions a project by name.

        Args:
            name: Project name or partial name to search for (case-insensitive).
        """
        async def _impl():
            repo_count = func.count(Repository.id).label("repo_count")
            contrib_count = (
                select(func.count(project_contributors.c.contributor_id))
                .where(project_contributors.c.project_id == Project.id)
                .correlate(Project)
                .scalar_subquery()
                .label("contributor_count")
            )
            stmt = scoped_query(
                select(Project.name, Project.description, repo_count, contrib_count)
                .outerjoin(Repository, Repository.project_id == Project.id)
                .where(Project.name.ilike(f"%{name}%"))
                .group_by(Project.id)
                .order_by(Project.name)
                .limit(10),
                project_col=Repository.project_id,
            )
            result = await db.execute(stmt)
            rows = result.all()
            if not rows:
                all_projects = await db.execute(
                    select(Project.name).order_by(Project.name).limit(20)
                )
                names = [r.name for r in all_projects.all()]
                return (
                    f"No project found matching '{name}'. "
                    f"Available projects: {', '.join(names)}"
                )
            return _table(
                ["Project", "Description", "Repositories", "Contributors"],
                [
                    (r.name, r.description or "—", r.repo_count, r.contributor_count)
                    for r in rows
                ],
            )
        return await _safe(db, _impl())

    @tool
    async def find_contributor(name_or_email: str) -> str:
        """Search for a contributor by name or email address.
        Use this tool when you need to identify a specific contributor.

        Args:
            name_or_email: Name or email (partial match, case-insensitive).
        """
        async def _impl():
            stmt = scoped_query(
                select(
                    Contributor.canonical_name,
                    Contributor.canonical_email,
                    Contributor.github_username,
                )
                .where(
                    Contributor.canonical_name.ilike(f"%{name_or_email}%")
                    | Contributor.canonical_email.ilike(f"%{name_or_email}%")
                )
                .order_by(Contributor.canonical_name)
                .limit(10),
                contributor_col=Contributor.id,
            )
            result = await db.execute(stmt)
            rows = result.all()
            if not rows:
                return f"No contributor found matching '{name_or_email}'."
            return _table(
                ["Name", "Email", "GitHub"],
                [
                    (r.canonical_name, r.canonical_email, r.github_username or "—")
                    for r in rows
                ],
            )
        return await _safe(db, _impl())

    @tool
    async def find_repository(
        name: str,
        project_name: Optional[str] = None,
    ) -> str:
        """Search for a repository by name, optionally within a specific project.

        Args:
            name: Repository name or partial name (case-insensitive).
            project_name: Optional project name to scope the search.
        """
        async def _impl():
            stmt = (
                select(
                    Repository.name,
                    Project.name.label("project"),
                    Repository.platform,
                    Repository.default_branch,
                    Repository.last_synced_at,
                )
                .join(Project, Project.id == Repository.project_id)
                .where(Repository.name.ilike(f"%{name}%"))
            )
            if project_name:
                stmt = stmt.where(Project.name.ilike(f"%{project_name}%"))
            stmt = scoped_query(stmt, project_col=Repository.project_id)
            stmt = stmt.order_by(Repository.name).limit(10)
            result = await db.execute(stmt)
            rows = result.all()
            if not rows:
                return f"No repository found matching '{name}'."
            return _table(
                ["Repository", "Project", "Platform", "Default Branch", "Last Synced"],
                [
                    (
                        r.name, r.project, r.platform, r.default_branch,
                        str(r.last_synced_at)[:10] if r.last_synced_at else "Never",
                    )
                    for r in rows
                ],
            )
        return await _safe(db, _impl())

    @tool
    async def get_project_overview(
        project_name: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> str:
        """Get a comprehensive overview of a project including commit stats,
        contributor count, PR cycle time, code churn, and contribution distribution.

        Args:
            project_name: Name of the project.
            from_date: Optional start date (YYYY-MM-DD).
            to_date: Optional end date (YYYY-MM-DD).
        """
        async def _impl():
            project = await _resolve_project(db, project_name)
            if not project:
                return f"No project found matching '{project_name}'."

            fd, td = _parse_date(from_date), _parse_date(to_date)

            repo_count = await db.scalar(
                scoped_query(
                    select(func.count()).select_from(Repository)
                    .where(Repository.project_id == project.id),
                    project_col=Repository.project_id,
                )
            )

            commit_q = scoped_query(
                select(Commit)
                .join(Repository)
                .where(Repository.project_id == project.id),
                project_col=Repository.project_id,
                contributor_col=Commit.contributor_id,
            )
            if fd:
                commit_q = commit_q.where(Commit.authored_at >= fd)
            if td:
                commit_q = commit_q.where(Commit.authored_at <= td + timedelta(days=1))
            sub = commit_q.with_only_columns(Commit.id).subquery()

            total_commits = await db.scalar(select(func.count()).select_from(sub))
            contributor_count = await db.scalar(
                scoped_query(
                    select(func.count(Commit.contributor_id.distinct()))
                    .join(Repository, Repository.id == Commit.repository_id)
                    .where(Commit.id.in_(select(sub.c.id))),
                    project_col=Repository.project_id,
                    contributor_col=Commit.contributor_id,
                )
            )

            agg = (await db.execute(
                scoped_query(
                    select(
                        func.coalesce(func.sum(Commit.lines_added), 0).label("la"),
                        func.coalesce(func.sum(Commit.lines_deleted), 0).label("ld"),
                    )
                    .join(Repository, Repository.id == Commit.repository_id)
                    .where(Commit.id.in_(select(sub.c.id))),
                    project_col=Repository.project_id,
                    contributor_col=Commit.contributor_id,
                )
            )).one()
            churn = round(agg.ld / agg.la, 2) if agg.la > 0 else 0

            repo_ids = (
                scoped_query(
                    select(Repository.id)
                    .where(Repository.project_id == project.id),
                    project_col=Repository.project_id,
                )
                .subquery()
            )
            pr_cycle = await db.scalar(
                scoped_query(
                    select(
                        func.avg(func.extract("epoch", PullRequest.merged_at - PullRequest.created_at) / 3600)
                    )
                    .join(Repository, Repository.id == PullRequest.repository_id)
                    .where(
                        PullRequest.repository_id.in_(select(repo_ids.c.id)),
                        PullRequest.state == PRState.MERGED,
                        PullRequest.merged_at.isnot(None),
                    ),
                    project_col=Repository.project_id,
                    contributor_col=PullRequest.contributor_id,
                )
            )

            first_review = (
                scoped_query(
                    select(
                        Review.pull_request_id,
                        func.min(Review.submitted_at).label("fr"),
                    )
                    .join(PullRequest, PullRequest.id == Review.pull_request_id)
                    .join(Repository, Repository.id == PullRequest.repository_id)
                    .group_by(Review.pull_request_id),
                    project_col=Repository.project_id,
                    contributor_col=Review.reviewer_id,
                )
                .subquery()
            )
            review_ta = await db.scalar(
                scoped_query(
                    select(
                        func.avg(func.extract("epoch", first_review.c.fr - PullRequest.created_at) / 3600)
                    )
                    .join(first_review, first_review.c.pull_request_id == PullRequest.id)
                    .join(Repository, Repository.id == PullRequest.repository_id)
                    .where(PullRequest.repository_id.in_(select(repo_ids.c.id))),
                    project_col=Repository.project_id,
                    contributor_col=PullRequest.contributor_id,
                )
            )

            contrib_counts = (await db.execute(
                scoped_query(
                    select(Commit.contributor_id, func.count().label("cnt"))
                    .join(Repository, Repository.id == Commit.repository_id)
                    .where(Commit.id.in_(select(sub.c.id)))
                    .group_by(Commit.contributor_id),
                    project_col=Repository.project_id,
                    contributor_col=Commit.contributor_id,
                )
            )).all()
            gini = _compute_gini([r.cnt for r in contrib_counts])

            trends = await get_trends(db, project_id=project.id)

            return _kv_block({
                "project": project.name,
                "description": project.description or "—",
                "repositories": repo_count,
                "total_commits": total_commits,
                "active_contributors": contributor_count,
                "lines_added": agg.la,
                "lines_deleted": agg.ld,
                "churn_ratio": churn,
                "avg_pr_cycle_time": f"{round(pr_cycle or 0, 1)} hours",
                "avg_review_turnaround": f"{round(review_ta or 0, 1)} hours",
                "contribution_gini": gini,
                "avg_commits_per_day_7d": trends["avg_commits_7d"],
                "avg_commits_per_day_30d": trends["avg_commits_30d"],
                "week_over_week_commit_change": f"{trends['wow_commits_delta']}%",
            }, f"Project Overview: {project.name}")

        return await _safe(db, _impl())

    @tool
    async def get_top_contributors_tool(
        project_name: str,
        metric: str = "commits",
        limit: int = 10,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> str:
        """Get the top contributors to a project ranked by a metric.

        Args:
            project_name: Name of the project.
            metric: Metric to rank by: commits, lines_added, lines_deleted,
                    prs_opened, prs_merged, reviews_given. Default: commits.
            limit: Number of top contributors to return (default 10, max 50).
            from_date: Optional start date (YYYY-MM-DD).
            to_date: Optional end date (YYYY-MM-DD).
        """
        async def _impl():
            project = await _resolve_project(db, project_name)
            if not project:
                return f"No project found matching '{project_name}'."

            rows = await get_top_contributors(
                db,
                project_id=project.id,
                metric=metric,
                from_date=_parse_date(from_date),
                to_date=_parse_date(to_date),
                limit=min(limit, 50),
            )
            if not rows:
                return f"No contribution data found for project '{project.name}'."

            return _table(
                ["Rank", "Name", "Email", "Commits", "Lines Added",
                 "Lines Deleted", "PRs Opened", "Reviews"],
                [
                    (
                        i, r["canonical_name"], r["canonical_email"],
                        r["commits"], r["lines_added"], r["lines_deleted"],
                        r["prs_opened"], r["reviews_given"],
                    )
                    for i, r in enumerate(rows, 1)
                ],
            )

        return await _safe(db, _impl())

    @tool
    async def get_contributor_profile(
        contributor_name: str,
        project_name: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> str:
        """Get a detailed profile of a contributor including commit stats, streak,
        impact score, PR activity, review engagement, and trends.

        Args:
            contributor_name: Name or email of the contributor.
            project_name: Optional project name to scope stats.
            from_date: Optional start date (YYYY-MM-DD).
            to_date: Optional end date (YYYY-MM-DD).
        """
        async def _impl():
            contributor = await _resolve_contributor(db, contributor_name)
            if not contributor:
                return f"No contributor found matching '{contributor_name}'."

            fd, td = _parse_date(from_date), _parse_date(to_date)

            commit_q = (
                select(Commit)
                .join(Repository, Repository.id == Commit.repository_id)
                .where(Commit.contributor_id == contributor.id)
            )
            commit_q = scoped_query(
                commit_q,
                project_col=Repository.project_id,
                contributor_col=Commit.contributor_id,
            )
            if fd:
                commit_q = commit_q.where(Commit.authored_at >= fd)
            if td:
                commit_q = commit_q.where(Commit.authored_at <= td + timedelta(days=1))
            if project_name:
                project = await _resolve_project(db, project_name)
                if project:
                    commit_q = commit_q.where(
                        Repository.project_id == project.id
                    )

            sub = commit_q.with_only_columns(Commit.id).subquery()
            total_commits = await db.scalar(select(func.count()).select_from(sub))

            agg = (await db.execute(
                scoped_query(
                    select(
                        func.coalesce(func.sum(Commit.lines_added), 0).label("la"),
                        func.coalesce(func.sum(Commit.lines_deleted), 0).label("ld"),
                        func.count(Commit.repository_id.distinct()).label("rc"),
                    )
                    .join(Repository, Repository.id == Commit.repository_id)
                    .where(Commit.id.in_(select(sub.c.id))),
                    project_col=Repository.project_id,
                    contributor_col=Commit.contributor_id,
                )
            )).one()

            day_col = func.date_trunc("day", Commit.authored_at).label("d")
            streak_q = scoped_query(
                select(day_col)
                .select_from(Commit)
                .join(Repository, Repository.id == Commit.repository_id)
                .where(Commit.contributor_id == contributor.id)
                .distinct()
                .order_by(day_col.desc()),
                project_col=Repository.project_id,
                contributor_col=Commit.contributor_id,
            )
            active_days_result = await db.execute(streak_q)
            active_dates = [
                r.d.date() if hasattr(r.d, "date") else r.d
                for r in active_days_result.all()
            ]
            streak = 0
            if active_dates:
                current = date.today()
                for d in active_dates:
                    if d == current or d == current - timedelta(days=1):
                        streak += 1
                        current = d - timedelta(days=1)
                    else:
                        break

            prs = await db.scalar(
                scoped_query(
                    select(func.count()).select_from(PullRequest)
                    .join(Repository, Repository.id == PullRequest.repository_id)
                    .where(PullRequest.contributor_id == contributor.id),
                    project_col=Repository.project_id,
                    contributor_col=PullRequest.contributor_id,
                )
            ) or 0
            reviews = await db.scalar(
                scoped_query(
                    select(func.count()).select_from(Review)
                    .join(PullRequest, PullRequest.id == Review.pull_request_id)
                    .join(Repository, Repository.id == PullRequest.repository_id)
                    .where(Review.reviewer_id == contributor.id),
                    project_col=Repository.project_id,
                    contributor_col=Review.reviewer_id,
                )
            ) or 0

            avg_size = round((agg.la + agg.ld) / total_commits, 1) if total_commits else 0
            velocity = agg.la - agg.ld
            engagement = round(reviews / prs, 2) if prs else 0
            impact = round(
                total_commits + (agg.la + agg.ld) * 0.1 + prs * 5 + reviews * 3, 1
            )

            trends = await get_trends(db, contributor_id=contributor.id)

            return _kv_block({
                "contributor": contributor.canonical_name,
                "email": contributor.canonical_email,
                "total_commits": total_commits,
                "lines_added": agg.la,
                "lines_deleted": agg.ld,
                "repositories": agg.rc,
                "current_streak_days": streak,
                "avg_commit_size": avg_size,
                "code_velocity": velocity,
                "prs_authored": prs,
                "reviews_given": reviews,
                "review_engagement": engagement,
                "impact_score": impact,
                "avg_commits_per_day_7d": trends["avg_commits_7d"],
                "avg_commits_per_day_30d": trends["avg_commits_30d"],
                "week_over_week_commit_change": f"{trends['wow_commits_delta']}%",
            }, f"Contributor Profile: {contributor.canonical_name}")

        return await _safe(db, _impl())

    @tool
    async def get_repository_overview(
        repo_name: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> str:
        """Get a comprehensive overview of a repository including commit stats,
        bus factor, code churn, PR metrics, and contribution distribution.

        Args:
            repo_name: Name of the repository.
            from_date: Optional start date (YYYY-MM-DD).
            to_date: Optional end date (YYYY-MM-DD).
        """
        async def _impl():
            repo = await _resolve_repository(db, repo_name)
            if not repo:
                return f"No repository found matching '{repo_name}'."

            fd, td = _parse_date(from_date), _parse_date(to_date)

            base_q = (
                select(Commit)
                .join(Repository, Repository.id == Commit.repository_id)
                .where(Commit.repository_id == repo.id)
            )
            base_q = scoped_query(
                base_q,
                project_col=Repository.project_id,
                contributor_col=Commit.contributor_id,
            )
            if fd:
                base_q = base_q.where(Commit.authored_at >= fd)
            if td:
                base_q = base_q.where(Commit.authored_at <= td + timedelta(days=1))
            sub = base_q.with_only_columns(Commit.id).subquery()

            total_commits = await db.scalar(select(func.count()).select_from(sub))
            contributor_count = await db.scalar(
                scoped_query(
                    select(func.count(Commit.contributor_id.distinct()))
                    .join(Repository, Repository.id == Commit.repository_id)
                    .where(Commit.id.in_(select(sub.c.id))),
                    project_col=Repository.project_id,
                    contributor_col=Commit.contributor_id,
                )
            )

            agg = (await db.execute(
                scoped_query(
                    select(
                        func.coalesce(func.sum(Commit.lines_added), 0).label("la"),
                        func.coalesce(func.sum(Commit.lines_deleted), 0).label("ld"),
                    )
                    .join(Repository, Repository.id == Commit.repository_id)
                    .where(Commit.id.in_(select(sub.c.id))),
                    project_col=Repository.project_id,
                    contributor_col=Commit.contributor_id,
                )
            )).one()
            churn = round(agg.ld / agg.la, 2) if agg.la > 0 else 0

            bus = await get_bus_factor(db, repo.id)
            trends = await get_trends(db, repository_id=repo.id)

            pr_cycle = await db.scalar(
                scoped_query(
                    select(
                        func.avg(func.extract("epoch", PullRequest.merged_at - PullRequest.created_at) / 3600)
                    )
                    .join(Repository, Repository.id == PullRequest.repository_id)
                    .where(
                        PullRequest.repository_id == repo.id,
                        PullRequest.state == PRState.MERGED,
                        PullRequest.merged_at.isnot(None),
                    ),
                    project_col=Repository.project_id,
                    contributor_col=PullRequest.contributor_id,
                )
            )

            contrib_counts = (await db.execute(
                scoped_query(
                    select(Commit.contributor_id, func.count().label("cnt"))
                    .join(Repository, Repository.id == Commit.repository_id)
                    .where(Commit.id.in_(select(sub.c.id)))
                    .group_by(Commit.contributor_id),
                    project_col=Repository.project_id,
                    contributor_col=Commit.contributor_id,
                )
            )).all()
            gini = _compute_gini([r.cnt for r in contrib_counts])

            return _kv_block({
                "repository": repo.name,
                "total_commits": total_commits,
                "active_contributors": contributor_count,
                "bus_factor": bus,
                "lines_added": agg.la,
                "lines_deleted": agg.ld,
                "churn_ratio": churn,
                "avg_pr_cycle_time": f"{round(pr_cycle or 0, 1)} hours",
                "contribution_gini": gini,
                "avg_commits_per_day_7d": trends["avg_commits_7d"],
                "avg_commits_per_day_30d": trends["avg_commits_30d"],
                "week_over_week_commit_change": f"{trends['wow_commits_delta']}%",
            }, f"Repository Overview: {repo.name}")

        return await _safe(db, _impl())

    @tool
    async def get_pr_activity(
        project_name: Optional[str] = None,
        repo_name: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        """Get pull request activity with cycle time and review turnaround metrics.

        Args:
            project_name: Optional project name to filter PRs.
            repo_name: Optional repository name to filter PRs.
            state: Optional PR state: "open", "merged", or "closed".
            limit: Max results (default 20, max 50).
        """
        async def _impl():
            filters = []
            if project_name:
                project = await _resolve_project(db, project_name)
                if not project:
                    return f"No project found matching '{project_name}'."
                repo_ids = (
                    scoped_query(
                        select(Repository.id)
                        .where(Repository.project_id == project.id),
                        project_col=Repository.project_id,
                    )
                    .subquery()
                )
                filters.append(PullRequest.repository_id.in_(select(repo_ids.c.id)))

            if repo_name:
                repo = await _resolve_repository(db, repo_name, project_name)
                if not repo:
                    return f"No repository found matching '{repo_name}'."
                filters.append(PullRequest.repository_id == repo.id)

            if state:
                state_lower = state.lower()
                valid = {"open": PRState.OPEN, "merged": PRState.MERGED, "closed": PRState.CLOSED}
                if state_lower not in valid:
                    return f"Invalid state '{state}'. Options: open, merged, closed."
                filters.append(PullRequest.state == valid[state_lower])

            first_review = (
                scoped_query(
                    select(
                        Review.pull_request_id,
                        func.min(Review.submitted_at).label("fr"),
                    )
                    .join(PullRequest, PullRequest.id == Review.pull_request_id)
                    .join(Repository, Repository.id == PullRequest.repository_id)
                    .group_by(Review.pull_request_id),
                    project_col=Repository.project_id,
                    contributor_col=Review.reviewer_id,
                )
                .subquery()
            )
            stmt = (
                select(
                    PullRequest.title, PullRequest.state,
                    PullRequest.lines_added, PullRequest.lines_deleted,
                    PullRequest.created_at, PullRequest.merged_at,
                    Contributor.canonical_name.label("author"),
                    Repository.name.label("repo"),
                    first_review.c.fr,
                )
                .outerjoin(Contributor, Contributor.id == PullRequest.contributor_id)
                .join(Repository, Repository.id == PullRequest.repository_id)
                .outerjoin(first_review, first_review.c.pull_request_id == PullRequest.id)
                .order_by(PullRequest.created_at.desc())
                .limit(min(limit, 50))
            )
            if filters:
                stmt = stmt.where(and_(*filters))

            stmt = scoped_query(
                stmt,
                project_col=Repository.project_id,
                contributor_col=PullRequest.contributor_id,
            )
            result = await db.execute(stmt)
            rows = result.all()
            if not rows:
                return "No pull requests found matching the criteria."

            formatted = []
            for r in rows:
                title = (r.title or "")[:50]
                cycle = "—"
                if r.merged_at:
                    hrs = round((r.merged_at - r.created_at).total_seconds() / 3600, 1)
                    cycle = f"{hrs}h"
                review_time = "—"
                if r.fr:
                    hrs = round((r.fr - r.created_at).total_seconds() / 3600, 1)
                    review_time = f"{hrs}h"
                formatted.append((
                    title, r.state, f"+{r.lines_added}", f"-{r.lines_deleted}",
                    str(r.created_at)[:10], r.author or "—", cycle, review_time,
                ))

            return _table(
                ["Title", "State", "Added", "Deleted", "Created",
                 "Author", "Cycle Time", "Review Time"],
                formatted,
            )

        return await _safe(db, _impl())

    @tool
    async def get_contribution_trends(
        project_name: Optional[str] = None,
        contributor_name: Optional[str] = None,
        repo_name: Optional[str] = None,
    ) -> str:
        """Get contribution trends including 7-day and 30-day averages
        and week-over-week changes.

        Args:
            project_name: Optional project name.
            contributor_name: Optional contributor name or email.
            repo_name: Optional repository name.
        """
        async def _impl():
            project_id = contributor_id = repository_id = None
            context_parts = []

            if project_name:
                project = await _resolve_project(db, project_name)
                if not project:
                    return f"No project found matching '{project_name}'."
                project_id = project.id
                context_parts.append(f"Project: {project.name}")

            if contributor_name:
                contributor = await _resolve_contributor(db, contributor_name)
                if not contributor:
                    return f"No contributor found matching '{contributor_name}'."
                contributor_id = contributor.id
                context_parts.append(f"Contributor: {contributor.canonical_name}")

            if repo_name:
                repo = await _resolve_repository(db, repo_name, project_name)
                if not repo:
                    return f"No repository found matching '{repo_name}'."
                repository_id = repo.id
                context_parts.append(f"Repository: {repo.name}")

            trends = await get_trends(
                db,
                project_id=project_id,
                contributor_id=contributor_id,
                repository_id=repository_id,
            )

            title = "Contribution Trends"
            if context_parts:
                title += f" ({', '.join(context_parts)})"

            return _kv_block({
                "avg_commits_per_day_7d": trends["avg_commits_7d"],
                "avg_commits_per_day_30d": trends["avg_commits_30d"],
                "avg_lines_per_day_7d": trends["avg_lines_7d"],
                "avg_lines_per_day_30d": trends["avg_lines_30d"],
                "week_over_week_commits": f"{trends['wow_commits_delta']}%",
                "week_over_week_lines": f"{trends['wow_lines_delta']}%",
                "current_week_commits": trends["current_week"]["commits"],
                "current_week_lines_added": trends["current_week"]["lines_added"],
                "current_week_lines_deleted": trends["current_week"]["lines_deleted"],
                "previous_week_commits": trends["previous_week"]["commits"],
                "previous_week_lines_added": trends["previous_week"]["lines_added"],
                "previous_week_lines_deleted": trends["previous_week"]["lines_deleted"],
            }, title)

        return await _safe(db, _impl())

    @tool
    async def get_code_hotspots(
        repo_name: str,
        limit: int = 20,
    ) -> str:
        """Get the most frequently changed files in a repository (hotspots).
        High-churn files often indicate areas of instability or active development.

        Args:
            repo_name: Name of the repository.
            limit: Number of files to return (default 20, max 50).
        """
        async def _impl():
            repo = await _resolve_repository(db, repo_name)
            if not repo:
                return f"No repository found matching '{repo_name}'."

            result = await db.execute(
                scoped_query(
                    select(
                        CommitFile.file_path,
                        func.count(CommitFile.commit_id.distinct()).label("commits"),
                        func.count(Commit.contributor_id.distinct()).label("contributors"),
                        func.sum(CommitFile.lines_added).label("la"),
                        func.sum(CommitFile.lines_deleted).label("ld"),
                    )
                    .join(Commit, Commit.id == CommitFile.commit_id)
                    .join(Repository, Repository.id == Commit.repository_id)
                    .where(Commit.repository_id == repo.id)
                    .group_by(CommitFile.file_path)
                    .order_by(func.count(CommitFile.commit_id.distinct()).desc())
                    .limit(min(limit, 50)),
                    project_col=Repository.project_id,
                    contributor_col=Commit.contributor_id,
                )
            )
            rows = result.all()
            if not rows:
                return f"No file change data found for repository '{repo.name}'."

            return _table(
                ["File", "Commits", "Contributors", "Lines Added", "Lines Deleted"],
                [
                    (r.file_path, r.commits, r.contributors, r.la or 0, r.ld or 0)
                    for r in rows
                ],
            )

        return await _safe(db, _impl())

    # ── PR / Review Deep Dive ─────────────────────────────────────────

    @tool
    async def get_pr_review_cycle(
        project_name: Optional[str] = None,
        repo_name: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> str:
        """Get detailed PR lifecycle metrics including median/p90 time-to-first-review,
        cycle time, average iterations, comments, and approval rate.

        Args:
            project_name: Optional project name to scope analysis.
            repo_name: Optional repository name to scope analysis.
            from_date: Optional start date (YYYY-MM-DD).
            to_date: Optional end date (YYYY-MM-DD).
        """
        async def _impl():
            filters: list = []
            context: list[str] = []
            if project_name:
                project = await _resolve_project(db, project_name)
                if not project:
                    return f"No project found matching '{project_name}'."
                repo_ids = (
                    scoped_query(
                        select(Repository.id).where(Repository.project_id == project.id),
                        project_col=Repository.project_id,
                    )
                    .subquery()
                )
                filters.append(PullRequest.repository_id.in_(select(repo_ids.c.id)))
                context.append(f"Project: {project.name}")
            if repo_name:
                repo = await _resolve_repository(db, repo_name, project_name)
                if not repo:
                    return f"No repository found matching '{repo_name}'."
                filters.append(PullRequest.repository_id == repo.id)
                context.append(f"Repo: {repo.name}")
            fd, td = _parse_date(from_date), _parse_date(to_date)
            if fd:
                filters.append(PullRequest.created_at >= fd)
            if td:
                filters.append(PullRequest.created_at <= td + timedelta(days=1))

            base_where = and_(*filters) if filters else True

            total_prs = await db.scalar(
                scoped_query(
                    select(func.count()).select_from(PullRequest)
                    .join(Repository, Repository.id == PullRequest.repository_id)
                    .where(base_where),
                    project_col=Repository.project_id,
                    contributor_col=PullRequest.contributor_id,
                )
            )
            if not total_prs:
                return "No pull requests found matching the criteria."

            cycle_times = sorted(
                float(v) for v in (await db.execute(
                    scoped_query(
                        select(func.extract("epoch", PullRequest.merged_at - PullRequest.created_at) / 3600)
                        .join(Repository, Repository.id == PullRequest.repository_id)
                        .where(base_where, PullRequest.state == PRState.MERGED, PullRequest.merged_at.isnot(None)),
                        project_col=Repository.project_id,
                        contributor_col=PullRequest.contributor_id,
                    )
                )).scalars().all()
            )

            first_rev = (
                scoped_query(
                    select(Review.pull_request_id, func.min(Review.submitted_at).label("fr"))
                    .join(PullRequest, PullRequest.id == Review.pull_request_id)
                    .join(Repository, Repository.id == PullRequest.repository_id)
                    .group_by(Review.pull_request_id),
                    project_col=Repository.project_id,
                    contributor_col=Review.reviewer_id,
                ).subquery()
            )
            review_times = sorted(
                float(v) for v in (await db.execute(
                    scoped_query(
                        select(func.extract("epoch", first_rev.c.fr - PullRequest.created_at) / 3600)
                        .join(first_rev, first_rev.c.pull_request_id == PullRequest.id)
                        .join(Repository, Repository.id == PullRequest.repository_id)
                        .where(base_where),
                        project_col=Repository.project_id,
                        contributor_col=PullRequest.contributor_id,
                    )
                )).scalars().all()
            )

            avgs = (await db.execute(
                scoped_query(
                    select(
                        func.avg(PullRequest.iteration_count).label("avg_iter"),
                        func.avg(PullRequest.comment_count).label("avg_comments"),
                    )
                    .join(Repository, Repository.id == PullRequest.repository_id)
                    .where(base_where),
                    project_col=Repository.project_id,
                    contributor_col=PullRequest.contributor_id,
                )
            )).one()

            pr_ids_approved = scoped_query(
                select(PullRequest.id)
                .join(Repository, Repository.id == PullRequest.repository_id)
                .where(base_where),
                project_col=Repository.project_id,
                contributor_col=PullRequest.contributor_id,
            )
            approved_prs = await db.scalar(
                scoped_query(
                    select(func.count(Review.pull_request_id.distinct()))
                    .join(PullRequest, PullRequest.id == Review.pull_request_id)
                    .join(Repository, Repository.id == PullRequest.repository_id)
                    .where(
                        Review.state == ReviewState.APPROVED,
                        Review.pull_request_id.in_(pr_ids_approved),
                    ),
                    project_col=Repository.project_id,
                    contributor_col=Review.reviewer_id,
                )
            ) or 0

            title = "PR Review Cycle"
            if context:
                title += f" ({', '.join(context)})"
            return _kv_block({
                "total_prs": total_prs,
                "merged_prs": len(cycle_times),
                "median_cycle_time": f"{_percentile(cycle_times, 0.5):.1f} hours" if cycle_times else "—",
                "p90_cycle_time": f"{_percentile(cycle_times, 0.9):.1f} hours" if cycle_times else "—",
                "median_time_to_first_review": f"{_percentile(review_times, 0.5):.1f} hours" if review_times else "—",
                "p90_time_to_first_review": f"{_percentile(review_times, 0.9):.1f} hours" if review_times else "—",
                "avg_iterations_per_pr": round(float(avgs.avg_iter or 0), 1),
                "avg_comments_per_pr": round(float(avgs.avg_comments or 0), 1),
                "approval_rate": f"{round(approved_prs / total_prs * 100, 1)}%",
            }, title)
        return await _safe(db, _impl())

    @tool
    async def get_reviewer_leaderboard(
        project_name: Optional[str] = None,
        repo_name: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        """Get top code reviewers ranked by volume, turnaround speed, and thoroughness.

        Args:
            project_name: Optional project name to scope.
            repo_name: Optional repository name to scope.
            from_date: Optional start date (YYYY-MM-DD).
            to_date: Optional end date (YYYY-MM-DD).
            limit: Number of reviewers to return (default 10, max 25).
        """
        async def _impl():
            filters: list = [Review.reviewer_id.isnot(None)]
            if project_name:
                project = await _resolve_project(db, project_name)
                if not project:
                    return f"No project found matching '{project_name}'."
                repo_ids = (
                    scoped_query(
                        select(Repository.id).where(Repository.project_id == project.id),
                        project_col=Repository.project_id,
                    )
                    .subquery()
                )
                filters.append(PullRequest.repository_id.in_(select(repo_ids.c.id)))
            if repo_name:
                repo = await _resolve_repository(db, repo_name, project_name)
                if not repo:
                    return f"No repository found matching '{repo_name}'."
                filters.append(PullRequest.repository_id == repo.id)
            fd, td = _parse_date(from_date), _parse_date(to_date)
            if fd:
                filters.append(Review.submitted_at >= fd)
            if td:
                filters.append(Review.submitted_at <= td + timedelta(days=1))

            rows = (await db.execute(
                scoped_query(
                    select(
                        Contributor.canonical_name,
                        func.count(Review.id).label("reviews"),
                        func.avg(func.extract("epoch", Review.submitted_at - PullRequest.created_at) / 3600).label("avg_ta"),
                        func.avg(Review.comment_count).label("avg_comments"),
                        func.sum(case((Review.state == ReviewState.APPROVED, 1), else_=0)).label("approvals"),
                        func.sum(case((Review.state == ReviewState.CHANGES_REQUESTED, 1), else_=0)).label("changes_req"),
                    )
                    .join(PullRequest, PullRequest.id == Review.pull_request_id)
                    .join(Repository, Repository.id == PullRequest.repository_id)
                    .join(Contributor, Contributor.id == Review.reviewer_id)
                    .where(and_(*filters))
                    .group_by(Contributor.id, Contributor.canonical_name)
                    .order_by(func.count(Review.id).desc())
                    .limit(min(limit, 25)),
                    project_col=Repository.project_id,
                    contributor_col=Review.reviewer_id,
                )
            )).all()
            if not rows:
                return "No review data found matching the criteria."
            return _table(
                ["Reviewer", "Reviews", "Avg Turnaround (h)", "Avg Comments", "Approvals", "Changes Req"],
                [(r.canonical_name, r.reviews, round(float(r.avg_ta or 0), 1),
                  round(float(r.avg_comments or 0), 1), r.approvals, r.changes_req) for r in rows],
            )
        return await _safe(db, _impl())

    @tool
    async def get_review_network(
        project_name: Optional[str] = None,
        repo_name: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        """Get the review network showing who reviews whose code.
        Returns author-reviewer pairs with review counts and average turnaround.

        Args:
            project_name: Optional project name to scope.
            repo_name: Optional repository name to scope.
            limit: Max pairs to return (default 20, max 50).
        """
        async def _impl():
            filters: list = [Review.reviewer_id.isnot(None), PullRequest.contributor_id.isnot(None)]
            if project_name:
                project = await _resolve_project(db, project_name)
                if not project:
                    return f"No project found matching '{project_name}'."
                repo_ids = (
                    scoped_query(
                        select(Repository.id).where(Repository.project_id == project.id),
                        project_col=Repository.project_id,
                    )
                    .subquery()
                )
                filters.append(PullRequest.repository_id.in_(select(repo_ids.c.id)))
            if repo_name:
                repo = await _resolve_repository(db, repo_name, project_name)
                if not repo:
                    return f"No repository found matching '{repo_name}'."
                filters.append(PullRequest.repository_id == repo.id)

            AuthorC = aliased(Contributor)
            ReviewerC = aliased(Contributor)
            rows = (await db.execute(
                scoped_query(
                    select(
                        AuthorC.canonical_name.label("author"),
                        ReviewerC.canonical_name.label("reviewer"),
                        func.count(Review.id).label("review_count"),
                        func.avg(func.extract("epoch", Review.submitted_at - PullRequest.created_at) / 3600).label("avg_ta"),
                    )
                    .join(PullRequest, PullRequest.id == Review.pull_request_id)
                    .join(Repository, Repository.id == PullRequest.repository_id)
                    .join(AuthorC, AuthorC.id == PullRequest.contributor_id)
                    .join(ReviewerC, ReviewerC.id == Review.reviewer_id)
                    .where(and_(*filters))
                    .group_by(AuthorC.canonical_name, ReviewerC.canonical_name)
                    .order_by(func.count(Review.id).desc())
                    .limit(min(limit, 50)),
                    project_col=Repository.project_id,
                    contributor_col=PullRequest.contributor_id,
                )
            )).all()
            if not rows:
                return "No review network data found."
            return _table(
                ["Author", "Reviewer", "Reviews", "Avg Turnaround (h)"],
                [(r.author, r.reviewer, r.review_count, round(float(r.avg_ta or 0), 1)) for r in rows],
            )
        return await _safe(db, _impl())

    @tool
    async def get_pr_size_analysis(
        project_name: Optional[str] = None,
        repo_name: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> str:
        """Analyze PR size distribution and its impact on review speed.
        Buckets: Small (<50 lines), Medium (50-200), Large (200-500), XL (>500).

        Args:
            project_name: Optional project name to scope.
            repo_name: Optional repository name to scope.
            from_date: Optional start date (YYYY-MM-DD).
            to_date: Optional end date (YYYY-MM-DD).
        """
        async def _impl():
            filters: list = []
            if project_name:
                project = await _resolve_project(db, project_name)
                if not project:
                    return f"No project found matching '{project_name}'."
                repo_ids = (
                    scoped_query(
                        select(Repository.id).where(Repository.project_id == project.id),
                        project_col=Repository.project_id,
                    )
                    .subquery()
                )
                filters.append(PullRequest.repository_id.in_(select(repo_ids.c.id)))
            if repo_name:
                repo = await _resolve_repository(db, repo_name, project_name)
                if not repo:
                    return f"No repository found matching '{repo_name}'."
                filters.append(PullRequest.repository_id == repo.id)
            fd, td = _parse_date(from_date), _parse_date(to_date)
            if fd:
                filters.append(PullRequest.created_at >= fd)
            if td:
                filters.append(PullRequest.created_at <= td + timedelta(days=1))
            base_where = and_(*filters) if filters else True

            size_expr = PullRequest.lines_added + PullRequest.lines_deleted
            bucket = case(
                (size_expr < 50, "1-Small (<50)"),
                (size_expr < 200, "2-Medium (50-200)"),
                (size_expr < 500, "3-Large (200-500)"),
                else_="4-XL (>500)",
            ).label("bucket")

            rows = (await db.execute(
                scoped_query(
                    select(
                        bucket,
                        func.count().label("pr_count"),
                        func.avg(case(
                            (and_(PullRequest.state == PRState.MERGED, PullRequest.merged_at.isnot(None)),
                             func.extract("epoch", PullRequest.merged_at - PullRequest.created_at) / 3600),
                            else_=None,
                        )).label("avg_cycle"),
                        func.avg(PullRequest.comment_count).label("avg_comments"),
                    )
                    .join(Repository, Repository.id == PullRequest.repository_id)
                    .where(base_where).group_by(bucket).order_by(bucket),
                    project_col=Repository.project_id,
                    contributor_col=PullRequest.contributor_id,
                )
            )).all()
            if not rows:
                return "No pull request data found."
            return _table(
                ["Size Bucket", "PRs", "Avg Cycle Time (h)", "Avg Comments"],
                [(r.bucket[2:], r.pr_count, round(float(r.avg_cycle or 0), 1),
                  round(float(r.avg_comments or 0), 1)) for r in rows],
            )
        return await _safe(db, _impl())

    @tool
    async def get_contributor_pr_summary(
        contributor_name: str,
        project_name: Optional[str] = None,
    ) -> str:
        """Get a contributor's detailed PR authoring and review statistics.

        Args:
            contributor_name: Name or email of the contributor.
            project_name: Optional project name to scope.
        """
        async def _impl():
            contributor = await _resolve_contributor(db, contributor_name)
            if not contributor:
                return f"No contributor found matching '{contributor_name}'."

            pr_filters: list = [PullRequest.contributor_id == contributor.id]
            rev_filters: list = [Review.reviewer_id == contributor.id]
            if project_name:
                project = await _resolve_project(db, project_name)
                if project:
                    repo_ids = (
                        scoped_query(
                            select(Repository.id).where(Repository.project_id == project.id),
                            project_col=Repository.project_id,
                        )
                        .subquery()
                    )
                    pr_filters.append(PullRequest.repository_id.in_(select(repo_ids.c.id)))
                    rev_filters.append(Review.pull_request_id.in_(
                        scoped_query(
                            select(PullRequest.id)
                            .join(Repository, Repository.id == PullRequest.repository_id)
                            .where(PullRequest.repository_id.in_(select(repo_ids.c.id))),
                            project_col=Repository.project_id,
                            contributor_col=PullRequest.contributor_id,
                        )
                    ))

            state_counts = (await db.execute(
                scoped_query(
                    select(PullRequest.state, func.count().label("cnt"))
                    .join(Repository, Repository.id == PullRequest.repository_id)
                    .where(and_(*pr_filters)).group_by(PullRequest.state),
                    project_col=Repository.project_id,
                    contributor_col=PullRequest.contributor_id,
                )
            )).all()
            by_state = {r.state: r.cnt for r in state_counts}

            auth_agg = (await db.execute(
                scoped_query(
                    select(
                        func.avg(PullRequest.lines_added + PullRequest.lines_deleted).label("avg_size"),
                        func.avg(case(
                            (and_(PullRequest.state == PRState.MERGED, PullRequest.merged_at.isnot(None)),
                             func.extract("epoch", PullRequest.merged_at - PullRequest.created_at) / 3600),
                            else_=None,
                        )).label("avg_cycle"),
                        func.avg(PullRequest.iteration_count).label("avg_iter"),
                    )
                    .join(Repository, Repository.id == PullRequest.repository_id)
                    .where(and_(*pr_filters)),
                    project_col=Repository.project_id,
                    contributor_col=PullRequest.contributor_id,
                )
            )).one()

            rev_agg = (await db.execute(
                scoped_query(
                    select(
                        func.count().label("total"),
                        func.avg(func.extract("epoch", Review.submitted_at - PullRequest.created_at) / 3600).label("avg_ta"),
                        func.avg(Review.comment_count).label("avg_comments"),
                        func.sum(case((Review.state == ReviewState.APPROVED, 1), else_=0)).label("approvals"),
                    )
                    .join(PullRequest, PullRequest.id == Review.pull_request_id)
                    .join(Repository, Repository.id == PullRequest.repository_id)
                    .where(and_(*rev_filters)),
                    project_col=Repository.project_id,
                    contributor_col=Review.reviewer_id,
                )
            )).one()

            return _kv_block({
                "contributor": contributor.canonical_name,
                "prs_open": by_state.get(PRState.OPEN, 0),
                "prs_merged": by_state.get(PRState.MERGED, 0),
                "prs_closed": by_state.get(PRState.CLOSED, 0),
                "avg_pr_size_lines": round(float(auth_agg.avg_size or 0)),
                "avg_cycle_time": f"{round(float(auth_agg.avg_cycle or 0), 1)} hours",
                "avg_iterations": round(float(auth_agg.avg_iter or 0), 1),
                "reviews_given": rev_agg.total,
                "avg_review_turnaround": f"{round(float(rev_agg.avg_ta or 0), 1)} hours",
                "avg_review_comments": round(float(rev_agg.avg_comments or 0), 1),
                "approval_rate": f"{round(rev_agg.approvals / rev_agg.total * 100, 1)}%" if rev_agg.total else "—",
            }, f"PR Summary: {contributor.canonical_name}")
        return await _safe(db, _impl())

    # ── File / Ownership ───────────────────────────────────────────────

    @tool
    async def get_file_ownership(repo_name: str, limit: int = 20) -> str:
        """Get primary code owners of the most frequently changed files in a repo.
        Shows ownership concentration and knowledge distribution.

        Args:
            repo_name: Name of the repository.
            limit: Number of files to analyze (default 20, max 50).
        """
        async def _impl():
            repo = await _resolve_repository(db, repo_name)
            if not repo:
                return f"No repository found matching '{repo_name}'."

            top_files = (await db.execute(
                scoped_query(
                    select(
                        CommitFile.file_path,
                        func.count(CommitFile.commit_id.distinct()).label("total_commits"),
                        func.count(Commit.contributor_id.distinct()).label("total_contributors"),
                    )
                    .join(Commit, Commit.id == CommitFile.commit_id)
                    .join(Repository, Repository.id == Commit.repository_id)
                    .where(Commit.repository_id == repo.id)
                    .group_by(CommitFile.file_path)
                    .order_by(func.count(CommitFile.commit_id.distinct()).desc())
                    .limit(min(limit, 50)),
                    project_col=Repository.project_id,
                    contributor_col=Commit.contributor_id,
                )
            )).all()
            if not top_files:
                return f"No file data found for repository '{repo.name}'."

            rows = []
            for f in top_files:
                owner = (await db.execute(
                    scoped_query(
                        select(Contributor.canonical_name, func.count().label("cnt"))
                        .join(Commit, Commit.contributor_id == Contributor.id)
                        .join(CommitFile, CommitFile.commit_id == Commit.id)
                        .join(Repository, Repository.id == Commit.repository_id)
                        .where(Commit.repository_id == repo.id, CommitFile.file_path == f.file_path)
                        .group_by(Contributor.id, Contributor.canonical_name)
                        .order_by(func.count().desc()).limit(1),
                        project_col=Repository.project_id,
                        contributor_col=Commit.contributor_id,
                    )
                )).first()
                pct = round(owner.cnt / f.total_commits * 100, 1) if owner and f.total_commits else 0
                rows.append((f.file_path, owner.canonical_name if owner else "—",
                             f"{pct}%", f.total_contributors, f.total_commits))
            return _table(["File", "Primary Owner", "Ownership %", "Contributors", "Commits"], rows)
        return await _safe(db, _impl())

    @tool
    async def get_contributor_file_focus(
        contributor_name: str,
        repo_name: Optional[str] = None,
        limit: int = 15,
    ) -> str:
        """Show which directories/areas a contributor focuses on most.

        Args:
            contributor_name: Name or email of the contributor.
            repo_name: Optional repository name to scope.
            limit: Number of directories to return (default 15, max 30).
        """
        async def _impl():
            contributor = await _resolve_contributor(db, contributor_name)
            if not contributor:
                return f"No contributor found matching '{contributor_name}'."
            filters: list = [Commit.contributor_id == contributor.id]
            if repo_name:
                repo = await _resolve_repository(db, repo_name)
                if repo:
                    filters.append(Commit.repository_id == repo.id)

            file_rows = (await db.execute(
                scoped_query(
                    select(
                        CommitFile.file_path,
                        func.count(CommitFile.commit_id.distinct()).label("commits"),
                        func.sum(CommitFile.lines_added).label("la"),
                        func.sum(CommitFile.lines_deleted).label("ld"),
                    )
                    .join(Commit, Commit.id == CommitFile.commit_id)
                    .join(Repository, Repository.id == Commit.repository_id)
                    .where(and_(*filters))
                    .group_by(CommitFile.file_path),
                    project_col=Repository.project_id,
                    contributor_col=Commit.contributor_id,
                )
            )).all()
            if not file_rows:
                return f"No file data found for '{contributor.canonical_name}'."

            dir_stats: dict[str, dict] = {}
            for r in file_rows:
                parts = r.file_path.rsplit("/", 1)
                directory = parts[0] if len(parts) > 1 else "."
                s = dir_stats.setdefault(directory, {"commits": 0, "la": 0, "ld": 0, "files": 0})
                s["commits"] += r.commits
                s["la"] += r.la or 0
                s["ld"] += r.ld or 0
                s["files"] += 1

            sorted_dirs = sorted(dir_stats.items(), key=lambda x: x[1]["commits"], reverse=True)[:min(limit, 30)]
            return _table(
                ["Directory", "Commits", "Files", "Lines Added", "Lines Deleted"],
                [(d, s["commits"], s["files"], s["la"], s["ld"]) for d, s in sorted_dirs],
            )
        return await _safe(db, _impl())

    @tool
    async def get_file_collaboration(
        repo_name: str,
        file_path: str,
        limit: int = 15,
    ) -> str:
        """Show all contributors who have edited a file or directory,
        with commit counts and last touch date.

        Args:
            repo_name: Name of the repository.
            file_path: File path or directory prefix (partial match supported).
            limit: Max contributors to return (default 15, max 30).
        """
        async def _impl():
            repo = await _resolve_repository(db, repo_name)
            if not repo:
                return f"No repository found matching '{repo_name}'."
            rows = (await db.execute(
                scoped_query(
                    select(
                        Contributor.canonical_name,
                        func.count(CommitFile.commit_id.distinct()).label("commits"),
                        func.sum(CommitFile.lines_added).label("la"),
                        func.sum(CommitFile.lines_deleted).label("ld"),
                        func.max(Commit.authored_at).label("last_touch"),
                    )
                    .join(Commit, Commit.id == CommitFile.commit_id)
                    .join(Repository, Repository.id == Commit.repository_id)
                    .join(Contributor, Contributor.id == Commit.contributor_id)
                    .where(Commit.repository_id == repo.id, CommitFile.file_path.ilike(f"%{file_path}%"))
                    .group_by(Contributor.id, Contributor.canonical_name)
                    .order_by(func.count(CommitFile.commit_id.distinct()).desc())
                    .limit(min(limit, 30)),
                    project_col=Repository.project_id,
                    contributor_col=Commit.contributor_id,
                )
            )).all()
            if not rows:
                return f"No contributors found for files matching '{file_path}' in '{repo.name}'."
            return _table(
                ["Contributor", "Commits", "Lines Added", "Lines Deleted", "Last Touch"],
                [(r.canonical_name, r.commits, r.la or 0, r.ld or 0,
                  str(r.last_touch)[:10] if r.last_touch else "—") for r in rows],
            )
        return await _safe(db, _impl())

    # ── Contributor Comparison / Patterns ──────────────────────────────

    @tool
    async def compare_contributors(
        contributor_names: str,
        project_name: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> str:
        """Compare 2-5 contributors side by side across key metrics.

        Args:
            contributor_names: Comma-separated list of contributor names or emails (2-5).
            project_name: Optional project name to scope.
            from_date: Optional start date (YYYY-MM-DD).
            to_date: Optional end date (YYYY-MM-DD).
        """
        async def _impl():
            names = [n.strip() for n in contributor_names.split(",")]
            if len(names) < 2 or len(names) > 5:
                return "Please provide 2 to 5 contributor names separated by commas."

            contributors = []
            for name in names:
                c = await _resolve_contributor(db, name)
                if not c:
                    return f"No contributor found matching '{name}'."
                contributors.append(c)

            fd, td = _parse_date(from_date), _parse_date(to_date)
            repo_filter = None
            if project_name:
                project = await _resolve_project(db, project_name)
                if project:
                    repo_filter = (
                        scoped_query(
                            select(Repository.id).where(Repository.project_id == project.id),
                            project_col=Repository.project_id,
                        )
                        .subquery()
                    )

            rows = []
            for c in contributors:
                commit_q = (
                    select(Commit)
                    .join(Repository, Repository.id == Commit.repository_id)
                    .where(Commit.contributor_id == c.id)
                )
                commit_q = scoped_query(
                    commit_q,
                    project_col=Repository.project_id,
                    contributor_col=Commit.contributor_id,
                )
                if fd:
                    commit_q = commit_q.where(Commit.authored_at >= fd)
                if td:
                    commit_q = commit_q.where(Commit.authored_at <= td + timedelta(days=1))
                if repo_filter is not None:
                    commit_q = commit_q.where(Commit.repository_id.in_(select(repo_filter.c.id)))
                sub = commit_q.with_only_columns(Commit.id).subquery()

                agg = (await db.execute(
                    scoped_query(
                        select(
                            func.count().label("commits"),
                            func.coalesce(func.sum(Commit.lines_added), 0).label("la"),
                            func.coalesce(func.sum(Commit.lines_deleted), 0).label("ld"),
                        )
                        .join(Repository, Repository.id == Commit.repository_id)
                        .where(Commit.id.in_(select(sub.c.id))),
                        project_col=Repository.project_id,
                        contributor_col=Commit.contributor_id,
                    )
                )).one()
                prs = await db.scalar(
                    scoped_query(
                        select(func.count()).select_from(PullRequest)
                        .join(Repository, Repository.id == PullRequest.repository_id)
                        .where(PullRequest.contributor_id == c.id),
                        project_col=Repository.project_id,
                        contributor_col=PullRequest.contributor_id,
                    )
                ) or 0
                reviews = await db.scalar(
                    scoped_query(
                        select(func.count()).select_from(Review)
                        .join(PullRequest, PullRequest.id == Review.pull_request_id)
                        .join(Repository, Repository.id == PullRequest.repository_id)
                        .where(Review.reviewer_id == c.id),
                        project_col=Repository.project_id,
                        contributor_col=Review.reviewer_id,
                    )
                ) or 0
                impact = round(agg.commits + (agg.la + agg.ld) * 0.1 + prs * 5 + reviews * 3, 1)
                rows.append((c.canonical_name, agg.commits, agg.la, agg.ld, prs, reviews, impact))

            return _table(
                ["Contributor", "Commits", "Lines Added", "Lines Deleted", "PRs", "Reviews", "Impact"],
                rows,
            )
        return await _safe(db, _impl())

    @tool
    async def get_work_patterns(
        contributor_name: Optional[str] = None,
        project_name: Optional[str] = None,
        repo_name: Optional[str] = None,
    ) -> str:
        """Get day-of-week and hour-of-day commit distribution.
        Shows when work activity peaks.

        Args:
            contributor_name: Optional contributor name to scope.
            project_name: Optional project name to scope.
            repo_name: Optional repository name to scope.
        """
        async def _impl():
            filters: list = []
            context: list[str] = []
            if contributor_name:
                contributor = await _resolve_contributor(db, contributor_name)
                if not contributor:
                    return f"No contributor found matching '{contributor_name}'."
                filters.append(Commit.contributor_id == contributor.id)
                context.append(contributor.canonical_name)
            if project_name:
                project = await _resolve_project(db, project_name)
                if project:
                    filters.append(Commit.repository_id.in_(
                        scoped_query(
                            select(Repository.id).where(Repository.project_id == project.id),
                            project_col=Repository.project_id,
                        )
                    ))
                    context.append(project.name)
            if repo_name:
                repo = await _resolve_repository(db, repo_name, project_name)
                if repo:
                    filters.append(Commit.repository_id == repo.id)
                    context.append(repo.name)

            base_where = and_(*filters) if filters else True
            rows = (await db.execute(
                scoped_query(
                    select(
                        func.extract("dow", Commit.authored_at).label("dow"),
                        func.extract("hour", Commit.authored_at).label("hour"),
                        func.count().label("commits"),
                    )
                    .select_from(Commit)
                    .join(Repository, Repository.id == Commit.repository_id)
                    .where(base_where).group_by("dow", "hour").order_by("dow", "hour"),
                    project_col=Repository.project_id,
                    contributor_col=Commit.contributor_id,
                )
            )).all()
            if not rows:
                return "No commit data found."

            day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
            day_totals: dict[int, int] = {}
            hour_totals: dict[int, int] = {}
            for r in rows:
                d, h = int(r.dow), int(r.hour)
                day_totals[d] = day_totals.get(d, 0) + r.commits
                hour_totals[h] = hour_totals.get(h, 0) + r.commits

            title = "Work Patterns"
            if context:
                title += f" ({', '.join(context)})"
            day_lines = "\n".join(f"- {day_names[d]}: {_fmt(day_totals.get(d, 0))} commits" for d in range(7))
            top_hours = sorted(hour_totals.items(), key=lambda x: x[1], reverse=True)[:5]
            hour_lines = "\n".join(f"- {h:02d}:00: {_fmt(c)} commits" for h, c in top_hours)
            total = sum(day_totals.values())
            return f"**{title}** (total: {_fmt(total)} commits)\n\n**By Day:**\n{day_lines}\n\n**Top Hours:**\n{hour_lines}"
        return await _safe(db, _impl())

    @tool
    async def get_contributor_cross_repo(contributor_name: str) -> str:
        """Show which repositories a contributor works on and their activity in each.

        Args:
            contributor_name: Name or email of the contributor.
        """
        async def _impl():
            contributor = await _resolve_contributor(db, contributor_name)
            if not contributor:
                return f"No contributor found matching '{contributor_name}'."
            rows = (await db.execute(
                scoped_query(
                    select(
                        Repository.name.label("repo"), Project.name.label("project"),
                        func.count().label("commits"),
                        func.coalesce(func.sum(Commit.lines_added), 0).label("la"),
                        func.max(Commit.authored_at).label("last_active"),
                    )
                    .join(Repository, Repository.id == Commit.repository_id)
                    .join(Project, Project.id == Repository.project_id)
                    .where(Commit.contributor_id == contributor.id)
                    .group_by(Repository.id, Repository.name, Project.name)
                    .order_by(func.count().desc()),
                    project_col=Repository.project_id,
                    contributor_col=Commit.contributor_id,
                )
            )).all()
            if not rows:
                return f"No commit data found for '{contributor.canonical_name}'."
            return _table(
                ["Repository", "Project", "Commits", "Lines Added", "Last Active"],
                [(r.repo, r.project, r.commits, r.la,
                  str(r.last_active)[:10] if r.last_active else "—") for r in rows],
            )
        return await _safe(db, _impl())

    @tool
    async def get_inactive_contributors(
        project_name: Optional[str] = None,
        days_inactive: int = 30,
        limit: int = 20,
    ) -> str:
        """Find contributors who were previously active but have gone quiet.

        Args:
            project_name: Optional project name to scope.
            days_inactive: Days of inactivity to qualify (default 30).
            limit: Max results (default 20, max 50).
        """
        async def _impl():
            cutoff = date.today() - timedelta(days=days_inactive)
            prev_start = cutoff - timedelta(days=30)
            base_filters: list = []
            if project_name:
                project = await _resolve_project(db, project_name)
                if not project:
                    return f"No project found matching '{project_name}'."
                repo_ids = (
                    scoped_query(
                        select(Repository.id).where(Repository.project_id == project.id),
                        project_col=Repository.project_id,
                    )
                    .subquery()
                )
                base_filters.append(Commit.repository_id.in_(select(repo_ids.c.id)))

            recent_active = (
                scoped_query(
                    select(Commit.contributor_id.distinct())
                    .join(Repository, Repository.id == Commit.repository_id)
                    .where(Commit.authored_at >= cutoff, *base_filters),
                    project_col=Repository.project_id,
                    contributor_col=Commit.contributor_id,
                )
            ).subquery()

            rows = (await db.execute(
                scoped_query(
                    select(
                        Contributor.canonical_name,
                        func.max(Commit.authored_at).label("last_commit"),
                        func.count().label("prev_commits"),
                    )
                    .join(Commit, Commit.contributor_id == Contributor.id)
                    .join(Repository, Repository.id == Commit.repository_id)
                    .where(
                        Commit.authored_at < cutoff, Commit.authored_at >= prev_start,
                        Contributor.id.notin_(select(recent_active.c.contributor_id)),
                        *base_filters,
                    )
                    .group_by(Contributor.id, Contributor.canonical_name)
                    .order_by(func.max(Commit.authored_at).desc())
                    .limit(min(limit, 50)),
                    project_col=Repository.project_id,
                    contributor_col=Commit.contributor_id,
                )
            )).all()
            if not rows:
                return f"No inactive contributors found (inactive >{days_inactive} days)."
            return _table(
                ["Contributor", "Last Commit", "Commits (prev 30d)"],
                [(r.canonical_name, str(r.last_commit)[:10] if r.last_commit else "—", r.prev_commits) for r in rows],
            )
        return await _safe(db, _impl())

    # ── Branch / Freshness ─────────────────────────────────────────────

    @tool
    async def get_branch_summary(repo_name: str, days: int = 30) -> str:
        """Get active branches in a repository with recent commit activity.

        Args:
            repo_name: Name of the repository.
            days: Look-back window in days (default 30).
        """
        async def _impl():
            repo = await _resolve_repository(db, repo_name)
            if not repo:
                return f"No repository found matching '{repo_name}'."
            since = date.today() - timedelta(days=days)
            rows = (await db.execute(
                scoped_query(
                    select(
                        Branch.name, Branch.is_default,
                        func.count(Commit.id.distinct()).label("commits"),
                        func.count(Commit.contributor_id.distinct()).label("contributors"),
                        func.max(Commit.authored_at).label("last_commit"),
                    )
                    .join(commit_branches, commit_branches.c.branch_id == Branch.id)
                    .join(Commit, Commit.id == commit_branches.c.commit_id)
                    .join(Repository, Repository.id == Branch.repository_id)
                    .where(Branch.repository_id == repo.id, Commit.authored_at >= since)
                    .group_by(Branch.id, Branch.name, Branch.is_default)
                    .order_by(func.count(Commit.id.distinct()).desc()),
                    project_col=Repository.project_id,
                    contributor_col=Commit.contributor_id,
                )
            )).all()
            if not rows:
                return f"No branch activity found in '{repo.name}' in the last {days} days."
            return _table(
                ["Branch", "Default", "Commits", "Contributors", "Last Commit"],
                [(r.name, "Yes" if r.is_default else "No", r.commits, r.contributors,
                  str(r.last_commit)[:10] if r.last_commit else "—") for r in rows],
            )
        return await _safe(db, _impl())

    @tool
    async def get_branch_comparison(repo_name: str, branch_a: str, branch_b: str) -> str:
        """Compare two branches in a repository by commits, contributors, and activity.

        Args:
            repo_name: Name of the repository.
            branch_a: First branch name.
            branch_b: Second branch name.
        """
        async def _impl():
            repo = await _resolve_repository(db, repo_name)
            if not repo:
                return f"No repository found matching '{repo_name}'."

            async def _stats(branch_name: str):
                br = (await db.execute(
                    scoped_query(
                        select(Branch)
                        .join(Repository, Repository.id == Branch.repository_id)
                        .where(Branch.repository_id == repo.id, Branch.name == branch_name),
                        project_col=Repository.project_id,
                    )
                )).scalar_one_or_none()
                if not br:
                    return None
                cids = select(commit_branches.c.commit_id).where(commit_branches.c.branch_id == br.id).subquery()
                return (await db.execute(
                    scoped_query(
                        select(
                            func.count().label("commits"),
                            func.count(Commit.contributor_id.distinct()).label("contributors"),
                            func.coalesce(func.sum(Commit.lines_added), 0).label("la"),
                            func.coalesce(func.sum(Commit.lines_deleted), 0).label("ld"),
                            func.min(Commit.authored_at).label("first"),
                            func.max(Commit.authored_at).label("last"),
                        )
                        .join(Repository, Repository.id == Commit.repository_id)
                        .where(Commit.id.in_(select(cids.c.commit_id))),
                        project_col=Repository.project_id,
                        contributor_col=Commit.contributor_id,
                    )
                )).one()

            sa = await _stats(branch_a)
            if sa is None:
                return f"Branch '{branch_a}' not found in '{repo.name}'."
            sb = await _stats(branch_b)
            if sb is None:
                return f"Branch '{branch_b}' not found in '{repo.name}'."
            return _table(
                ["Metric", branch_a, branch_b],
                [
                    ("Commits", sa.commits, sb.commits),
                    ("Contributors", sa.contributors, sb.contributors),
                    ("Lines Added", sa.la, sb.la),
                    ("Lines Deleted", sa.ld, sb.ld),
                    ("First Commit", str(sa.first)[:10] if sa.first else "—", str(sb.first)[:10] if sb.first else "—"),
                    ("Last Commit", str(sa.last)[:10] if sa.last else "—", str(sb.last)[:10] if sb.last else "—"),
                ],
            )
        return await _safe(db, _impl())

    @tool
    async def get_data_freshness(
        project_name: Optional[str] = None,
        repo_name: Optional[str] = None,
    ) -> str:
        """Check how current the synced data is for a project or repository.
        Helps caveat answers when data might be stale.

        Args:
            project_name: Optional project name.
            repo_name: Optional repository name.
        """
        async def _impl():
            if repo_name:
                repo = await _resolve_repository(db, repo_name, project_name)
                if not repo:
                    return f"No repository found matching '{repo_name}'."
                repos = [repo]
            elif project_name:
                project = await _resolve_project(db, project_name)
                if not project:
                    return f"No project found matching '{project_name}'."
                repos = (await db.execute(
                    scoped_query(
                        select(Repository).where(Repository.project_id == project.id).order_by(Repository.name),
                        project_col=Repository.project_id,
                    )
                )).scalars().all()
            else:
                return "Please specify a project_name or repo_name."

            rows = []
            for r in repos:
                last_commit = await db.scalar(
                    scoped_query(
                        select(func.max(Commit.authored_at))
                        .join(Repository, Repository.id == Commit.repository_id)
                        .where(Commit.repository_id == r.id),
                        project_col=Repository.project_id,
                        contributor_col=Commit.contributor_id,
                    )
                )
                sync_row = (await db.execute(
                    select(SyncJob.status, SyncJob.finished_at)
                    .where(SyncJob.repository_id == r.id)
                    .order_by(SyncJob.created_at.desc()).limit(1)
                )).first()
                sync_status = sync_row.status if sync_row else "never"
                sync_time = str(sync_row.finished_at)[:16] if sync_row and sync_row.finished_at else "—"
                rows.append((
                    r.name,
                    str(r.last_synced_at)[:16] if r.last_synced_at else "Never",
                    sync_status, sync_time,
                    str(last_commit)[:16] if last_commit else "—",
                ))
            return _table(["Repository", "Last Synced", "Sync Status", "Sync Finished", "Latest Commit"], rows)
        return await _safe(db, _impl())

    @tool
    async def list_pull_requests(project_name: str, state: str = "all", limit: int = 20) -> str:
        """Search and filter pull requests across project repositories.

        Args:
            project_name: Project name (fuzzy match).
            state: Filter by state: open, merged, closed, or all.
            limit: Max results to return (default 20).
        """
        async def _impl():
            result = await db.execute(
                select(Project).where(Project.name.ilike(f"%{project_name}%")).limit(1)
            )
            project = result.scalar_one_or_none()
            if not project:
                return f"No project found matching '{project_name}'."

            repo_ids = scoped_query(
                select(Repository.id).where(Repository.project_id == project.id),
                project_col=Repository.project_id,
            )
            q = (
                select(PullRequest)
                .join(Repository, Repository.id == PullRequest.repository_id)
                .where(PullRequest.repository_id.in_(repo_ids))
                .options(
                    __import__("sqlalchemy.orm", fromlist=["selectinload"]).selectinload(PullRequest.repository),
                    __import__("sqlalchemy.orm", fromlist=["selectinload"]).selectinload(PullRequest.contributor),
                )
            )
            if state and state != "all":
                state_map = {"open": PRState.OPEN, "merged": PRState.MERGED, "closed": PRState.CLOSED}
                if state in state_map:
                    q = q.where(PullRequest.state == state_map[state])
            q = scoped_query(
                q,
                project_col=Repository.project_id,
                contributor_col=PullRequest.contributor_id,
            )
            q = q.order_by(PullRequest.created_at.desc()).limit(min(int(limit), 50))

            pr_result = await db.execute(q)
            prs = pr_result.scalars().unique().all()

            if not prs:
                return f"No PRs found in '{project_name}' with state='{state}'."

            rows = []
            for p in prs:
                ct = ""
                if p.merged_at and p.created_at:
                    hours = (p.merged_at.timestamp() - p.created_at.timestamp()) / 3600
                    ct = f"{hours:.1f}h"
                rows.append((
                    f"#{p.platform_pr_id}",
                    (p.title or "")[:60],
                    p.state.value,
                    p.repository.name if p.repository else "",
                    p.contributor.canonical_name if p.contributor else "",
                    f"+{p.lines_added}/-{p.lines_deleted}",
                    ct,
                ))
            header = f"**{project.name}** — {len(prs)} PR(s) ({state})\n\n"
            return header + _table(["#", "Title", "State", "Repo", "Author", "+/-", "Cycle"], rows)
        return await _safe(db, _impl())

    return [
        find_project,
        find_contributor,
        find_repository,
        get_project_overview,
        get_top_contributors_tool,
        get_contributor_profile,
        get_repository_overview,
        get_pr_activity,
        get_contribution_trends,
        get_code_hotspots,
        get_pr_review_cycle,
        get_reviewer_leaderboard,
        get_review_network,
        get_pr_size_analysis,
        get_contributor_pr_summary,
        get_file_ownership,
        get_contributor_file_focus,
        get_file_collaboration,
        compare_contributors,
        get_work_patterns,
        get_contributor_cross_repo,
        get_inactive_contributors,
        list_pull_requests,
        get_branch_summary,
        get_branch_comparison,
        get_data_freshness,
    ]


# Auto-register when this module is imported
register_tool_category(CATEGORY, DEFINITIONS, _build_contribution_tools, concurrency_safe=True)
