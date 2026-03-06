from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from langchain_core.tools import tool
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Project, Repository, Contributor, Commit, PullRequest,
    Review, DailyContributorStats, CommitFile,
)
from app.db.models.project import project_contributors
from app.db.models.pull_request import PRState
from app.services.metrics import get_trends, get_bus_factor, get_top_contributors

logger = logging.getLogger(__name__)


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
        select(Contributor).where(
            Contributor.canonical_name.ilike(f"%{name_or_email}%")
            | Contributor.canonical_email.ilike(f"%{name_or_email}%")
        ).order_by(Contributor.canonical_name).limit(1)
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
    result = await db.execute(stmt.order_by(Repository.name).limit(1))
    return result.scalar_one_or_none()


def _parse_date(val: str | None) -> date | None:
    if not val:
        return None
    return date.fromisoformat(val)


# ── Transaction isolation ─────────────────────────────────────────────


async def _safe(db: AsyncSession, coro):
    """Run a coroutine inside a SAVEPOINT so failures don't poison the session."""
    try:
        async with db.begin_nested():
            return await coro
    except Exception as e:
        logger.warning("Tool query failed: %s", e)
        return f"Error: {e}"


# ── Shared utilities ──────────────────────────────────────────────────


def _compute_gini(values: list[int]) -> float:
    if not values or sum(values) == 0:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    cumulative = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(sorted_vals))
    return round(cumulative / (n * sum(sorted_vals)), 2)


# ── Tool builder ──────────────────────────────────────────────────────


class ServiceTools:
    """Builds LangChain tools backed by service-layer logic with name resolution."""

    def __init__(self, db: AsyncSession):
        self._db = db

    def get_tools(self) -> list:
        return [
            self._make_find_project(),
            self._make_find_contributor(),
            self._make_find_repository(),
            self._make_get_project_overview(),
            self._make_get_top_contributors(),
            self._make_get_contributor_profile(),
            self._make_get_repository_overview(),
            self._make_get_pr_activity(),
            self._make_get_contribution_trends(),
            self._make_get_code_hotspots(),
        ]

    # ── Tier 1: Lookup / Discovery ────────────────────────────────────

    def _make_find_project(self):
        db = self._db

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
                stmt = (
                    select(Project.name, Project.description, repo_count, contrib_count)
                    .outerjoin(Repository, Repository.project_id == Project.id)
                    .where(Project.name.ilike(f"%{name}%"))
                    .group_by(Project.id)
                    .order_by(Project.name)
                    .limit(10)
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

        return find_project

    def _make_find_contributor(self):
        db = self._db

        @tool
        async def find_contributor(name_or_email: str) -> str:
            """Search for a contributor by name or email address.
            Use this tool when you need to identify a specific contributor.

            Args:
                name_or_email: Name or email (partial match, case-insensitive).
            """
            async def _impl():
                stmt = (
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
                    .limit(10)
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

        return find_contributor

    def _make_find_repository(self):
        db = self._db

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

        return find_repository

    # ── Tier 2: Analytics ─────────────────────────────────────────────

    def _make_get_project_overview(self):
        db = self._db

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
                    select(func.count()).select_from(Repository)
                    .where(Repository.project_id == project.id)
                )

                commit_q = (
                    select(Commit)
                    .join(Repository)
                    .where(Repository.project_id == project.id)
                )
                if fd:
                    commit_q = commit_q.where(Commit.authored_at >= fd)
                if td:
                    commit_q = commit_q.where(Commit.authored_at <= td + timedelta(days=1))
                sub = commit_q.with_only_columns(Commit.id).subquery()

                total_commits = await db.scalar(select(func.count()).select_from(sub))
                contributor_count = await db.scalar(
                    select(func.count(Commit.contributor_id.distinct()))
                    .where(Commit.id.in_(select(sub.c.id)))
                )

                agg = (await db.execute(
                    select(
                        func.coalesce(func.sum(Commit.lines_added), 0).label("la"),
                        func.coalesce(func.sum(Commit.lines_deleted), 0).label("ld"),
                    ).where(Commit.id.in_(select(sub.c.id)))
                )).one()
                churn = round(agg.ld / agg.la, 2) if agg.la > 0 else 0

                repo_ids = (
                    select(Repository.id)
                    .where(Repository.project_id == project.id)
                    .subquery()
                )
                pr_cycle = await db.scalar(
                    select(
                        func.avg(func.extract("epoch", PullRequest.merged_at - PullRequest.created_at) / 3600)
                    ).where(
                        PullRequest.repository_id.in_(select(repo_ids.c.id)),
                        PullRequest.state == PRState.MERGED,
                        PullRequest.merged_at.isnot(None),
                    )
                )

                first_review = (
                    select(
                        Review.pull_request_id,
                        func.min(Review.submitted_at).label("fr"),
                    )
                    .group_by(Review.pull_request_id)
                    .subquery()
                )
                review_ta = await db.scalar(
                    select(
                        func.avg(func.extract("epoch", first_review.c.fr - PullRequest.created_at) / 3600)
                    )
                    .join(first_review, first_review.c.pull_request_id == PullRequest.id)
                    .where(PullRequest.repository_id.in_(select(repo_ids.c.id)))
                )

                contrib_counts = (await db.execute(
                    select(Commit.contributor_id, func.count().label("cnt"))
                    .where(Commit.id.in_(select(sub.c.id)))
                    .group_by(Commit.contributor_id)
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

        return get_project_overview

    def _make_get_top_contributors(self):
        db = self._db

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

        return get_top_contributors_tool

    def _make_get_contributor_profile(self):
        db = self._db

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

                commit_q = select(Commit).where(Commit.contributor_id == contributor.id)
                if fd:
                    commit_q = commit_q.where(Commit.authored_at >= fd)
                if td:
                    commit_q = commit_q.where(Commit.authored_at <= td + timedelta(days=1))
                if project_name:
                    project = await _resolve_project(db, project_name)
                    if project:
                        commit_q = commit_q.join(Repository).where(
                            Repository.project_id == project.id
                        )

                sub = commit_q.with_only_columns(Commit.id).subquery()
                total_commits = await db.scalar(select(func.count()).select_from(sub))

                agg = (await db.execute(
                    select(
                        func.coalesce(func.sum(Commit.lines_added), 0).label("la"),
                        func.coalesce(func.sum(Commit.lines_deleted), 0).label("ld"),
                        func.count(Commit.repository_id.distinct()).label("rc"),
                    ).where(Commit.id.in_(select(sub.c.id)))
                )).one()

                day_col = func.date_trunc("day", Commit.authored_at).label("d")
                streak_q = (
                    select(day_col)
                    .where(Commit.contributor_id == contributor.id)
                    .distinct()
                    .order_by(day_col.desc())
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
                    select(func.count()).select_from(PullRequest)
                    .where(PullRequest.contributor_id == contributor.id)
                ) or 0
                reviews = await db.scalar(
                    select(func.count()).select_from(Review)
                    .where(Review.reviewer_id == contributor.id)
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

        return get_contributor_profile

    def _make_get_repository_overview(self):
        db = self._db

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

                base_q = select(Commit).where(Commit.repository_id == repo.id)
                if fd:
                    base_q = base_q.where(Commit.authored_at >= fd)
                if td:
                    base_q = base_q.where(Commit.authored_at <= td + timedelta(days=1))
                sub = base_q.with_only_columns(Commit.id).subquery()

                total_commits = await db.scalar(select(func.count()).select_from(sub))
                contributor_count = await db.scalar(
                    select(func.count(Commit.contributor_id.distinct()))
                    .where(Commit.id.in_(select(sub.c.id)))
                )

                agg = (await db.execute(
                    select(
                        func.coalesce(func.sum(Commit.lines_added), 0).label("la"),
                        func.coalesce(func.sum(Commit.lines_deleted), 0).label("ld"),
                    ).where(Commit.id.in_(select(sub.c.id)))
                )).one()
                churn = round(agg.ld / agg.la, 2) if agg.la > 0 else 0

                bus = await get_bus_factor(db, repo.id)
                trends = await get_trends(db, repository_id=repo.id)

                pr_cycle = await db.scalar(
                    select(
                        func.avg(func.extract("epoch", PullRequest.merged_at - PullRequest.created_at) / 3600)
                    ).where(
                        PullRequest.repository_id == repo.id,
                        PullRequest.state == PRState.MERGED,
                        PullRequest.merged_at.isnot(None),
                    )
                )

                contrib_counts = (await db.execute(
                    select(Commit.contributor_id, func.count().label("cnt"))
                    .where(Commit.id.in_(select(sub.c.id)))
                    .group_by(Commit.contributor_id)
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

        return get_repository_overview

    def _make_get_pr_activity(self):
        db = self._db

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
                        select(Repository.id)
                        .where(Repository.project_id == project.id)
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
                    select(
                        Review.pull_request_id,
                        func.min(Review.submitted_at).label("fr"),
                    )
                    .group_by(Review.pull_request_id)
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

        return get_pr_activity

    def _make_get_contribution_trends(self):
        db = self._db

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

        return get_contribution_trends

    def _make_get_code_hotspots(self):
        db = self._db

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
                    select(
                        CommitFile.file_path,
                        func.count(CommitFile.commit_id.distinct()).label("commits"),
                        func.count(Commit.contributor_id.distinct()).label("contributors"),
                        func.sum(CommitFile.lines_added).label("la"),
                        func.sum(CommitFile.lines_deleted).label("ld"),
                    )
                    .join(Commit, Commit.id == CommitFile.commit_id)
                    .where(Commit.repository_id == repo.id)
                    .group_by(CommitFile.file_path)
                    .order_by(func.count(CommitFile.commit_id.distinct()).desc())
                    .limit(min(limit, 50))
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

        return get_code_hotspots
