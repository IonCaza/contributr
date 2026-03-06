import re
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import get_db
from app.db.models import Contributor, ContributorAlias, Commit, User, DailyContributorStats, Repository, Branch, PullRequest, Review
from app.db.models.branch import commit_branches
from app.db.models.pull_request import PRState
from app.db.models.project import Project
from app.auth.dependencies import get_current_user
from app.services.metrics import get_trends

router = APIRouter(prefix="/contributors", tags=["contributors"])


class ProjectBrief(BaseModel):
    id: uuid.UUID
    name: str
    model_config = {"from_attributes": True}


class ContributorResponse(BaseModel):
    id: uuid.UUID
    canonical_name: str
    canonical_email: str
    alias_emails: list[str] | None
    alias_names: list[str] | None
    github_username: str | None
    gitlab_username: str | None
    azure_username: str | None
    projects: list[ProjectBrief]
    created_at: datetime
    model_config = {"from_attributes": True}


class MergeRequest(BaseModel):
    merge_into_id: uuid.UUID


class DuplicateGroup(BaseModel):
    group_key: str
    reason: str
    contributor_ids: list[uuid.UUID]


@router.get("/duplicates", response_model=list[DuplicateGroup])
async def get_duplicate_suggestions(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Contributor))
    contributors = result.scalars().all()

    groups: dict[str, list[uuid.UUID]] = defaultdict(list)

    for c in contributors:
        prefix = c.canonical_email.split("@")[0].lower().strip()
        if prefix:
            groups[f"email:{prefix}"].append(c.id)

        normalized = re.sub(r"[^a-z0-9]", "", c.canonical_name.lower())
        if normalized:
            groups[f"name:{normalized}"].append(c.id)

    result_groups: list[DuplicateGroup] = []
    for key, ids in groups.items():
        if len(ids) < 2:
            continue
        kind, value = key.split(":", 1)
        if kind == "email":
            reason = f"Same email prefix: {value}"
        else:
            reason = f"Similar name: {value}"
        result_groups.append(DuplicateGroup(group_key=key, reason=reason, contributor_ids=ids))

    return result_groups


@router.get("", response_model=list[ContributorResponse])
async def list_contributors(
    project_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = select(Contributor).options(selectinload(Contributor.projects)).order_by(Contributor.canonical_name)
    if project_id:
        from app.db.models.project import project_contributors
        query = query.join(project_contributors).where(project_contributors.c.project_id == project_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{contributor_id}", response_model=ContributorResponse)
async def get_contributor(contributor_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Contributor).options(selectinload(Contributor.projects)).where(Contributor.id == contributor_id)
    )
    contributor = result.scalar_one_or_none()
    if contributor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contributor not found")
    return contributor


@router.post("/{contributor_id}/merge", status_code=status.HTTP_200_OK)
async def merge_contributors(
    contributor_id: uuid.UUID,
    body: MergeRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Merge contributor_id INTO merge_into_id. Re-assigns all commits, adds alias."""
    if contributor_id == body.merge_into_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot merge a contributor into itself")

    source = await db.get(Contributor, contributor_id)
    target = await db.get(Contributor, body.merge_into_id)
    if not source or not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contributor not found")

    from sqlalchemy import update, delete, and_

    await db.execute(update(Commit).where(Commit.contributor_id == source.id).values(contributor_id=target.id))

    target_keys = await db.execute(
        select(DailyContributorStats.repository_id, DailyContributorStats.date)
        .where(DailyContributorStats.contributor_id == target.id)
    )
    existing_keys = {(row.repository_id, row.date) for row in target_keys.all()}

    source_stats = await db.execute(
        select(DailyContributorStats).where(DailyContributorStats.contributor_id == source.id)
    )
    for s in source_stats.scalars().all():
        if (s.repository_id, s.date) in existing_keys:
            await db.execute(
                update(DailyContributorStats)
                .where(and_(
                    DailyContributorStats.contributor_id == target.id,
                    DailyContributorStats.repository_id == s.repository_id,
                    DailyContributorStats.date == s.date,
                ))
                .values(
                    commits=DailyContributorStats.commits + s.commits,
                    lines_added=DailyContributorStats.lines_added + s.lines_added,
                    lines_deleted=DailyContributorStats.lines_deleted + s.lines_deleted,
                    files_changed=DailyContributorStats.files_changed + s.files_changed,
                    merges=DailyContributorStats.merges + s.merges,
                    prs_opened=DailyContributorStats.prs_opened + s.prs_opened,
                    prs_merged=DailyContributorStats.prs_merged + s.prs_merged,
                    reviews_given=DailyContributorStats.reviews_given + s.reviews_given,
                )
            )
            await db.delete(s)
        else:
            s.contributor_id = target.id

    alias = ContributorAlias(contributor_id=target.id, email=source.canonical_email, name=source.canonical_name)
    db.add(alias)

    if target.alias_emails is None:
        target.alias_emails = []
    if source.canonical_email not in target.alias_emails:
        target.alias_emails = [*target.alias_emails, source.canonical_email]
    if target.alias_names is None:
        target.alias_names = []
    if source.canonical_name not in target.alias_names and source.canonical_name != target.canonical_name:
        target.alias_names = [*target.alias_names, source.canonical_name]

    await db.delete(source)
    await db.commit()
    return {"merged": True, "target_id": str(target.id)}


class ContributorRepoResponse(BaseModel):
    id: uuid.UUID
    name: str
    platform: str
    model_config = {"from_attributes": True}


@router.get("/{contributor_id}/repositories", response_model=list[ContributorRepoResponse])
async def get_contributor_repositories(
    contributor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Repository)
        .join(Commit, Commit.repository_id == Repository.id)
        .where(Commit.contributor_id == contributor_id)
        .distinct()
        .order_by(Repository.name)
    )
    return result.scalars().all()


def _filtered_commit_base(
    contributor_id: uuid.UUID,
    *,
    from_date: date | None = None,
    to_date: date | None = None,
    repository_id: uuid.UUID | None = None,
    branch_names: list[str] | None = None,
):
    """Return a base select(Commit) with contributor + optional filters applied."""
    q = select(Commit).where(Commit.contributor_id == contributor_id)
    if from_date:
        q = q.where(Commit.authored_at >= from_date)
    if to_date:
        q = q.where(Commit.authored_at <= to_date + timedelta(days=1))
    if repository_id:
        q = q.where(Commit.repository_id == repository_id)
    if branch_names:
        q = (
            q.join(commit_branches, commit_branches.c.commit_id == Commit.id)
            .join(Branch, Branch.id == commit_branches.c.branch_id)
            .where(Branch.name.in_(branch_names))
        )
    return q


@router.get("/{contributor_id}/stats")
async def get_contributor_stats(
    contributor_id: uuid.UUID,
    from_date: date | None = None,
    to_date: date | None = None,
    repository_id: uuid.UUID | None = None,
    branch: list[str] = Query(default=[]),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Contributor).where(Contributor.id == contributor_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contributor not found")

    branch_names = branch or None
    base = _filtered_commit_base(
        contributor_id,
        from_date=from_date,
        to_date=to_date,
        repository_id=repository_id,
        branch_names=branch_names,
    )

    sub = base.with_only_columns(Commit.id).distinct().subquery()
    total_commits = await db.scalar(select(func.count()).select_from(sub))

    agg_q = select(
        func.coalesce(func.sum(Commit.lines_added), 0).label("la"),
        func.coalesce(func.sum(Commit.lines_deleted), 0).label("ld"),
        func.count(Commit.repository_id.distinct()).label("rc"),
    ).where(Commit.id.in_(select(sub.c.id)))
    agg = (await db.execute(agg_q)).one()
    total_lines_added = agg.la
    total_lines_deleted = agg.ld
    repo_count = agg.rc

    trends = await get_trends(
        db,
        contributor_id=contributor_id,
        repository_id=repository_id,
        branch_names=branch_names,
    )

    # Streak: filter by repo/branch but not date range
    streak_base = _filtered_commit_base(
        contributor_id,
        repository_id=repository_id,
        branch_names=branch_names,
    )
    day_col = func.date_trunc("day", Commit.authored_at).label("d")
    streak_sub = (
        streak_base.with_only_columns(day_col)
        .distinct()
        .subquery()
    )
    streak_q = select(streak_sub.c.d).order_by(streak_sub.c.d.desc())
    active_days_result = await db.execute(streak_q)
    active_dates = [r.d.date() if hasattr(r.d, "date") else r.d for r in active_days_result.all()]

    streak = 0
    if active_dates:
        current = date.today()
        for d in active_dates:
            if d == current or d == current - timedelta(days=1):
                streak += 1
                current = d - timedelta(days=1)
            else:
                break

    avg_commit_size = round((total_lines_added + total_lines_deleted) / total_commits, 1) if total_commits else 0
    code_velocity = total_lines_added - total_lines_deleted

    merge_q = select(func.count()).where(Commit.id.in_(select(sub.c.id)), Commit.is_merge.is_(True))
    merge_count = await db.scalar(merge_q) or 0
    merge_ratio = round(merge_count / total_commits * 100, 1) if total_commits else 0

    active_days_q = (
        select(func.count(func.distinct(func.date_trunc("day", Commit.authored_at))))
        .where(Commit.id.in_(select(sub.c.id)))
    )
    active_days = await db.scalar(active_days_q) or 0

    repo_ids_q = select(Commit.repository_id.distinct()).where(Commit.contributor_id == contributor_id)
    repo_ids_sub = repo_ids_q.subquery()

    reviews_q = (
        select(func.count())
        .select_from(Review)
        .where(Review.reviewer_id == contributor_id)
    )
    reviews_given = await db.scalar(reviews_q) or 0

    prs_authored_q = (
        select(func.count())
        .select_from(PullRequest)
        .where(PullRequest.contributor_id == contributor_id)
    )
    prs_authored = await db.scalar(prs_authored_q) or 0

    review_engagement = round(reviews_given / prs_authored, 2) if prs_authored else 0

    impact_score = round(
        total_commits * 1
        + (total_lines_added + total_lines_deleted) * 0.1
        + prs_authored * 5
        + reviews_given * 3,
        1,
    )

    return {
        "total_commits": total_commits,
        "total_lines_added": total_lines_added,
        "total_lines_deleted": total_lines_deleted,
        "repository_count": repo_count,
        "current_streak_days": streak,
        "avg_commit_size": avg_commit_size,
        "code_velocity": code_velocity,
        "merge_ratio": merge_ratio,
        "active_days": active_days,
        "review_engagement": review_engagement,
        "impact_score": impact_score,
        "prs_authored": prs_authored,
        "reviews_given": reviews_given,
        "trends": trends,
    }
