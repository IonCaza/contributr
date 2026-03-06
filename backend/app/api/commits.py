import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import get_db
from app.db.models import Commit, Contributor, User, Branch, Repository, CommitFile
from app.db.models.repository import Platform
from app.db.models.branch import commit_branches
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/commits", tags=["commits"])


def _build_commit_url(repo: Repository, sha: str) -> str | None:
    from urllib.parse import quote
    owner = repo.platform_owner
    name = repo.platform_repo
    if not owner or not name:
        return None
    if repo.platform == Platform.GITHUB:
        return f"https://github.com/{owner}/{name}/commit/{sha}"
    if repo.platform == Platform.GITLAB:
        return f"https://gitlab.com/{owner}/{name}/-/commit/{sha}"
    if repo.platform == Platform.AZURE:
        encoded_owner = "/".join(quote(p, safe="") for p in owner.split("/"))
        return f"https://dev.azure.com/{encoded_owner}/_git/{quote(name, safe='')}/commit/{sha}"
    return None


class CommitResponse(BaseModel):
    id: uuid.UUID
    sha: str
    message: str | None
    authored_at: datetime
    lines_added: int
    lines_deleted: int
    files_changed: int
    is_merge: bool
    contributor_name: str | None = None
    contributor_email: str | None = None
    repository_name: str | None = None
    repository_id: uuid.UUID
    commit_url: str | None = None
    branches: list[str] = []


class PaginatedCommits(BaseModel):
    items: list[CommitResponse]
    total: int
    page: int
    per_page: int


async def _query_commits(
    db: AsyncSession,
    *,
    repository_id: uuid.UUID | None = None,
    contributor_id: uuid.UUID | None = None,
    branch_names: list[str] | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> PaginatedCommits:
    base = select(Commit)
    count_base = select(func.count()).select_from(Commit)

    if repository_id:
        base = base.where(Commit.repository_id == repository_id)
        count_base = count_base.where(Commit.repository_id == repository_id)
    if contributor_id:
        base = base.where(Commit.contributor_id == contributor_id)
        count_base = count_base.where(Commit.contributor_id == contributor_id)
    if from_date:
        base = base.where(Commit.authored_at >= from_date)
        count_base = count_base.where(Commit.authored_at >= from_date)
    if to_date:
        end = to_date + timedelta(days=1)
        base = base.where(Commit.authored_at <= end)
        count_base = count_base.where(Commit.authored_at <= end)
    if search:
        like_pattern = f"%{search}%"
        base = base.where(Commit.message.ilike(like_pattern))
        count_base = count_base.where(Commit.message.ilike(like_pattern))
    if branch_names:
        base = (
            base.join(commit_branches, commit_branches.c.commit_id == Commit.id)
            .join(Branch, Branch.id == commit_branches.c.branch_id)
            .where(Branch.name.in_(branch_names))
        )
        count_base = (
            count_base.join(commit_branches, commit_branches.c.commit_id == Commit.id)
            .join(Branch, Branch.id == commit_branches.c.branch_id)
            .where(Branch.name.in_(branch_names))
        )

    total = await db.scalar(count_base) or 0

    base = (
        base.options(selectinload(Commit.contributor), selectinload(Commit.repository), selectinload(Commit.branches))
        .order_by(Commit.authored_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .distinct()
    )

    result = await db.execute(base)
    commits = result.scalars().unique().all()

    items = []
    for c in commits:
        items.append(CommitResponse(
            id=c.id,
            sha=c.sha,
            message=c.message,
            authored_at=c.authored_at,
            lines_added=c.lines_added,
            lines_deleted=c.lines_deleted,
            files_changed=c.files_changed,
            is_merge=c.is_merge,
            contributor_name=c.contributor.canonical_name if c.contributor else None,
            contributor_email=c.contributor.canonical_email if c.contributor else None,
            repository_name=c.repository.name if c.repository else None,
            repository_id=c.repository_id,
            commit_url=_build_commit_url(c.repository, c.sha) if c.repository else None,
            branches=[b.name for b in c.branches] if c.branches else [],
        ))

    return PaginatedCommits(items=items, total=total, page=page, per_page=per_page)


@router.get("/by-repo/{repo_id}", response_model=PaginatedCommits)
async def list_repo_commits(
    repo_id: uuid.UUID,
    branch: list[str] = Query(default=[]),
    contributor_id: uuid.UUID | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await _query_commits(
        db,
        repository_id=repo_id,
        contributor_id=contributor_id,
        branch_names=branch or None,
        search=search,
        page=page,
        per_page=per_page,
    )


@router.get("/by-contributor/{contributor_id}", response_model=PaginatedCommits)
async def list_contributor_commits(
    contributor_id: uuid.UUID,
    repository_id: uuid.UUID | None = None,
    branch: list[str] = Query(default=[]),
    from_date: date | None = None,
    to_date: date | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await _query_commits(
        db,
        repository_id=repository_id,
        contributor_id=contributor_id,
        branch_names=branch or None,
        from_date=from_date,
        to_date=to_date,
        search=search,
        page=page,
        per_page=per_page,
    )


class CommitFileResponse(BaseModel):
    id: uuid.UUID
    file_path: str
    lines_added: int
    lines_deleted: int


class CommitDetailResponse(CommitResponse):
    files: list[CommitFileResponse] = []


@router.get("/{commit_id}", response_model=CommitDetailResponse)
async def get_commit_detail(
    commit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    from fastapi import HTTPException, status as http_status
    result = await db.execute(
        select(Commit)
        .options(selectinload(Commit.contributor), selectinload(Commit.repository), selectinload(Commit.branches), selectinload(Commit.files))
        .where(Commit.id == commit_id)
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Commit not found")

    return CommitDetailResponse(
        id=c.id,
        sha=c.sha,
        message=c.message,
        authored_at=c.authored_at,
        lines_added=c.lines_added,
        lines_deleted=c.lines_deleted,
        files_changed=c.files_changed,
        is_merge=c.is_merge,
        contributor_name=c.contributor.canonical_name if c.contributor else None,
        contributor_email=c.contributor.canonical_email if c.contributor else None,
        repository_name=c.repository.name if c.repository else None,
        repository_id=c.repository_id,
        commit_url=_build_commit_url(c.repository, c.sha) if c.repository else None,
        branches=[b.name for b in c.branches] if c.branches else [],
        files=[CommitFileResponse(id=f.id, file_path=f.file_path, lines_added=f.lines_added, lines_deleted=f.lines_deleted) for f in (c.files or [])],
    )
