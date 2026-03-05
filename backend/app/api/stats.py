import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models import User
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
