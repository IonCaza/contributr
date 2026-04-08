import json
import os
import shutil
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status, Query as QueryParam
from pydantic import BaseModel
from sqlalchemy import delete, select, func
from sqlalchemy.dialects.postgresql import array_agg
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse
import redis.asyncio as aioredis

from collections import defaultdict

from app.config import settings
from app.db.base import get_db
from app.db.models import Repository, User, SyncJob, Commit, Branch, Contributor, PullRequest, Review, CommitFile, DailyContributorStats
from app.db.models.branch import commit_branches
from app.db.models.repository import Platform
from app.db.models.sync_job import SyncStatus
from app.db.models.pull_request import PRState
from app.auth.dependencies import get_current_user, get_accessible_project_ids
from app.services.metrics import get_trends, get_bus_factor
from app.workers.tasks import sync_repository

router = APIRouter(tags=["repositories"])


def _compute_gini(values: list[int]) -> float:
    if not values or sum(values) == 0:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    cumulative = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(sorted_vals))
    return round(cumulative / (n * sum(sorted_vals)), 2)


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


def _check_project_access(project_id: uuid.UUID, accessible: set[uuid.UUID] | None) -> None:
    if accessible is not None and project_id not in accessible:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this project")


@router.get("/projects/{project_id}/repositories", response_model=list[RepoResponse])
async def list_repositories(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    accessible: set[uuid.UUID] | None = Depends(get_accessible_project_ids),
):
    _check_project_access(project_id, accessible)
    result = await db.execute(
        select(Repository).where(Repository.project_id == project_id).order_by(Repository.name)
    )
    return result.scalars().all()


@router.post("/projects/{project_id}/repositories", response_model=RepoResponse, status_code=status.HTTP_201_CREATED)
async def create_repository(
    project_id: uuid.UUID,
    body: RepoCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    accessible: set[uuid.UUID] | None = Depends(get_accessible_project_ids),
):
    _check_project_access(project_id, accessible)
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


async def _load_repo(db: AsyncSession, repo_id: uuid.UUID, accessible: set[uuid.UUID] | None) -> Repository:
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    _check_project_access(repo.project_id, accessible)
    return repo


@router.get("/repositories/{repo_id}", response_model=RepoResponse)
async def get_repository(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    accessible: set[uuid.UUID] | None = Depends(get_accessible_project_ids),
):
    return await _load_repo(db, repo_id, accessible)


@router.put("/repositories/{repo_id}", response_model=RepoResponse)
async def update_repository(
    repo_id: uuid.UUID,
    body: RepoUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    accessible: set[uuid.UUID] | None = Depends(get_accessible_project_ids),
):
    repo = await _load_repo(db, repo_id, accessible)
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
async def delete_repository(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    accessible: set[uuid.UUID] | None = Depends(get_accessible_project_ids),
):
    repo = await _load_repo(db, repo_id, accessible)

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


@router.post("/repositories/{repo_id}/purge-data", status_code=status.HTTP_200_OK)
async def purge_repository_data(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    accessible: set[uuid.UUID] | None = Depends(get_accessible_project_ids),
):
    repo = await _load_repo(db, repo_id, accessible)

    running = await db.execute(
        select(SyncJob).where(SyncJob.repository_id == repo_id, SyncJob.status.in_([SyncStatus.QUEUED, SyncStatus.RUNNING]))
    )
    active_job = running.scalar_one_or_none()
    if active_job and active_job.celery_task_id:
        from app.workers.celery_app import celery
        celery.control.revoke(active_job.celery_task_id, terminate=True, signal="SIGTERM")

    await db.execute(delete(DailyContributorStats).where(DailyContributorStats.repository_id == repo_id))
    await db.execute(delete(Commit).where(Commit.repository_id == repo_id))
    await db.execute(delete(PullRequest).where(PullRequest.repository_id == repo_id))
    await db.execute(delete(Branch).where(Branch.repository_id == repo_id))
    await db.execute(delete(SyncJob).where(SyncJob.repository_id == repo_id))
    await db.commit()

    repo.last_synced_at = None
    await db.commit()

    cache_dir = os.path.join(settings.repos_cache_dir, str(repo_id))
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir, ignore_errors=True)

    return {"status": "purged", "repository_id": str(repo_id)}


@router.post("/repositories/{repo_id}/sync", response_model=SyncJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    accessible: set[uuid.UUID] | None = Depends(get_accessible_project_ids),
):
    repo = await _load_repo(db, repo_id, accessible)

    STALE_QUEUED = timedelta(minutes=10)
    STALE_RUNNING = timedelta(hours=2)
    now = datetime.now(timezone.utc)

    blocking_result = await db.execute(
        select(SyncJob).where(SyncJob.repository_id == repo_id, SyncJob.status.in_([SyncStatus.QUEUED, SyncStatus.RUNNING]))
    )
    blocking_job = blocking_result.scalar_one_or_none()

    if blocking_job:
        is_stale = (
            (blocking_job.status == SyncStatus.QUEUED and blocking_job.created_at < now - STALE_QUEUED)
            or (blocking_job.status == SyncStatus.RUNNING and blocking_job.started_at and blocking_job.started_at < now - STALE_RUNNING)
            or (blocking_job.status == SyncStatus.RUNNING and blocking_job.started_at is None and blocking_job.created_at < now - STALE_QUEUED)
        )
        if is_stale:
            blocking_job.status = SyncStatus.FAILED
            blocking_job.error_message = "Automatically marked as failed (stale job)"
            blocking_job.finished_at = now
            await db.commit()
        else:
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
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    base_q = _branch_filtered_commit_query(repo_id, branch) if branch else select(Commit).where(Commit.repository_id == repo_id)
    if from_date:
        base_q = base_q.where(Commit.authored_at >= from_date)
    if to_date:
        base_q = base_q.where(Commit.authored_at <= to_date + timedelta(days=1))

    sub = base_q.with_only_columns(Commit.id).subquery()
    commit_count = await db.scalar(select(func.count()).select_from(sub))
    contributor_count = await db.scalar(
        select(func.count(Commit.contributor_id.distinct())).where(Commit.id.in_(select(sub.c.id)))
    )
    trends = await get_trends(db, repository_id=repo_id, branch_names=branch if branch else None)
    bus_factor = await get_bus_factor(db, repo_id, branch_names=branch if branch else None)

    agg_q = select(
        func.coalesce(func.sum(Commit.lines_added), 0).label("la"),
        func.coalesce(func.sum(Commit.lines_deleted), 0).label("ld"),
    ).where(Commit.id.in_(select(sub.c.id)))
    agg = (await db.execute(agg_q)).one()
    churn_ratio = round(agg.ld / agg.la, 2) if agg.la > 0 else 0

    pr_cycle_q = select(
        func.avg(func.extract("epoch", PullRequest.merged_at - PullRequest.created_at) / 3600)
    ).where(
        PullRequest.repository_id == repo_id,
        PullRequest.state == PRState.MERGED,
        PullRequest.merged_at.isnot(None),
    )
    if from_date:
        pr_cycle_q = pr_cycle_q.where(PullRequest.created_at >= from_date)
    if to_date:
        pr_cycle_q = pr_cycle_q.where(PullRequest.created_at <= to_date + timedelta(days=1))
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
        PullRequest.repository_id == repo_id,
    )
    if from_date:
        pr_review_q = pr_review_q.where(PullRequest.created_at >= from_date)
    if to_date:
        pr_review_q = pr_review_q.where(PullRequest.created_at <= to_date + timedelta(days=1))
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
    _vals = [r.cnt for r in contrib_rows]
    contribution_gini = _compute_gini(_vals)

    return {
        "total_commits": commit_count,
        "contributor_count": contributor_count,
        "bus_factor": bus_factor,
        "churn_ratio": churn_ratio,
        "pr_cycle_time_hours": pr_cycle_time_hours,
        "pr_review_turnaround_hours": pr_review_turnaround_hours,
        "contribution_gini": contribution_gini,
        "trends": trends,
    }


@router.get("/repositories/{repo_id}/file-tree")
async def get_file_tree(
    repo_id: uuid.UUID,
    branch: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = (
        select(
            CommitFile.file_path,
            func.count(CommitFile.commit_id.distinct()).label("commits"),
            func.count(Commit.contributor_id.distinct()).label("contributors"),
            func.sum(CommitFile.lines_added).label("lines_added"),
            func.sum(CommitFile.lines_deleted).label("lines_deleted"),
            func.max(Commit.authored_at).label("last_modified"),
            array_agg(Commit.contributor_id.distinct()).label("contributor_ids"),
        )
        .join(Commit, Commit.id == CommitFile.commit_id)
        .where(Commit.repository_id == repo_id)
    )
    if branch:
        q = q.join(commit_branches, commit_branches.c.commit_id == Commit.id).join(
            Branch, Branch.id == commit_branches.c.branch_id
        ).where(Branch.name == branch)
    q = q.group_by(CommitFile.file_path)
    result = await db.execute(q)
    rows = result.all()
    if not rows:
        return []

    tree: dict[str, Any] = {}
    for row in rows:
        parts = row.file_path.split("/")
        node = tree
        for i, part in enumerate(parts):
            if part not in node:
                node[part] = {"_children": {}, "_data": None}
            if i == len(parts) - 1:
                cids = set(str(c) for c in (row.contributor_ids or []))
                node[part]["_data"] = {
                    "commits": row.commits,
                    "contributors": len(cids),
                    "lines_added": row.lines_added or 0,
                    "lines_deleted": row.lines_deleted or 0,
                    "last_modified": row.last_modified.isoformat() if row.last_modified else None,
                    "_contributor_ids": cids,
                }
            node = node[part]["_children"]

    def _build(node_dict: dict, prefix: str = "") -> tuple[list[dict], set]:
        items = []
        all_cids: set = set()
        for name, val in sorted(node_dict.items()):
            path = f"{prefix}/{name}" if prefix else name
            children, child_cids = _build(val["_children"], path)
            if val["_data"]:
                file_cids = val["_data"].pop("_contributor_ids", set())
                all_cids |= file_cids
                items.append({
                    "name": name, "path": path, "type": "file",
                    **val["_data"],
                })
            elif children:
                all_cids |= child_cids
                agg_commits = sum(c.get("commits", 0) for c in children)
                agg_la = sum(c.get("lines_added", 0) for c in children)
                agg_ld = sum(c.get("lines_deleted", 0) for c in children)
                agg_lm = max((c.get("last_modified") for c in children if c.get("last_modified")), default=None)
                items.append({
                    "name": name, "path": path, "type": "directory",
                    "commits": agg_commits, "contributors": len(child_cids),
                    "lines_added": agg_la, "lines_deleted": agg_ld,
                    "last_modified": agg_lm,
                    "children": children,
                })
        return items, all_cids

    tree_list, _ = _build(tree)
    return tree_list


@router.get("/repositories/{repo_id}/files/{file_path:path}")
async def get_file_detail(
    repo_id: uuid.UUID,
    file_path: str,
    branch: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    from app.api.commits import _build_commit_url

    agg_q = (
        select(
            func.count(CommitFile.commit_id.distinct()).label("total_commits"),
            func.sum(CommitFile.lines_added).label("la"),
            func.sum(CommitFile.lines_deleted).label("ld"),
        )
        .join(Commit, Commit.id == CommitFile.commit_id)
        .where(Commit.repository_id == repo_id, CommitFile.file_path == file_path)
    )
    if branch:
        agg_q = agg_q.join(commit_branches, commit_branches.c.commit_id == Commit.id).join(
            Branch, Branch.id == commit_branches.c.branch_id
        ).where(Branch.name == branch)
    agg = await db.execute(agg_q)
    totals = agg.one()

    cq = (
        select(
            Contributor.id, Contributor.canonical_name, Contributor.canonical_email,
            func.count(CommitFile.commit_id.distinct()).label("commits"),
            func.sum(CommitFile.lines_added).label("la"),
            func.sum(CommitFile.lines_deleted).label("ld"),
            func.max(Commit.authored_at).label("last_touched"),
        )
        .join(Commit, Commit.id == CommitFile.commit_id)
        .join(Contributor, Contributor.id == Commit.contributor_id)
        .where(Commit.repository_id == repo_id, CommitFile.file_path == file_path)
    )
    if branch:
        cq = cq.join(commit_branches, commit_branches.c.commit_id == Commit.id).join(
            Branch, Branch.id == commit_branches.c.branch_id
        ).where(Branch.name == branch)
    contrib_q = await db.execute(
        cq.group_by(Contributor.id, Contributor.canonical_name, Contributor.canonical_email)
        .order_by(func.count(CommitFile.commit_id.distinct()).desc())
    )
    contrib_rows = contrib_q.all()

    contribs = []
    for r in contrib_rows:
        contribs.append({
            "id": str(r.id), "name": r.canonical_name, "email": r.canonical_email,
            "commits": r.commits, "lines_added": r.la or 0, "lines_deleted": r.ld or 0,
            "last_touched": r.last_touched.isoformat() if r.last_touched else None,
        })

    primary = contribs[0] if contribs else None

    from sqlalchemy.orm import selectinload
    recent_stmt = (
        select(Commit)
        .join(CommitFile, CommitFile.commit_id == Commit.id)
        .options(selectinload(Commit.contributor), selectinload(Commit.repository), selectinload(Commit.branches))
        .where(Commit.repository_id == repo_id, CommitFile.file_path == file_path)
    )
    if branch:
        recent_stmt = recent_stmt.join(commit_branches, commit_branches.c.commit_id == Commit.id).join(
            Branch, Branch.id == commit_branches.c.branch_id
        ).where(Branch.name == branch)
    recent_q = await db.execute(
        recent_stmt.order_by(Commit.authored_at.desc()).limit(20)
    )
    recent_commits = []
    for c in recent_q.scalars().unique().all():
        recent_commits.append({
            "id": str(c.id), "sha": c.sha, "message": c.message,
            "authored_at": c.authored_at.isoformat(),
            "lines_added": c.lines_added, "lines_deleted": c.lines_deleted,
            "files_changed": c.files_changed, "is_merge": c.is_merge,
            "contributor_name": c.contributor.canonical_name if c.contributor else None,
            "contributor_email": c.contributor.canonical_email if c.contributor else None,
            "repository_name": c.repository.name if c.repository else None,
            "repository_id": str(c.repository_id),
            "commit_url": _build_commit_url(c.repository, c.sha) if c.repository else None,
            "branches": [b.name for b in c.branches] if c.branches else [],
        })

    return {
        "path": file_path,
        "total_commits": totals.total_commits or 0,
        "total_lines_added": totals.la or 0,
        "total_lines_deleted": totals.ld or 0,
        "primary_owner": primary,
        "contributors": contribs,
        "recent_commits": recent_commits,
    }


@router.get("/repositories/{repo_id}/hotspots")
async def get_hotspots(
    repo_id: uuid.UUID,
    limit: int = QueryParam(default=50, ge=1, le=200),
    branch: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = (
        select(
            CommitFile.file_path,
            func.count(CommitFile.commit_id.distinct()).label("commit_count"),
            func.count(Commit.contributor_id.distinct()).label("contributor_count"),
            func.sum(CommitFile.lines_added).label("la"),
            func.sum(CommitFile.lines_deleted).label("ld"),
        )
        .join(Commit, Commit.id == CommitFile.commit_id)
        .where(Commit.repository_id == repo_id)
    )
    if branch:
        q = q.join(commit_branches, commit_branches.c.commit_id == Commit.id).join(
            Branch, Branch.id == commit_branches.c.branch_id
        ).where(Branch.name == branch)
    q = q.group_by(CommitFile.file_path).order_by(func.count(CommitFile.commit_id.distinct()).desc()).limit(limit)
    result = await db.execute(q)
    items = []
    for r in result.all():
        items.append({
            "file_path": r.file_path,
            "commit_count": r.commit_count,
            "contributor_count": r.contributor_count,
            "total_lines_added": r.la or 0,
            "total_lines_deleted": r.ld or 0,
            "bus_factor": 1 if r.contributor_count == 1 else r.contributor_count,
        })
    return items


@router.get("/repositories/{repo_id}/sync-jobs/{job_id}/logs")
async def stream_sync_logs(
    request: Request,
    repo_id: uuid.UUID,
    job_id: uuid.UUID,
    token: str | None = QueryParam(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Stream sync job logs in real-time via Server-Sent Events.

    Accepts JWT as a ``token`` query parameter because EventSource
    does not support Authorization headers.
    """
    from app.auth.security import decode_token as decode_jwt
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token required")
    payload = decode_jwt(token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    list_key = f"sync:logs:{job_id}"
    channel_key = f"sync:logs:live:{job_id}"

    async def event_generator():
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            existing = await r.lrange(list_key, 0, -1)
            for entry in existing:
                data = json.loads(entry)
                if data.get("phase") == "__done__":
                    yield {"event": "done", "data": entry}
                    return
                yield {"event": "log", "data": entry}

            pubsub = r.pubsub()
            await pubsub.subscribe(channel_key)
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if msg is None:
                        continue
                    data = json.loads(msg["data"])
                    if data.get("phase") == "__done__":
                        yield {"event": "done", "data": msg["data"]}
                        break
                    yield {"event": "log", "data": msg["data"]}
            finally:
                await pubsub.unsubscribe(channel_key)
                await pubsub.aclose()
        finally:
            await r.aclose()

    return EventSourceResponse(event_generator())
