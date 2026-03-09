import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import get_db
from app.db.models import Project, Repository, User, Commit, DailyContributorStats, PullRequest, Review
from app.db.models.pull_request import PRState
from app.auth.dependencies import get_current_user
from app.services.metrics import get_trends, get_bus_factor

router = APIRouter(prefix="/projects", tags=["projects"])


def _compute_gini(values: list[int]) -> float:
    if not values or sum(values) == 0:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    cumulative = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(sorted_vals))
    return round(cumulative / (n * sum(sorted_vals)), 2)


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    platform_credential_id: uuid.UUID | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    platform_credential_id: uuid.UUID | None = None


class RepoSummary(BaseModel):
    id: uuid.UUID
    name: str
    ssh_url: str | None
    clone_url: str | None
    platform: str
    platform_owner: str | None
    platform_repo: str | None
    default_branch: str
    ssh_credential_id: uuid.UUID | None
    last_synced_at: datetime | None
    model_config = {"from_attributes": True}


class ContributorSummary(BaseModel):
    id: uuid.UUID
    canonical_name: str
    canonical_email: str
    model_config = {"from_attributes": True}


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    platform_credential_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class ProjectDetailResponse(ProjectResponse):
    repositories: list[RepoSummary] = []
    contributors: list[ContributorSummary] = []


@router.get("", response_model=list[ProjectResponse])
async def list_projects(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(select(Project).order_by(Project.name))
    return result.scalars().all()


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    existing = await db.execute(select(Project).where(Project.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project name already exists")
    project = Project(name=body.name, description=body.description, platform_credential_id=body.platform_credential_id)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.repositories), selectinload(Project.contributors))
        .where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: uuid.UUID, body: ProjectUpdate, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    updates = body.model_dump(exclude_unset=True)
    if "name" in updates:
        project.name = updates["name"]
    if "description" in updates:
        project.description = updates["description"]
    if "platform_credential_id" in updates:
        project.platform_credential_id = updates["platform_credential_id"]
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    await db.delete(project)
    await db.commit()


@router.get("/{project_id}/stats")
async def get_project_stats(
    project_id: uuid.UUID,
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    repo_count = await db.scalar(select(func.count()).select_from(Repository).where(Repository.project_id == project_id))

    commit_base = select(Commit).join(Repository).where(Repository.project_id == project_id)
    if from_date:
        commit_base = commit_base.where(Commit.authored_at >= from_date)
    if to_date:
        commit_base = commit_base.where(Commit.authored_at <= to_date + timedelta(days=1))

    sub = commit_base.with_only_columns(Commit.id).subquery()
    commit_count = await db.scalar(select(func.count()).select_from(sub))
    contributor_count = await db.scalar(
        select(func.count(Commit.contributor_id.distinct())).where(Commit.id.in_(select(sub.c.id)))
    )
    trends = await get_trends(db, project_id=project_id)

    agg_q = select(
        func.coalesce(func.sum(Commit.lines_added), 0).label("la"),
        func.coalesce(func.sum(Commit.lines_deleted), 0).label("ld"),
    ).where(Commit.id.in_(select(sub.c.id)))
    agg = (await db.execute(agg_q)).one()
    churn_ratio = round(agg.ld / agg.la, 2) if agg.la > 0 else 0

    repo_ids_sub = select(Repository.id).where(Repository.project_id == project_id).subquery()
    pr_cycle_q = select(
        func.avg(func.extract("epoch", PullRequest.merged_at - PullRequest.created_at) / 3600)
    ).where(
        PullRequest.repository_id.in_(select(repo_ids_sub.c.id)),
        PullRequest.state == PRState.MERGED,
        PullRequest.merged_at.isnot(None),
    )
    pr_cycle_time_hours = round(await db.scalar(pr_cycle_q) or 0, 1)

    first_review_sub = (
        select(
            Review.pull_request_id,
            func.min(Review.submitted_at).label("first_review"),
        )
        .group_by(Review.pull_request_id)
        .subquery()
    )
    pr_review_q = select(
        func.avg(func.extract("epoch", first_review_sub.c.first_review - PullRequest.created_at) / 3600)
    ).join(
        first_review_sub, first_review_sub.c.pull_request_id == PullRequest.id
    ).where(
        PullRequest.repository_id.in_(select(repo_ids_sub.c.id)),
    )
    pr_review_turnaround_hours = round(await db.scalar(pr_review_q) or 0, 1)

    contrib_counts_q = (
        select(Commit.contributor_id, func.count().label("cnt"))
        .where(
            Commit.id.in_(select(sub.c.id)),
            Commit.contributor_id.isnot(None),
        )
        .group_by(Commit.contributor_id)
    )
    contrib_rows = (await db.execute(contrib_counts_q)).all()
    contribution_gini = _compute_gini([r.cnt for r in contrib_rows])

    return {
        "repository_count": repo_count,
        "total_commits": commit_count,
        "contributor_count": contributor_count,
        "churn_ratio": churn_ratio,
        "pr_cycle_time_hours": pr_cycle_time_hours,
        "pr_review_turnaround_hours": pr_review_turnaround_hours,
        "contribution_gini": contribution_gini,
        "trends": trends,
    }


class PRStatItem(BaseModel):
    id: uuid.UUID
    title: str | None
    state: str
    repository_id: uuid.UUID
    contributor_id: uuid.UUID | None
    created_at: datetime
    merged_at: datetime | None
    cycle_time_hours: float | None
    review_turnaround_hours: float | None


@router.get("/{project_id}/pr-stats", response_model=list[PRStatItem])
async def get_project_pr_stats(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    repo_ids_sub = select(Repository.id).where(Repository.project_id == project_id).subquery()

    first_review = (
        select(
            Review.pull_request_id,
            func.min(Review.submitted_at).label("first_review"),
        )
        .group_by(Review.pull_request_id)
        .subquery()
    )

    q = (
        select(
            PullRequest,
            first_review.c.first_review,
        )
        .outerjoin(first_review, first_review.c.pull_request_id == PullRequest.id)
        .where(PullRequest.repository_id.in_(select(repo_ids_sub.c.id)))
        .order_by(PullRequest.created_at.desc())
        .limit(200)
    )

    rows = (await db.execute(q)).all()
    items = []
    for pr, fr in rows:
        cycle = None
        if pr.merged_at:
            cycle = round((pr.merged_at - pr.created_at).total_seconds() / 3600, 1)
        review_ta = None
        if fr:
            review_ta = round((fr - pr.created_at).total_seconds() / 3600, 1)
        items.append(PRStatItem(
            id=pr.id,
            title=pr.title,
            state=pr.state.value,
            repository_id=pr.repository_id,
            contributor_id=pr.contributor_id,
            created_at=pr.created_at,
            merged_at=pr.merged_at,
            cycle_time_hours=cycle,
            review_turnaround_hours=review_ta,
        ))
    return items
