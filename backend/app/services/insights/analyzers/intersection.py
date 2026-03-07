"""Code-Delivery Intersection analyzers: commit-work item linkage, estimation accuracy."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.commit import Commit
from app.db.models.repository import Repository
from app.db.models.work_item import WorkItem
from app.db.models.work_item_commit import WorkItemCommit
from app.services.insights.types import RawFinding

CATEGORY = "intersection"


async def analyze_commit_work_item_linkage(
    db: AsyncSession, project_id: uuid.UUID,
) -> list[RawFinding]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    repo_ids = select(Repository.id).where(Repository.project_id == project_id)

    total_commits_q = select(func.count()).select_from(Commit).where(
        Commit.repository_id.in_(repo_ids),
        Commit.authored_at >= cutoff,
        Commit.is_merge.is_(False),
    )
    total_commits = (await db.execute(total_commits_q)).scalar() or 0
    if total_commits == 0:
        return []

    linked_q = select(func.count(func.distinct(WorkItemCommit.commit_id))).where(
        WorkItemCommit.commit_id.in_(
            select(Commit.id).where(
                Commit.repository_id.in_(repo_ids),
                Commit.authored_at >= cutoff,
                Commit.is_merge.is_(False),
            )
        )
    )
    linked = (await db.execute(linked_q)).scalar() or 0
    coverage_pct = round((linked / total_commits) * 100, 1)

    if coverage_pct >= 50:
        return []

    # Per-repo breakdown
    per_repo_q = (
        select(
            Repository.id,
            Repository.name,
            func.count(Commit.id).label("total"),
        )
        .join(Commit, Commit.repository_id == Repository.id)
        .where(
            Repository.project_id == project_id,
            Commit.authored_at >= cutoff,
            Commit.is_merge.is_(False),
        )
        .group_by(Repository.id)
    )
    repo_totals = {r.id: (r.name, r.total) for r in (await db.execute(per_repo_q)).all()}

    linked_per_repo_q = (
        select(
            Commit.repository_id,
            func.count(func.distinct(WorkItemCommit.commit_id)).label("linked"),
        )
        .join(Commit, WorkItemCommit.commit_id == Commit.id)
        .where(
            Commit.repository_id.in_(repo_ids),
            Commit.authored_at >= cutoff,
            Commit.is_merge.is_(False),
        )
        .group_by(Commit.repository_id)
    )
    linked_map = {r.repository_id: r.linked for r in (await db.execute(linked_per_repo_q)).all()}

    per_repo = []
    for rid, (rname, rtotal) in repo_totals.items():
        rlinked = linked_map.get(rid, 0)
        per_repo.append({
            "name": rname,
            "total_commits": rtotal,
            "linked_commits": rlinked,
            "coverage_pct": round((rlinked / rtotal) * 100, 1) if rtotal else 0,
        })

    severity = "critical" if coverage_pct < 25 else "warning"
    return [RawFinding(
        category=CATEGORY,
        severity=severity,
        slug="commit-wi-linkage",
        title=f"Only {coverage_pct}% of commits are linked to work items",
        description=(
            f"Out of {total_commits} non-merge commits in 90 days, only {linked} ({coverage_pct}%) "
            f"are linked to work items. Low linkage makes it hard to trace code changes to requirements."
        ),
        recommendation="Include work item references in commit messages (e.g. #1234). Configure automated linking in your CI pipeline.",
        metric_data={
            "overall_coverage_pct": coverage_pct,
            "total_commits": total_commits,
            "linked_commits": linked,
            "per_repo": per_repo,
        },
    )]


async def analyze_estimation_accuracy(
    db: AsyncSession, project_id: uuid.UUID,
) -> list[RawFinding]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    items_q = (
        select(
            WorkItem.id,
            WorkItem.title,
            WorkItem.story_points,
            func.count(WorkItemCommit.commit_id).label("commit_count"),
        )
        .outerjoin(WorkItemCommit, WorkItemCommit.work_item_id == WorkItem.id)
        .where(
            WorkItem.project_id == project_id,
            WorkItem.resolved_at.isnot(None),
            WorkItem.resolved_at >= cutoff,
            WorkItem.story_points.isnot(None),
            WorkItem.story_points > 0,
        )
        .group_by(WorkItem.id)
        .having(func.count(WorkItemCommit.commit_id) > 0)
    )
    rows = (await db.execute(items_q)).all()

    if len(rows) < 5:
        return []

    efforts = []
    for r in rows:
        cpp = r.commit_count / r.story_points
        efforts.append({
            "id": str(r.id),
            "title": r.title[:80] if r.title else "?",
            "story_points": float(r.story_points),
            "commits": r.commit_count,
            "commits_per_point": round(cpp, 2),
        })

    all_cpp = [e["commits_per_point"] for e in efforts]
    avg_cpp = sum(all_cpp) / len(all_cpp)
    variance = sum((c - avg_cpp) ** 2 for c in all_cpp) / len(all_cpp)

    outliers = [e for e in efforts if e["commits_per_point"] > avg_cpp * 3]

    findings: list[RawFinding] = []

    if outliers:
        findings.append(RawFinding(
            category=CATEGORY,
            severity="warning",
            slug="estimation-outliers",
            title=f"{len(outliers)} work items took 3x+ more effort than estimated",
            description=(
                f"Average effort ratio is {round(avg_cpp, 1)} commits per story point. "
                f"{len(outliers)} items significantly exceeded this, suggesting underestimation."
            ),
            recommendation="Review outlier items in retrospectives. Consider breaking down large stories before estimation.",
            metric_data={
                "avg_commits_per_point": round(avg_cpp, 2),
                "variance": round(variance, 2),
                "outlier_count": len(outliers),
                "outlier_items": outliers[:5],
                "total_items": len(rows),
            },
        ))

    if variance > avg_cpp * avg_cpp:
        findings.append(RawFinding(
            category=CATEGORY,
            severity="warning",
            slug="estimation-high-variance",
            title="Story point estimates have very high variance",
            description=(
                f"The variance of commits-per-story-point is {round(variance, 1)}, "
                f"much higher than expected. Estimates are unreliable as a planning tool."
            ),
            recommendation="Calibrate estimation with reference stories. Use relative sizing and re-estimate based on actual effort.",
            metric_data={
                "avg_commits_per_point": round(avg_cpp, 2),
                "variance": round(variance, 2),
                "total_items": len(rows),
            },
        ))

    return findings
