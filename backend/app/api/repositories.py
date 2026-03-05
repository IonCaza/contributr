import os
import shutil
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Query as QueryParam

from app.config import settings
from app.db.base import get_db
from app.db.models import Repository, User, SyncJob, Commit, Branch, Contributor
from app.db.models.branch import commit_branches
from app.db.models.repository import Platform
from app.db.models.sync_job import SyncStatus
from app.auth.dependencies import get_current_user
from app.services.metrics import get_trends, get_bus_factor
from app.workers.tasks import sync_repository

router = APIRouter(tags=["repositories"])


import re
from urllib.parse import unquote

def _parse_platform_fields(ssh_url: str | None, clone_url: str | None, platform: Platform) -> tuple[str | None, str | None]:
    """Extract platform_owner and platform_repo from URLs."""
    url = ssh_url or clone_url
    if not url:
        return None, None

    if platform == Platform.AZURE:
        m = re.search(r"v3/([^/]+)/([^/]+)/([^/\s]+)", url)
        if m:
            org, project, repo = m.group(1), unquote(m.group(2)), m.group(3)
            return f"{org}/{project}", repo
        m = re.search(r"dev\.azure\.com/([^/]+)/([^/]+)/_git/([^/\s]+)", url)
        if m:
            org, project, repo = m.group(1), unquote(m.group(2)), m.group(3)
            return f"{org}/{project}", repo

    if platform == Platform.GITHUB:
        m = re.search(r"github\.com[:/]([^/]+)/([^/\s]+?)(?:\.git)?$", url)
        if m:
            return m.group(1), m.group(2)

    if platform == Platform.GITLAB:
        m = re.search(r"gitlab\.com[:/]([^/]+)/([^/\s]+?)(?:\.git)?$", url)
        if m:
            return m.group(1), m.group(2)

    return None, None


class RepoCreate(BaseModel):
    name: str
    clone_url: str | None = None
    ssh_url: str | None = None
    platform: Platform
    platform_owner: str | None = None
    platform_repo: str | None = None
    default_branch: str = "main"
    ssh_credential_id: uuid.UUID | None = None


class RepoResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    clone_url: str | None
    ssh_url: str | None
    platform: str
    platform_owner: str | None
    platform_repo: str | None
    default_branch: str
    ssh_credential_id: uuid.UUID | None
    last_synced_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


class SyncJobResponse(BaseModel):
    id: uuid.UUID
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    model_config = {"from_attributes": True}


@router.get("/projects/{project_id}/repositories", response_model=list[RepoResponse])
async def list_repositories(project_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Repository).where(Repository.project_id == project_id).order_by(Repository.name)
    )
    return result.scalars().all()


@router.post("/projects/{project_id}/repositories", response_model=RepoResponse, status_code=status.HTTP_201_CREATED)
async def create_repository(project_id: uuid.UUID, body: RepoCreate, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    data = body.model_dump()
    if not data.get("platform_owner") or not data.get("platform_repo"):
        owner, name = _parse_platform_fields(data.get("ssh_url"), data.get("clone_url"), body.platform)
        if owner:
            data["platform_owner"] = owner
        if name:
            data["platform_repo"] = name
    repo = Repository(project_id=project_id, **data)
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
    return repo


class RepoUpdate(BaseModel):
    name: str | None = None
    ssh_url: str | None = None
    clone_url: str | None = None
    platform: Platform | None = None
    platform_owner: str | None = None
    platform_repo: str | None = None
    default_branch: str | None = None
    ssh_credential_id: uuid.UUID | None = None


@router.get("/repositories/{repo_id}", response_model=RepoResponse)
async def get_repository(repo_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return repo


@router.put("/repositories/{repo_id}", response_model=RepoResponse)
async def update_repository(repo_id: uuid.UUID, body: RepoUpdate, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(repo, field, value)
    if ("ssh_url" in updates or "clone_url" in updates) and (not repo.platform_owner or not repo.platform_repo):
        owner, name = _parse_platform_fields(repo.ssh_url, repo.clone_url, repo.platform)
        if owner:
            repo.platform_owner = owner
        if name:
            repo.platform_repo = name
    await db.commit()
    await db.refresh(repo)
    return repo


@router.delete("/repositories/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repository(repo_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    running = await db.execute(
        select(SyncJob).where(SyncJob.repository_id == repo_id, SyncJob.status.in_([SyncStatus.QUEUED, SyncStatus.RUNNING]))
    )
    active_job = running.scalar_one_or_none()
    if active_job and active_job.celery_task_id:
        from app.workers.celery_app import celery
        celery.control.revoke(active_job.celery_task_id, terminate=True, signal="SIGTERM")

    await db.delete(repo)
    await db.commit()

    cache_dir = os.path.join(settings.repos_cache_dir, str(repo_id))
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir, ignore_errors=True)


@router.post("/repositories/{repo_id}/sync", response_model=SyncJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(repo_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    running = await db.execute(
        select(SyncJob).where(SyncJob.repository_id == repo_id, SyncJob.status.in_([SyncStatus.QUEUED, SyncStatus.RUNNING]))
    )
    if running.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Sync already in progress")

    job = SyncJob(repository_id=repo_id, status=SyncStatus.QUEUED)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    celery_result = sync_repository.delay(str(repo_id), str(job.id))
    job.celery_task_id = celery_result.id
    await db.commit()
    await db.refresh(job)
    return job


@router.post("/repositories/{repo_id}/sync-jobs/{job_id}/cancel", response_model=SyncJobResponse)
async def cancel_sync_job(repo_id: uuid.UUID, job_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(
        select(SyncJob).where(SyncJob.id == job_id, SyncJob.repository_id == repo_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync job not found")

    if job.status not in (SyncStatus.QUEUED, SyncStatus.RUNNING):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot cancel job in {job.status.value} state")

    if job.celery_task_id:
        from app.workers.celery_app import celery
        celery.control.revoke(job.celery_task_id, terminate=True, signal="SIGTERM")

    job.status = SyncStatus.CANCELLED
    job.finished_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("/repositories/{repo_id}/sync-jobs", response_model=list[SyncJobResponse])
async def list_sync_jobs(repo_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(
        select(SyncJob).where(SyncJob.repository_id == repo_id).order_by(SyncJob.created_at.desc()).limit(20)
    )
    return result.scalars().all()


class BranchResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_default: bool
    model_config = {"from_attributes": True}


class ContributorSummaryResponse(BaseModel):
    id: uuid.UUID
    canonical_name: str
    canonical_email: str
    model_config = {"from_attributes": True}


@router.get("/repositories/{repo_id}/branches", response_model=list[BranchResponse])
async def list_branches(
    repo_id: uuid.UUID,
    contributor_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = select(Branch).where(Branch.repository_id == repo_id)
    if contributor_id:
        query = (
            query.join(commit_branches, commit_branches.c.branch_id == Branch.id)
            .join(Commit, Commit.id == commit_branches.c.commit_id)
            .where(Commit.contributor_id == contributor_id)
            .distinct()
        )
    query = query.order_by(Branch.is_default.desc(), Branch.name)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/repositories/{repo_id}/contributors", response_model=list[ContributorSummaryResponse])
async def list_repo_contributors(
    repo_id: uuid.UUID,
    branch: list[str] = QueryParam(default=[]),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = (
        select(Contributor)
        .join(Commit, Commit.contributor_id == Contributor.id)
        .where(Commit.repository_id == repo_id)
    )
    if branch:
        query = query.join(commit_branches, commit_branches.c.commit_id == Commit.id).join(
            Branch, Branch.id == commit_branches.c.branch_id
        ).where(Branch.name.in_(branch))
    query = query.distinct().order_by(Contributor.canonical_name)
    result = await db.execute(query)
    return result.scalars().all()


def _branch_filtered_commit_query(repo_id: uuid.UUID, branches: list[str]):
    """Build a base query on Commit filtered by repo and optionally branches."""
    q = select(Commit).where(Commit.repository_id == repo_id)
    if branches:
        q = q.join(commit_branches, commit_branches.c.commit_id == Commit.id).join(
            Branch, Branch.id == commit_branches.c.branch_id
        ).where(Branch.name.in_(branches))
    return q


@router.get("/repositories/{repo_id}/stats")
async def get_repo_stats(
    repo_id: uuid.UUID,
    branch: list[str] = QueryParam(default=[]),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    if branch:
        base = _branch_filtered_commit_query(repo_id, branch).with_only_columns(Commit.id)
        sub = base.subquery()
        commit_count = await db.scalar(select(func.count()).select_from(sub))
        contributor_q = (
            select(func.count(Commit.contributor_id.distinct()))
            .where(Commit.repository_id == repo_id)
            .join(commit_branches, commit_branches.c.commit_id == Commit.id)
            .join(Branch, Branch.id == commit_branches.c.branch_id)
            .where(Branch.name.in_(branch))
        )
        contributor_count = await db.scalar(contributor_q)
        trends = await get_trends(db, repository_id=repo_id, branch_names=branch)
        bus_factor = await get_bus_factor(db, repo_id, branch_names=branch)
    else:
        commit_count = await db.scalar(select(func.count()).select_from(Commit).where(Commit.repository_id == repo_id))
        contributor_count = await db.scalar(
            select(func.count(Commit.contributor_id.distinct())).where(Commit.repository_id == repo_id)
        )
        trends = await get_trends(db, repository_id=repo_id)
        bus_factor = await get_bus_factor(db, repo_id)

    return {
        "total_commits": commit_count,
        "contributor_count": contributor_count,
        "bus_factor": bus_factor,
        "trends": trends,
    }
