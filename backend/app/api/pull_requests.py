import logging
import uuid
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, case, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import get_db
from app.db.models import PullRequest, Review, PRComment, Repository, Contributor, User, PlatformCredential
from app.db.models.pull_request import PRState
from app.db.models.review import ReviewState
from app.db.models.repository import Platform
from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/pull-requests", tags=["pull-requests"])


# ── Schemas ────────────────────────────────────────────────────────────

class ReviewResponse(BaseModel):
    id: uuid.UUID
    reviewer_name: str | None = None
    reviewer_id: uuid.UUID | None = None
    state: str
    comment_count: int = 0
    submitted_at: datetime

class CommentResponse(BaseModel):
    id: uuid.UUID
    author_name: str
    author_id: uuid.UUID | None = None
    body: str
    thread_id: str | None = None
    parent_comment_id: uuid.UUID | None = None
    file_path: str | None = None
    line_number: int | None = None
    comment_type: str
    created_at: datetime
    updated_at: datetime | None = None

class PRListItem(BaseModel):
    id: uuid.UUID
    platform_pr_id: int
    title: str | None
    state: str
    repository_name: str
    repository_id: uuid.UUID
    author_name: str | None = None
    contributor_id: uuid.UUID | None = None
    lines_added: int = 0
    lines_deleted: int = 0
    comment_count: int = 0
    review_count: int = 0
    iteration_count: int = 0
    created_at: datetime
    merged_at: datetime | None = None
    closed_at: datetime | None = None
    first_review_at: datetime | None = None
    cycle_time_hours: float | None = None
    review_turnaround_hours: float | None = None

class PRListResponse(BaseModel):
    items: list[PRListItem]
    total: int
    page: int
    page_size: int

class PRDetailResponse(BaseModel):
    id: uuid.UUID
    platform_pr_id: int
    title: str | None
    state: str
    repository_name: str
    repository_id: uuid.UUID
    author_name: str | None = None
    contributor_id: uuid.UUID | None = None
    lines_added: int = 0
    lines_deleted: int = 0
    comment_count: int = 0
    iteration_count: int = 0
    created_at: datetime
    merged_at: datetime | None = None
    closed_at: datetime | None = None
    first_review_at: datetime | None = None
    cycle_time_hours: float | None = None
    review_turnaround_hours: float | None = None
    reviews: list[ReviewResponse] = []
    comments: list[CommentResponse] = []

class SizeBucket(BaseModel):
    label: str
    count: int
    avg_cycle_time_hours: float | None = None

class ReviewerStat(BaseModel):
    reviewer_name: str
    reviewer_id: uuid.UUID | None = None
    review_count: int = 0
    avg_turnaround_hours: float | None = None
    approval_count: int = 0

class CycleTimeTrend(BaseModel):
    period: str
    avg_cycle_time_hours: float | None = None
    pr_count: int = 0

class AnalyticsResponse(BaseModel):
    total_prs: int = 0
    open_prs: int = 0
    merged_prs: int = 0
    closed_prs: int = 0
    avg_cycle_time_hours: float | None = None
    avg_review_turnaround_hours: float | None = None
    merge_rate: float | None = None
    size_distribution: list[SizeBucket] = []
    cycle_time_trend: list[CycleTimeTrend] = []
    top_reviewers: list[ReviewerStat] = []


# ── Helpers ────────────────────────────────────────────────────────────

def _cycle_time(pr: PullRequest) -> float | None:
    end = pr.merged_at or pr.closed_at
    if end and pr.created_at:
        return round((end.timestamp() - pr.created_at.timestamp()) / 3600, 1)
    return None

def _review_turnaround(pr: PullRequest) -> float | None:
    if pr.first_review_at and pr.created_at:
        return round((pr.first_review_at.timestamp() - pr.created_at.timestamp()) / 3600, 1)
    return None

def _size_label(lines: int) -> str:
    if lines < 10:
        return "XS"
    if lines < 100:
        return "S"
    if lines < 500:
        return "M"
    if lines < 1000:
        return "L"
    return "XL"


# ── Endpoints ──────────────────────────────────────────────────────────

@router.get("", response_model=PRListResponse)
async def list_pull_requests(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    state: str | None = Query(None, description="open, merged, closed, or all"),
    repository_id: uuid.UUID | None = Query(None),
    contributor_id: uuid.UUID | None = Query(None),
    reviewer_id: uuid.UUID | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: Literal["asc", "desc"] = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    repo_ids_q = select(Repository.id).where(Repository.project_id == project_id)
    base = (
        select(PullRequest)
        .where(PullRequest.repository_id.in_(repo_ids_q))
        .options(
            selectinload(PullRequest.repository),
            selectinload(PullRequest.contributor),
            selectinload(PullRequest.reviews),
        )
    )
    count_q = (
        select(func.count(PullRequest.id))
        .where(PullRequest.repository_id.in_(repo_ids_q))
    )

    if state and state != "all":
        state_enum = {"open": PRState.OPEN, "merged": PRState.MERGED, "closed": PRState.CLOSED}.get(state)
        if state_enum:
            base = base.where(PullRequest.state == state_enum)
            count_q = count_q.where(PullRequest.state == state_enum)

    if repository_id:
        base = base.where(PullRequest.repository_id == repository_id)
        count_q = count_q.where(PullRequest.repository_id == repository_id)

    if contributor_id:
        base = base.where(PullRequest.contributor_id == contributor_id)
        count_q = count_q.where(PullRequest.contributor_id == contributor_id)

    if reviewer_id:
        review_pr_ids = select(Review.pull_request_id).where(Review.reviewer_id == reviewer_id)
        base = base.where(PullRequest.id.in_(review_pr_ids))
        count_q = count_q.where(PullRequest.id.in_(review_pr_ids))

    if from_date:
        base = base.where(PullRequest.created_at >= datetime.combine(from_date, datetime.min.time()))
        count_q = count_q.where(PullRequest.created_at >= datetime.combine(from_date, datetime.min.time()))

    if to_date:
        base = base.where(PullRequest.created_at <= datetime.combine(to_date, datetime.max.time()))
        count_q = count_q.where(PullRequest.created_at <= datetime.combine(to_date, datetime.max.time()))

    if search:
        base = base.where(PullRequest.title.ilike(f"%{search}%"))
        count_q = count_q.where(PullRequest.title.ilike(f"%{search}%"))

    sort_col = {
        "created_at": PullRequest.created_at,
        "lines_changed": (PullRequest.lines_added + PullRequest.lines_deleted),
        "comment_count": PullRequest.comment_count,
    }.get(sort_by, PullRequest.created_at)

    base = base.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    base = base.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(base)
    prs = result.scalars().unique().all()

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    items = []
    for pr in prs:
        items.append(PRListItem(
            id=pr.id,
            platform_pr_id=pr.platform_pr_id,
            title=pr.title,
            state=pr.state.value,
            repository_name=pr.repository.name if pr.repository else "",
            repository_id=pr.repository_id,
            author_name=pr.contributor.canonical_name if pr.contributor else None,
            contributor_id=pr.contributor_id,
            lines_added=pr.lines_added,
            lines_deleted=pr.lines_deleted,
            comment_count=pr.comment_count,
            review_count=len(pr.reviews) if pr.reviews else 0,
            iteration_count=pr.iteration_count,
            created_at=pr.created_at,
            merged_at=pr.merged_at,
            closed_at=pr.closed_at,
            first_review_at=pr.first_review_at,
            cycle_time_hours=_cycle_time(pr),
            review_turnaround_hours=_review_turnaround(pr),
        ))

    return PRListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/analytics", response_model=AnalyticsResponse)
async def pr_analytics(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    repository_id: uuid.UUID | None = Query(None),
):
    repo_ids_q = select(Repository.id).where(Repository.project_id == project_id)
    base = select(PullRequest).where(PullRequest.repository_id.in_(repo_ids_q))

    if repository_id:
        base = base.where(PullRequest.repository_id == repository_id)
    if from_date:
        base = base.where(PullRequest.created_at >= datetime.combine(from_date, datetime.min.time()))
    if to_date:
        base = base.where(PullRequest.created_at <= datetime.combine(to_date, datetime.max.time()))

    result = await db.execute(
        base.options(selectinload(PullRequest.reviews).selectinload(Review.reviewer))
    )
    prs = list(result.scalars().unique().all())

    total = len(prs)
    open_count = sum(1 for p in prs if p.state == PRState.OPEN)
    merged_count = sum(1 for p in prs if p.state == PRState.MERGED)
    closed_count = sum(1 for p in prs if p.state == PRState.CLOSED)

    cycle_times = [ct for p in prs if (ct := _cycle_time(p)) is not None]
    avg_ct = round(sum(cycle_times) / len(cycle_times), 1) if cycle_times else None

    turnarounds = [rt for p in prs if (rt := _review_turnaround(p)) is not None]
    avg_rt = round(sum(turnarounds) / len(turnarounds), 1) if turnarounds else None

    merge_rate = round(merged_count / total * 100, 1) if total > 0 else None

    size_buckets: dict[str, list] = {"XS": [], "S": [], "M": [], "L": [], "XL": []}
    for p in prs:
        label = _size_label(p.lines_added + p.lines_deleted)
        size_buckets[label].append(p)

    size_distribution = []
    for label in ["XS", "S", "M", "L", "XL"]:
        bucket_prs = size_buckets[label]
        bucket_cts = [ct for p in bucket_prs if (ct := _cycle_time(p)) is not None]
        size_distribution.append(SizeBucket(
            label=label,
            count=len(bucket_prs),
            avg_cycle_time_hours=round(sum(bucket_cts) / len(bucket_cts), 1) if bucket_cts else None,
        ))

    weekly: dict[str, list[float]] = {}
    for p in prs:
        ct = _cycle_time(p)
        if ct is not None and p.created_at:
            week = p.created_at.strftime("%Y-W%W")
            weekly.setdefault(week, []).append(ct)

    cycle_time_trend = [
        CycleTimeTrend(
            period=w,
            avg_cycle_time_hours=round(sum(cts) / len(cts), 1),
            pr_count=len(cts),
        )
        for w, cts in sorted(weekly.items())[-26:]
    ]

    reviewer_stats: dict[uuid.UUID, dict] = {}
    for p in prs:
        for r in (p.reviews or []):
            if not r.reviewer_id:
                continue
            if r.reviewer_id not in reviewer_stats:
                reviewer_stats[r.reviewer_id] = {
                    "name": r.reviewer.canonical_name if r.reviewer else "Unknown",
                    "count": 0,
                    "approvals": 0,
                    "turnarounds": [],
                }
            entry = reviewer_stats[r.reviewer_id]
            entry["count"] += 1
            if r.state == ReviewState.APPROVED:
                entry["approvals"] += 1
            if r.submitted_at and p.created_at:
                ta = (r.submitted_at.timestamp() - p.created_at.timestamp()) / 3600
                if ta >= 0:
                    entry["turnarounds"].append(ta)

    top_reviewers = sorted(reviewer_stats.items(), key=lambda x: x[1]["count"], reverse=True)[:20]
    reviewer_list = [
        ReviewerStat(
            reviewer_name=v["name"],
            reviewer_id=rid,
            review_count=v["count"],
            avg_turnaround_hours=round(sum(v["turnarounds"]) / len(v["turnarounds"]), 1) if v["turnarounds"] else None,
            approval_count=v["approvals"],
        )
        for rid, v in top_reviewers
    ]

    return AnalyticsResponse(
        total_prs=total,
        open_prs=open_count,
        merged_prs=merged_count,
        closed_prs=closed_count,
        avg_cycle_time_hours=avg_ct,
        avg_review_turnaround_hours=avg_rt,
        merge_rate=merge_rate,
        size_distribution=size_distribution,
        cycle_time_trend=cycle_time_trend,
        top_reviewers=reviewer_list,
    )


@router.get("/{pr_id}", response_model=PRDetailResponse)
async def get_pull_request(
    project_id: uuid.UUID,
    pr_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PullRequest)
        .where(PullRequest.id == pr_id)
        .options(
            selectinload(PullRequest.repository),
            selectinload(PullRequest.contributor),
            selectinload(PullRequest.reviews).selectinload(Review.reviewer),
            selectinload(PullRequest.comments).selectinload(PRComment.author),
        )
    )
    pr = result.scalar_one_or_none()
    if not pr:
        from fastapi import HTTPException
        raise HTTPException(404, "Pull request not found")

    reviews = [
        ReviewResponse(
            id=r.id,
            reviewer_name=r.reviewer.canonical_name if r.reviewer else None,
            reviewer_id=r.reviewer_id,
            state=r.state.value,
            comment_count=r.comment_count,
            submitted_at=r.submitted_at,
        )
        for r in (pr.reviews or [])
    ]

    comments = [
        CommentResponse(
            id=c.id,
            author_name=c.author_name,
            author_id=c.author_id,
            body=c.body,
            thread_id=c.thread_id,
            parent_comment_id=c.parent_comment_id,
            file_path=c.file_path,
            line_number=c.line_number,
            comment_type=c.comment_type.value,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in (pr.comments or [])
    ]

    return PRDetailResponse(
        id=pr.id,
        platform_pr_id=pr.platform_pr_id,
        title=pr.title,
        state=pr.state.value,
        repository_name=pr.repository.name if pr.repository else "",
        repository_id=pr.repository_id,
        author_name=pr.contributor.canonical_name if pr.contributor else None,
        contributor_id=pr.contributor_id,
        lines_added=pr.lines_added,
        lines_deleted=pr.lines_deleted,
        comment_count=pr.comment_count,
        iteration_count=pr.iteration_count,
        created_at=pr.created_at,
        merged_at=pr.merged_at,
        closed_at=pr.closed_at,
        first_review_at=pr.first_review_at,
        cycle_time_hours=_cycle_time(pr),
        review_turnaround_hours=_review_turnaround(pr),
        reviews=reviews,
        comments=comments,
    )


# ── Sync ──────────────────────────────────────────────────────────────

async def _resolve_platform_token(
    db: AsyncSession, platform: Platform | None,
) -> tuple[str | None, str | None]:
    """Look up the most recent credential for *platform*."""
    if not platform:
        return None, None

    from app.api.platform_credentials import decrypt_token

    result = await db.execute(
        select(PlatformCredential)
        .where(PlatformCredential.platform == platform)
        .order_by(PlatformCredential.created_at.desc())
        .limit(1)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        return None, None
    try:
        return decrypt_token(cred.token_encrypted), cred.base_url
    except Exception:
        return None, None


@router.post("/{pr_id}/sync", response_model=PRDetailResponse)
async def sync_pull_request(
    project_id: uuid.UUID,
    pr_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Re-fetch a single PR from its platform, updating all fields, reviews, and comments."""
    result = await db.execute(
        select(PullRequest)
        .where(PullRequest.id == pr_id)
        .options(selectinload(PullRequest.repository))
    )
    pr = result.scalar_one_or_none()
    if not pr:
        raise HTTPException(404, "Pull request not found")

    repo = pr.repository
    if not repo:
        raise HTTPException(400, "Repository not found for this pull request")

    repo_ids = (await db.execute(
        select(Repository.id).where(Repository.project_id == project_id)
    )).scalars().all()
    if repo.id not in set(repo_ids):
        raise HTTPException(404, "Pull request does not belong to this project")

    token, base_url = await _resolve_platform_token(db, repo.platform)
    if not token:
        raise HTTPException(
            400,
            f"No platform credential configured for {repo.platform.value if repo.platform else 'unknown'}. "
            "Add one in Settings > Platform Credentials.",
        )

    updated_pr: PullRequest | None = None

    if repo.platform == Platform.GITHUB:
        from app.services.github_client import sync_single_github_pr
        updated_pr = await sync_single_github_pr(db, repo, pr.platform_pr_id, token=token)

    elif repo.platform == Platform.GITLAB:
        from app.services.gitlab_client import sync_single_gitlab_mr
        gl_url = base_url or "https://gitlab.com"
        updated_pr = await sync_single_gitlab_mr(db, repo, pr.platform_pr_id, token=token, url=gl_url)

    elif repo.platform == Platform.AZURE:
        from app.services.azure_client import sync_single_azure_pr
        org_url = base_url
        if not org_url:
            owner = repo.platform_owner or ""
            parts = owner.split("/", 1)
            org = parts[0] if parts else ""
            org_url = f"https://dev.azure.com/{org}" if org else None
        updated_pr = await sync_single_azure_pr(db, repo, pr.platform_pr_id, org_url=org_url, token=token)

    if not updated_pr:
        raise HTTPException(502, "Failed to fetch PR data from the platform")

    await db.commit()

    return await get_pull_request(project_id, pr_id, db, _user)
