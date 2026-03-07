import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models import User
from app.db.models.pull_request import PullRequest, PRState
from app.db.models.work_item import WorkItem
from app.db.models.contributor import Contributor
from app.db.models.commit import Commit
from app.auth.dependencies import get_current_user
from app.services.metrics import get_daily_stats, get_weekly_stats, get_monthly_stats, get_trends

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/daily")
async def daily_stats(
    contributor_id: uuid.UUID | None = None,
    repository_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    branch: list[str] = Query(default=[]),
    from_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    to_date: date = Query(default_factory=date.today),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await get_daily_stats(db, from_date, to_date, contributor_id, repository_id, project_id, branch_names=branch or None)


@router.get("/weekly")
async def weekly_stats(
    contributor_id: uuid.UUID | None = None,
    repository_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    from_date: date = Query(default_factory=lambda: date.today() - timedelta(days=90)),
    to_date: date = Query(default_factory=date.today),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await get_weekly_stats(db, from_date, to_date, contributor_id, repository_id, project_id)


@router.get("/monthly")
async def monthly_stats(
    contributor_id: uuid.UUID | None = None,
    repository_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    from_date: date = Query(default_factory=lambda: date.today() - timedelta(days=365)),
    to_date: date = Query(default_factory=date.today),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await get_monthly_stats(db, from_date, to_date, contributor_id, repository_id, project_id)


@router.get("/delivery-summary")
async def delivery_summary(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    today = date.today()
    last_7 = today - timedelta(days=7)
    last_30 = today - timedelta(days=30)

    active_contributors_q = select(func.count(func.distinct(Commit.contributor_id))).where(
        Commit.authored_at >= last_30,
    )
    active_contributors = (await db.execute(active_contributors_q)).scalar() or 0

    total_contributors_q = select(func.count()).select_from(Contributor)
    total_contributors = (await db.execute(total_contributors_q)).scalar() or 0

    open_prs_q = select(func.count()).select_from(PullRequest).where(PullRequest.state == PRState.OPEN)
    open_prs = (await db.execute(open_prs_q)).scalar() or 0

    merged_7d_q = select(func.count()).select_from(PullRequest).where(
        PullRequest.state == PRState.MERGED,
        PullRequest.merged_at >= last_7,
    )
    merged_7d = (await db.execute(merged_7d_q)).scalar() or 0

    prev_7 = last_7 - timedelta(days=7)
    merged_prev_7d_q = select(func.count()).select_from(PullRequest).where(
        PullRequest.state == PRState.MERGED,
        PullRequest.merged_at >= prev_7,
        PullRequest.merged_at < last_7,
    )
    merged_prev_7d = (await db.execute(merged_prev_7d_q)).scalar() or 0

    cycle_time_q = select(
        func.percentile_cont(0.5).within_group(
            extract("epoch", PullRequest.merged_at - PullRequest.created_at) / 3600
        )
    ).where(
        PullRequest.state == PRState.MERGED,
        PullRequest.merged_at >= last_30,
    )
    pr_cycle_time_hours = round((await db.execute(cycle_time_q)).scalar() or 0, 1)

    review_turnaround_q = select(
        func.percentile_cont(0.5).within_group(
            extract("epoch", PullRequest.first_review_at - PullRequest.created_at) / 3600
        )
    ).where(
        PullRequest.first_review_at.isnot(None),
        PullRequest.created_at >= last_30,
    )
    review_turnaround_hours = round((await db.execute(review_turnaround_q)).scalar() or 0, 1)

    total_wi_q = select(func.count()).select_from(WorkItem)
    total_work_items = (await db.execute(total_wi_q)).scalar() or 0

    open_states = ("New", "Active", "Committed", "In Progress", "Approved")
    open_wi_q = select(func.count()).select_from(WorkItem).where(WorkItem.state.in_(open_states))
    open_work_items = (await db.execute(open_wi_q)).scalar() or 0

    completed_30d_q = select(func.count()).select_from(WorkItem).where(
        WorkItem.resolved_at.isnot(None),
        WorkItem.resolved_at >= last_30,
    )
    completed_work_items_30d = (await db.execute(completed_30d_q)).scalar() or 0

    wi_cycle_q = select(
        func.percentile_cont(0.5).within_group(
            extract("epoch", WorkItem.resolved_at - WorkItem.activated_at) / 3600
        )
    ).where(
        WorkItem.activated_at.isnot(None),
        WorkItem.resolved_at.isnot(None),
        WorkItem.resolved_at >= last_30,
    )
    wi_cycle_time_hours = round((await db.execute(wi_cycle_q)).scalar() or 0, 1)

    def _wow_delta(current: int, previous: int) -> float:
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 1)

    return {
        "active_contributors_30d": active_contributors,
        "total_contributors": total_contributors,
        "open_prs": open_prs,
        "merged_prs_7d": merged_7d,
        "merged_prs_wow_delta": _wow_delta(merged_7d, merged_prev_7d),
        "pr_cycle_time_hours": pr_cycle_time_hours,
        "review_turnaround_hours": review_turnaround_hours,
        "total_work_items": total_work_items,
        "open_work_items": open_work_items,
        "completed_work_items_30d": completed_work_items_30d,
        "wi_cycle_time_hours": wi_cycle_time_hours,
    }


@router.get("/trends")
async def trend_stats(
    contributor_id: uuid.UUID | None = None,
    repository_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    branch: list[str] = Query(default=[]),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await get_trends(db, contributor_id, repository_id, project_id, branch_names=branch or None)
