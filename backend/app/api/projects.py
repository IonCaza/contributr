import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import get_db
from app.db.models import Project, Repository, User, Commit, DailyContributorStats
from app.auth.dependencies import get_current_user
from app.services.metrics import get_trends, get_bus_factor

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


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
    project = Project(name=body.name, description=body.description)
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
    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description
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

    return {
        "repository_count": repo_count,
        "total_commits": commit_count,
        "contributor_count": contributor_count,
        "trends": trends,
    }
