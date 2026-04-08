import uuid
from datetime import date, timedelta
from typing import Sequence

from sqlalchemy import select, func, case, text, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Commit, DailyContributorStats, PullRequest, Review, Contributor, Branch, Repository
from app.db.models.branch import commit_branches
from app.db.models.pull_request import PRState
from app.db.models.project import project_contributors


async def rebuild_daily_stats(db: AsyncSession, repository_id: uuid.UUID) -> int:
    """Rebuild DailyContributorStats for a repository from raw commits, PRs, reviews."""
    await db.execute(
        text("DELETE FROM daily_contributor_stats WHERE repository_id = :rid"),
        {"rid": repository_id},
    )

    commit_stats = await db.execute(
        select(
            Commit.contributor_id,
            func.date_trunc("day", Commit.authored_at).label("day"),
            func.count().label("commits"),
            func.sum(Commit.lines_added).label("lines_added"),
            func.sum(Commit.lines_deleted).label("lines_deleted"),
            func.sum(Commit.files_changed).label("files_changed"),
            func.sum(case((Commit.is_merge, 1), else_=0)).label("merges"),
        )
        .where(Commit.repository_id == repository_id)
        .group_by(Commit.contributor_id, text("day"))
    )

    stats_map: dict[tuple, DailyContributorStats] = {}

    rows = commit_stats.all()
    for row in rows:
        d = row.day.date() if hasattr(row.day, "date") else row.day
        key = (row.contributor_id, d)
        stat = DailyContributorStats(
            contributor_id=row.contributor_id,
            repository_id=repository_id,
            date=d,
            commits=row.commits,
            lines_added=row.lines_added or 0,
            lines_deleted=row.lines_deleted or 0,
            files_changed=row.files_changed or 0,
            merges=row.merges or 0,
        )
        stats_map[key] = stat
        db.add(stat)

    prs_opened_q = await db.execute(
        select(
            PullRequest.contributor_id,
            func.date_trunc("day", PullRequest.created_at).label("day"),
            func.count().label("cnt"),
        )
        .where(PullRequest.repository_id == repository_id, PullRequest.contributor_id.isnot(None))
        .group_by(PullRequest.contributor_id, text("day"))
    )
    for row in prs_opened_q.all():
        d = row.day.date() if hasattr(row.day, "date") else row.day
        key = (row.contributor_id, d)
        if key in stats_map:
            stats_map[key].prs_opened = row.cnt
        else:
            stat = DailyContributorStats(
                contributor_id=row.contributor_id, repository_id=repository_id,
                date=d, prs_opened=row.cnt,
            )
            stats_map[key] = stat
            db.add(stat)

    prs_merged_q = await db.execute(
        select(
            PullRequest.contributor_id,
            func.date_trunc("day", PullRequest.merged_at).label("day"),
            func.count().label("cnt"),
        )
        .where(
            PullRequest.repository_id == repository_id,
            PullRequest.contributor_id.isnot(None),
            PullRequest.state == PRState.MERGED,
            PullRequest.merged_at.isnot(None),
        )
        .group_by(PullRequest.contributor_id, text("day"))
    )
    for row in prs_merged_q.all():
        d = row.day.date() if hasattr(row.day, "date") else row.day
        key = (row.contributor_id, d)
        if key in stats_map:
            stats_map[key].prs_merged = row.cnt
        else:
            stat = DailyContributorStats(
                contributor_id=row.contributor_id, repository_id=repository_id,
                date=d, prs_merged=row.cnt,
            )
            stats_map[key] = stat
            db.add(stat)

    reviews_q = await db.execute(
        select(
            Review.reviewer_id,
            func.date_trunc("day", Review.submitted_at).label("day"),
            func.count().label("cnt"),
            func.coalesce(func.sum(Review.comment_count), 0).label("comments"),
        )
        .join(PullRequest, PullRequest.id == Review.pull_request_id)
        .where(PullRequest.repository_id == repository_id, Review.reviewer_id.isnot(None))
        .group_by(Review.reviewer_id, text("day"))
    )
    for row in reviews_q.all():
        d = row.day.date() if hasattr(row.day, "date") else row.day
        key = (row.reviewer_id, d)
        if key in stats_map:
            stats_map[key].reviews_given = row.cnt
            stats_map[key].pr_comments = row.comments
        else:
            stat = DailyContributorStats(
                contributor_id=row.reviewer_id, repository_id=repository_id,
                date=d, reviews_given=row.cnt, pr_comments=row.comments,
            )
            stats_map[key] = stat
            db.add(stat)

    await db.flush()
    return len(stats_map)


async def _daily_stats_from_commits(
    db: AsyncSession,
    from_date: date,
    to_date: date,
    branch_names: list[str],
    contributor_id: uuid.UUID | None = None,
    repository_id: uuid.UUID | None = None,
) -> list[dict]:
    """Compute daily stats on-the-fly from raw commits filtered by branch."""
    q = select(
        func.date_trunc("day", Commit.authored_at).label("date"),
        Commit.contributor_id,
        Commit.repository_id,
        func.count().label("commits"),
        func.sum(Commit.lines_added).label("lines_added"),
        func.sum(Commit.lines_deleted).label("lines_deleted"),
        func.sum(Commit.files_changed).label("files_changed"),
        func.sum(case((Commit.is_merge, 1), else_=0)).label("merges"),
    ).join(
        commit_branches, commit_branches.c.commit_id == Commit.id
    ).join(
        Branch, Branch.id == commit_branches.c.branch_id
    ).where(
        Branch.name.in_(branch_names),
        Commit.authored_at >= from_date,
        Commit.authored_at <= to_date,
    )
    if contributor_id:
        q = q.where(Commit.contributor_id == contributor_id)
    if repository_id:
        q = q.where(Commit.repository_id == repository_id)
    q = q.group_by(text("date"), Commit.contributor_id, Commit.repository_id).order_by(text("date"))
    result = await db.execute(q)
    rows = []
    for r in result.all():
        d = r._asdict()
        d["prs_opened"] = 0
        d["prs_merged"] = 0
        d["reviews_given"] = 0
        rows.append(d)
    return rows


def _apply_project_scope(
    query,
    stats_repo_col,
    project_id: uuid.UUID | None,
    accessible_project_ids: set[uuid.UUID] | None,
):
    """Join through Repository to restrict by project_id or accessible set."""
    if project_id:
        query = query.join(Repository, Repository.id == stats_repo_col).where(
            Repository.project_id == project_id
        )
    elif accessible_project_ids is not None:
        query = query.join(Repository, Repository.id == stats_repo_col).where(
            Repository.project_id.in_(accessible_project_ids)
        )
    return query


async def get_daily_stats(
    db: AsyncSession,
    from_date: date,
    to_date: date,
    contributor_id: uuid.UUID | None = None,
    repository_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    branch_names: list[str] | None = None,
    accessible_project_ids: set[uuid.UUID] | None = None,
) -> list[dict]:
    if branch_names:
        return await _daily_stats_from_commits(
            db, from_date, to_date, branch_names, contributor_id, repository_id
        )

    query = select(
        DailyContributorStats.date,
        DailyContributorStats.contributor_id,
        DailyContributorStats.repository_id,
        DailyContributorStats.commits,
        DailyContributorStats.lines_added,
        DailyContributorStats.lines_deleted,
        DailyContributorStats.files_changed,
        DailyContributorStats.merges,
        DailyContributorStats.prs_opened,
        DailyContributorStats.prs_merged,
        DailyContributorStats.reviews_given,
    ).where(
        DailyContributorStats.date >= from_date,
        DailyContributorStats.date <= to_date,
    )

    if contributor_id:
        query = query.where(DailyContributorStats.contributor_id == contributor_id)
    if repository_id:
        query = query.where(DailyContributorStats.repository_id == repository_id)
    query = _apply_project_scope(query, DailyContributorStats.repository_id, project_id, accessible_project_ids)

    query = query.order_by(DailyContributorStats.date)
    result = await db.execute(query)
    return [row._asdict() for row in result.all()]


async def get_weekly_stats(
    db: AsyncSession,
    from_date: date,
    to_date: date,
    contributor_id: uuid.UUID | None = None,
    repository_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    accessible_project_ids: set[uuid.UUID] | None = None,
) -> list[dict]:
    base = select(
        func.date_trunc("week", DailyContributorStats.date).label("week"),
        DailyContributorStats.contributor_id,
        func.sum(DailyContributorStats.commits).label("commits"),
        func.sum(DailyContributorStats.lines_added).label("lines_added"),
        func.sum(DailyContributorStats.lines_deleted).label("lines_deleted"),
        func.sum(DailyContributorStats.files_changed).label("files_changed"),
        func.sum(DailyContributorStats.merges).label("merges"),
        func.sum(DailyContributorStats.prs_opened).label("prs_opened"),
        func.sum(DailyContributorStats.prs_merged).label("prs_merged"),
        func.sum(DailyContributorStats.reviews_given).label("reviews_given"),
    ).where(
        DailyContributorStats.date >= from_date,
        DailyContributorStats.date <= to_date,
    )

    if contributor_id:
        base = base.where(DailyContributorStats.contributor_id == contributor_id)
    if repository_id:
        base = base.where(DailyContributorStats.repository_id == repository_id)
    base = _apply_project_scope(base, DailyContributorStats.repository_id, project_id, accessible_project_ids)

    base = base.group_by(text("week"), DailyContributorStats.contributor_id).order_by(text("week"))
    result = await db.execute(base)
    return [row._asdict() for row in result.all()]


async def get_monthly_stats(
    db: AsyncSession,
    from_date: date,
    to_date: date,
    contributor_id: uuid.UUID | None = None,
    repository_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    accessible_project_ids: set[uuid.UUID] | None = None,
) -> list[dict]:
    base = select(
        func.date_trunc("month", DailyContributorStats.date).label("month"),
        DailyContributorStats.contributor_id,
        func.sum(DailyContributorStats.commits).label("commits"),
        func.sum(DailyContributorStats.lines_added).label("lines_added"),
        func.sum(DailyContributorStats.lines_deleted).label("lines_deleted"),
        func.sum(DailyContributorStats.files_changed).label("files_changed"),
        func.sum(DailyContributorStats.merges).label("merges"),
        func.sum(DailyContributorStats.prs_opened).label("prs_opened"),
        func.sum(DailyContributorStats.prs_merged).label("prs_merged"),
        func.sum(DailyContributorStats.reviews_given).label("reviews_given"),
    ).where(
        DailyContributorStats.date >= from_date,
        DailyContributorStats.date <= to_date,
    )

    if contributor_id:
        base = base.where(DailyContributorStats.contributor_id == contributor_id)
    if repository_id:
        base = base.where(DailyContributorStats.repository_id == repository_id)
    base = _apply_project_scope(base, DailyContributorStats.repository_id, project_id, accessible_project_ids)

    base = base.group_by(text("month"), DailyContributorStats.contributor_id).order_by(text("month"))
    result = await db.execute(base)
    return [row._asdict() for row in result.all()]


async def get_trends(
    db: AsyncSession,
    contributor_id: uuid.UUID | None = None,
    repository_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    branch_names: list[str] | None = None,
    accessible_project_ids: set[uuid.UUID] | None = None,
) -> dict:
    """Compute 7-day and 30-day rolling averages and week-over-week deltas."""
    today = date.today()
    last_7 = today - timedelta(days=7)
    prev_7 = last_7 - timedelta(days=7)
    last_30 = today - timedelta(days=30)

    async def _sum_range(start: date, end: date) -> dict:
        if branch_names:
            q = select(
                func.coalesce(func.count(), 0).label("commits"),
                func.coalesce(func.sum(Commit.lines_added), 0).label("lines_added"),
                func.coalesce(func.sum(Commit.lines_deleted), 0).label("lines_deleted"),
            ).join(
                commit_branches, commit_branches.c.commit_id == Commit.id
            ).join(
                Branch, Branch.id == commit_branches.c.branch_id
            ).where(
                Branch.name.in_(branch_names),
                Commit.authored_at >= start,
                Commit.authored_at <= end,
            )
            if contributor_id:
                q = q.where(Commit.contributor_id == contributor_id)
            if repository_id:
                q = q.where(Commit.repository_id == repository_id)
        else:
            q = select(
                func.coalesce(func.sum(DailyContributorStats.commits), 0).label("commits"),
                func.coalesce(func.sum(DailyContributorStats.lines_added), 0).label("lines_added"),
                func.coalesce(func.sum(DailyContributorStats.lines_deleted), 0).label("lines_deleted"),
            ).where(
                DailyContributorStats.date >= start,
                DailyContributorStats.date <= end,
            )
            if contributor_id:
                q = q.where(DailyContributorStats.contributor_id == contributor_id)
            if repository_id:
                q = q.where(DailyContributorStats.repository_id == repository_id)
            q = _apply_project_scope(q, DailyContributorStats.repository_id, project_id, accessible_project_ids)
        row = (await db.execute(q)).one()
        return row._asdict()

    current_week = await _sum_range(last_7, today)
    previous_week = await _sum_range(prev_7, last_7 - timedelta(days=1))
    last_30_totals = await _sum_range(last_30, today)

    def _delta(current: int, previous: int) -> float:
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 1)

    return {
        "avg_commits_7d": round(current_week["commits"] / 7, 2),
        "avg_commits_30d": round(last_30_totals["commits"] / 30, 2),
        "avg_lines_7d": round((current_week["lines_added"] + current_week["lines_deleted"]) / 7, 2),
        "avg_lines_30d": round((last_30_totals["lines_added"] + last_30_totals["lines_deleted"]) / 30, 2),
        "wow_commits_delta": _delta(current_week["commits"], previous_week["commits"]),
        "wow_lines_delta": _delta(
            current_week["lines_added"] + current_week["lines_deleted"],
            previous_week["lines_added"] + previous_week["lines_deleted"],
        ),
        "current_week": current_week,
        "previous_week": previous_week,
    }


async def get_bus_factor(db: AsyncSession, repository_id: uuid.UUID, days: int = 90, branch_names: list[str] | None = None) -> int:
    """Minimum number of contributors responsible for 50%+ of recent commits."""
    since = date.today() - timedelta(days=days)

    if branch_names:
        result = await db.execute(
            select(
                Commit.contributor_id,
                func.count().label("total"),
            )
            .join(commit_branches, commit_branches.c.commit_id == Commit.id)
            .join(Branch, Branch.id == commit_branches.c.branch_id)
            .where(
                Commit.repository_id == repository_id,
                Branch.name.in_(branch_names),
                Commit.authored_at >= since,
            )
            .group_by(Commit.contributor_id)
            .order_by(text("total DESC"))
        )
    else:
        result = await db.execute(
            select(
                DailyContributorStats.contributor_id,
                func.sum(DailyContributorStats.commits).label("total"),
            )
            .where(
                DailyContributorStats.repository_id == repository_id,
                DailyContributorStats.date >= since,
            )
            .group_by(DailyContributorStats.contributor_id)
            .order_by(text("total DESC"))
        )
    rows = result.all()
    total = sum(r.total for r in rows)
    if total == 0:
        return 0

    cumulative = 0
    for i, row in enumerate(rows, 1):
        cumulative += row.total
        if cumulative >= total * 0.5:
            return i
    return len(rows)


async def get_top_contributors(
    db: AsyncSession,
    *,
    project_id: uuid.UUID | None = None,
    repository_id: uuid.UUID | None = None,
    metric: str = "commits",
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = 10,
) -> list[dict]:
    """Rank contributors by a configurable metric within a project or repository scope."""
    valid_metrics = {
        "commits", "lines_added", "lines_deleted", "files_changed",
        "prs_opened", "prs_merged", "reviews_given",
    }
    if metric not in valid_metrics:
        metric = "commits"

    metric_col = getattr(DailyContributorStats, metric)

    stmt = (
        select(
            Contributor.canonical_name,
            Contributor.canonical_email,
            func.sum(metric_col).label("metric_value"),
            func.sum(DailyContributorStats.commits).label("commits"),
            func.sum(DailyContributorStats.lines_added).label("lines_added"),
            func.sum(DailyContributorStats.lines_deleted).label("lines_deleted"),
            func.sum(DailyContributorStats.prs_opened).label("prs_opened"),
            func.sum(DailyContributorStats.prs_merged).label("prs_merged"),
            func.sum(DailyContributorStats.reviews_given).label("reviews_given"),
        )
        .join(Contributor, Contributor.id == DailyContributorStats.contributor_id)
        .group_by(Contributor.id, Contributor.canonical_name, Contributor.canonical_email)
        .order_by(func.sum(metric_col).desc())
        .limit(limit)
    )

    from app.db.models import Repository
    filters = []
    if project_id:
        stmt = stmt.join(Repository, Repository.id == DailyContributorStats.repository_id)
        filters.append(Repository.project_id == project_id)
    if repository_id:
        filters.append(DailyContributorStats.repository_id == repository_id)
    if from_date:
        filters.append(DailyContributorStats.date >= from_date)
    if to_date:
        filters.append(DailyContributorStats.date <= to_date)
    if filters:
        stmt = stmt.where(and_(*filters))

    result = await db.execute(stmt)
    return [row._asdict() for row in result.all()]


# ---------------------------------------------------------------------------
# Team-scoped code analytics
# ---------------------------------------------------------------------------


async def get_team_code_stats(
    db: AsyncSession,
    project_id: uuid.UUID,
    contributor_ids: Sequence[uuid.UUID],
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict:
    """Aggregated code stats for a set of contributors within a project."""
    if not contributor_ids:
        return {
            "total_commits": 0, "lines_added": 0, "lines_deleted": 0,
            "files_changed": 0, "prs_opened": 0, "prs_merged": 0,
            "reviews_given": 0, "active_repos": 0, "avg_commit_size": 0,
        }

    dcs = DailyContributorStats
    filters = [
        dcs.contributor_id.in_(contributor_ids),
    ]
    stmt = (
        select(
            func.coalesce(func.sum(dcs.commits), 0).label("total_commits"),
            func.coalesce(func.sum(dcs.lines_added), 0).label("lines_added"),
            func.coalesce(func.sum(dcs.lines_deleted), 0).label("lines_deleted"),
            func.coalesce(func.sum(dcs.files_changed), 0).label("files_changed"),
            func.coalesce(func.sum(dcs.prs_opened), 0).label("prs_opened"),
            func.coalesce(func.sum(dcs.prs_merged), 0).label("prs_merged"),
            func.coalesce(func.sum(dcs.reviews_given), 0).label("reviews_given"),
            func.count(func.distinct(dcs.repository_id)).label("active_repos"),
        )
        .join(Repository, Repository.id == dcs.repository_id)
        .where(Repository.project_id == project_id, *filters)
    )
    if from_date:
        stmt = stmt.where(dcs.date >= from_date)
    if to_date:
        stmt = stmt.where(dcs.date <= to_date)

    row = (await db.execute(stmt)).one()
    total_commits = int(row.total_commits)
    lines = int(row.lines_added) + int(row.lines_deleted)

    return {
        "total_commits": total_commits,
        "lines_added": int(row.lines_added),
        "lines_deleted": int(row.lines_deleted),
        "files_changed": int(row.files_changed),
        "prs_opened": int(row.prs_opened),
        "prs_merged": int(row.prs_merged),
        "reviews_given": int(row.reviews_given),
        "active_repos": int(row.active_repos),
        "avg_commit_size": round(lines / total_commits, 1) if total_commits > 0 else 0,
    }


async def get_team_code_activity(
    db: AsyncSession,
    project_id: uuid.UUID,
    contributor_ids: Sequence[uuid.UUID],
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[dict]:
    """Daily aggregated code activity for a team (time series)."""
    if not contributor_ids:
        return []

    dcs = DailyContributorStats
    filters = [dcs.contributor_id.in_(contributor_ids)]
    stmt = (
        select(
            dcs.date.label("date"),
            func.sum(dcs.commits).label("commits"),
            func.sum(dcs.lines_added).label("lines_added"),
            func.sum(dcs.lines_deleted).label("lines_deleted"),
        )
        .join(Repository, Repository.id == dcs.repository_id)
        .where(Repository.project_id == project_id, *filters)
        .group_by(dcs.date)
        .order_by(dcs.date)
    )
    if from_date:
        stmt = stmt.where(dcs.date >= from_date)
    if to_date:
        stmt = stmt.where(dcs.date <= to_date)

    rows = (await db.execute(stmt)).all()
    return [
        {
            "date": str(r.date),
            "commits": int(r.commits or 0),
            "lines_added": int(r.lines_added or 0),
            "lines_deleted": int(r.lines_deleted or 0),
        }
        for r in rows
    ]


async def get_team_member_stats(
    db: AsyncSession,
    project_id: uuid.UUID,
    contributor_ids: Sequence[uuid.UUID],
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[dict]:
    """Per-member code stats breakdown for ranking within a team."""
    if not contributor_ids:
        return []

    dcs = DailyContributorStats
    stmt = (
        select(
            Contributor.id.label("id"),
            Contributor.canonical_name.label("name"),
            func.coalesce(func.sum(dcs.commits), 0).label("commits"),
            func.coalesce(func.sum(dcs.lines_added), 0).label("lines_added"),
            func.coalesce(func.sum(dcs.lines_deleted), 0).label("lines_deleted"),
            func.coalesce(func.sum(dcs.prs_opened), 0).label("prs_opened"),
            func.coalesce(func.sum(dcs.prs_merged), 0).label("prs_merged"),
            func.coalesce(func.sum(dcs.reviews_given), 0).label("reviews_given"),
        )
        .join(dcs, dcs.contributor_id == Contributor.id)
        .join(Repository, Repository.id == dcs.repository_id)
        .where(
            Contributor.id.in_(contributor_ids),
            Repository.project_id == project_id,
        )
        .group_by(Contributor.id, Contributor.canonical_name)
        .order_by(func.sum(dcs.commits).desc())
    )
    if from_date:
        stmt = stmt.where(dcs.date >= from_date)
    if to_date:
        stmt = stmt.where(dcs.date <= to_date)

    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "commits": int(r.commits),
            "lines_added": int(r.lines_added),
            "lines_deleted": int(r.lines_deleted),
            "prs_opened": int(r.prs_opened),
            "prs_merged": int(r.prs_merged),
            "reviews_given": int(r.reviews_given),
        }
        for r in rows
    ]
