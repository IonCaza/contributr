import uuid
from datetime import date, timedelta

from sqlalchemy import select, func, case, text, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Commit, DailyContributorStats, PullRequest, Review, Contributor, Branch
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

    rows = commit_stats.all()
    for row in rows:
        stat = DailyContributorStats(
            contributor_id=row.contributor_id,
            repository_id=repository_id,
            date=row.day.date() if hasattr(row.day, "date") else row.day,
            commits=row.commits,
            lines_added=row.lines_added or 0,
            lines_deleted=row.lines_deleted or 0,
            files_changed=row.files_changed or 0,
            merges=row.merges or 0,
        )
        db.add(stat)

    await db.flush()
    return len(rows)


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


async def get_daily_stats(
    db: AsyncSession,
    from_date: date,
    to_date: date,
    contributor_id: uuid.UUID | None = None,
    repository_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    branch_names: list[str] | None = None,
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
    if project_id:
        from app.db.models import Repository
        query = query.join(Repository, Repository.id == DailyContributorStats.repository_id).where(
            Repository.project_id == project_id
        )

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
    if project_id:
        from app.db.models import Repository
        base = base.join(Repository, Repository.id == DailyContributorStats.repository_id).where(
            Repository.project_id == project_id
        )

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
    if project_id:
        from app.db.models import Repository
        base = base.join(Repository, Repository.id == DailyContributorStats.repository_id).where(
            Repository.project_id == project_id
        )

    base = base.group_by(text("month"), DailyContributorStats.contributor_id).order_by(text("month"))
    result = await db.execute(base)
    return [row._asdict() for row in result.all()]


async def get_trends(
    db: AsyncSession,
    contributor_id: uuid.UUID | None = None,
    repository_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    branch_names: list[str] | None = None,
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
            if project_id:
                from app.db.models import Repository
                q = q.join(Repository, Repository.id == DailyContributorStats.repository_id).where(
                    Repository.project_id == project_id
                )
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
