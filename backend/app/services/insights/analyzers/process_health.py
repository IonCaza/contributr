"""Process Health analyzers: commit message quality, PR compliance, PR size, branch hygiene."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_, not_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.commit import Commit
from app.db.models.repository import Repository
from app.db.models.pull_request import PullRequest, PRState
from app.db.models.review import Review, ReviewState
from app.db.models.branch import Branch
from app.services.insights.types import RawFinding

CATEGORY = "process"
WI_REF_RE = re.compile(r"(?:AB)?#\d{2,}")


async def analyze_commit_message_quality(
    db: AsyncSession, project_id: uuid.UUID,
) -> list[RawFinding]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    repo_ids = select(Repository.id).where(Repository.project_id == project_id)

    total_q = select(func.count()).select_from(Commit).where(
        Commit.repository_id.in_(repo_ids),
        Commit.authored_at >= cutoff,
        Commit.is_merge.is_(False),
    )
    total = (await db.execute(total_q)).scalar() or 0
    if total == 0:
        return []

    short_q = select(func.count()).select_from(Commit).where(
        Commit.repository_id.in_(repo_ids),
        Commit.authored_at >= cutoff,
        Commit.is_merge.is_(False),
        func.length(Commit.message) < 10,
    )
    short_count = (await db.execute(short_q)).scalar() or 0

    all_commits_q = select(Commit.message).where(
        Commit.repository_id.in_(repo_ids),
        Commit.authored_at >= cutoff,
        Commit.is_merge.is_(False),
        Commit.message.isnot(None),
    )
    messages = (await db.execute(all_commits_q)).scalars().all()

    no_ref_count = sum(1 for m in messages if not WI_REF_RE.search(m))
    bad_pct = round((short_count / total) * 100, 1) if total else 0
    no_ref_pct = round((no_ref_count / total) * 100, 1) if total else 0

    findings: list[RawFinding] = []

    if bad_pct > 30:
        severity = "critical" if bad_pct > 60 else "warning"
        sample_bad = [m[:80] for m in messages if m and len(m) < 10][:5]
        findings.append(RawFinding(
            category=CATEGORY,
            severity=severity,
            slug="commit-msg-quality",
            title=f"{bad_pct}% of commits have non-descriptive messages",
            description=(
                f"Out of {total} non-merge commits in the last 90 days, "
                f"{short_count} ({bad_pct}%) have messages shorter than 10 characters."
            ),
            recommendation="Establish commit message guidelines requiring a minimum length and a reference to a work item.",
            metric_data={
                "total_commits": total,
                "short_messages": short_count,
                "short_pct": bad_pct,
                "sample_bad_messages": sample_bad,
            },
        ))

    if no_ref_pct > 50:
        severity = "critical" if no_ref_pct > 75 else "warning"
        findings.append(RawFinding(
            category=CATEGORY,
            severity=severity,
            slug="commit-msg-no-wi-ref",
            title=f"{no_ref_pct}% of commits lack a work item reference",
            description=(
                f"{no_ref_count} out of {total} commits do not contain a work item reference "
                f"(e.g. #1234 or AB#1234). This makes it harder to trace code changes to requirements."
            ),
            recommendation="Adopt a convention of including the work item ID in every commit message, and consider pre-commit hooks to enforce it.",
            metric_data={
                "total_commits": total,
                "no_reference": no_ref_count,
                "no_ref_pct": no_ref_pct,
            },
        ))

    return findings


async def analyze_pr_process_compliance(
    db: AsyncSession, project_id: uuid.UUID,
) -> list[RawFinding]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    repo_ids = select(Repository.id).where(Repository.project_id == project_id)

    findings: list[RawFinding] = []

    # PRs merged with 0 reviews
    no_review_q = (
        select(func.count())
        .select_from(PullRequest)
        .outerjoin(Review)
        .where(
            PullRequest.repository_id.in_(repo_ids),
            PullRequest.state == PRState.MERGED,
            PullRequest.merged_at >= cutoff,
        )
        .group_by(PullRequest.id)
        .having(func.count(Review.id) == 0)
    )
    no_review_subq = select(func.count()).select_from(no_review_q.subquery())
    no_review_count = (await db.execute(no_review_subq)).scalar() or 0

    total_merged_q = select(func.count()).select_from(PullRequest).where(
        PullRequest.repository_id.in_(repo_ids),
        PullRequest.state == PRState.MERGED,
        PullRequest.merged_at >= cutoff,
    )
    total_merged = (await db.execute(total_merged_q)).scalar() or 0

    if total_merged > 0 and no_review_count > 0:
        pct = round((no_review_count / total_merged) * 100, 1)
        severity = "critical" if pct > 30 else "warning"
        findings.append(RawFinding(
            category=CATEGORY,
            severity=severity,
            slug="pr-no-review",
            title=f"{no_review_count} PRs merged without any review ({pct}%)",
            description=(
                f"In the last 90 days, {no_review_count} of {total_merged} merged PRs had zero reviews. "
                f"Code review is a key quality gate."
            ),
            recommendation="Enforce branch protection rules requiring at least one approving review before merge.",
            metric_data={
                "total_merged": total_merged,
                "no_review_count": no_review_count,
                "pct": pct,
            },
        ))

    # PRs merged with outstanding changes_requested
    changes_requested_q = (
        select(PullRequest.id)
        .join(Review)
        .where(
            PullRequest.repository_id.in_(repo_ids),
            PullRequest.state == PRState.MERGED,
            PullRequest.merged_at >= cutoff,
            Review.state == ReviewState.CHANGES_REQUESTED,
        )
        .group_by(PullRequest.id)
    )
    cr_sub = changes_requested_q.subquery()
    cr_count = (await db.execute(select(func.count()).select_from(cr_sub))).scalar() or 0

    if cr_count > 0:
        findings.append(RawFinding(
            category=CATEGORY,
            severity="warning",
            slug="pr-merged-with-changes-requested",
            title=f"{cr_count} PRs merged despite outstanding change requests",
            description=(
                f"{cr_count} PRs were merged even though at least one reviewer requested changes. "
                f"This may indicate review feedback is being ignored."
            ),
            recommendation="Configure branch protection to block merges when there are outstanding change requests.",
            metric_data={"count": cr_count},
        ))

    return findings


async def analyze_pr_size_distribution(
    db: AsyncSession, project_id: uuid.UUID,
) -> list[RawFinding]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    repo_ids = select(Repository.id).where(Repository.project_id == project_id)

    total_q = select(func.count()).select_from(PullRequest).where(
        PullRequest.repository_id.in_(repo_ids),
        PullRequest.created_at >= cutoff,
    )
    total = (await db.execute(total_q)).scalar() or 0
    if total == 0:
        return []

    oversized_q = select(func.count()).select_from(PullRequest).where(
        PullRequest.repository_id.in_(repo_ids),
        PullRequest.created_at >= cutoff,
        (PullRequest.lines_added + PullRequest.lines_deleted) > 500,
    )
    oversized = (await db.execute(oversized_q)).scalar() or 0
    pct = round((oversized / total) * 100, 1)

    if pct <= 25:
        return []

    size_stats_q = select(
        func.percentile_cont(0.5).within_group(PullRequest.lines_added + PullRequest.lines_deleted),
        func.percentile_cont(0.9).within_group(PullRequest.lines_added + PullRequest.lines_deleted),
    ).where(
        PullRequest.repository_id.in_(repo_ids),
        PullRequest.created_at >= cutoff,
    )
    row = (await db.execute(size_stats_q)).one()
    median_size = round(row[0] or 0)
    p90_size = round(row[1] or 0)

    return [RawFinding(
        category=CATEGORY,
        severity="warning",
        slug="pr-too-large",
        title=f"{pct}% of PRs exceed 500 lines changed",
        description=(
            f"{oversized} of {total} recent PRs have more than 500 lines changed. "
            f"Large PRs are harder to review and more likely to introduce bugs. "
            f"Median PR size: {median_size} lines, P90: {p90_size} lines."
        ),
        recommendation="Break large changes into smaller, focused PRs. Aim for fewer than 400 lines per PR.",
        metric_data={
            "total_prs": total,
            "oversized_count": oversized,
            "oversized_pct": pct,
            "median_size": median_size,
            "p90_size": p90_size,
        },
    )]


async def analyze_branch_hygiene(
    db: AsyncSession, project_id: uuid.UUID,
) -> list[RawFinding]:
    repo_ids = select(Repository.id).where(Repository.project_id == project_id)
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    stale_q = (
        select(Branch.name, Branch.repository_id, func.max(Commit.authored_at).label("last_commit"))
        .outerjoin(Branch.commits)
        .where(
            Branch.repository_id.in_(repo_ids),
            Branch.is_default.is_(False),
        )
        .group_by(Branch.id)
        .having(func.coalesce(func.max(Commit.authored_at), cutoff - timedelta(days=1)) < cutoff)
    )
    stale_rows = (await db.execute(stale_q)).all()

    findings: list[RawFinding] = []

    if len(stale_rows) > 5:
        sample = [r.name for r in stale_rows[:10]]
        findings.append(RawFinding(
            category=CATEGORY,
            severity="info",
            slug="stale-branches",
            title=f"{len(stale_rows)} stale branches with no commits in 30+ days",
            description=(
                f"There are {len(stale_rows)} non-default branches with no commit activity "
                f"in the last 30 days. Stale branches add clutter and risk merge conflicts."
            ),
            recommendation="Periodically delete merged and inactive branches. Consider automating branch cleanup.",
            metric_data={
                "stale_count": len(stale_rows),
                "sample_branches": sample,
            },
        ))

    total_branches_q = select(func.count()).select_from(Branch).where(
        Branch.repository_id.in_(repo_ids),
        Branch.is_default.is_(False),
    )
    total_branches = (await db.execute(total_branches_q)).scalar() or 0

    if total_branches > 5:
        no_separator_q = select(func.count()).select_from(Branch).where(
            Branch.repository_id.in_(repo_ids),
            Branch.is_default.is_(False),
            not_(Branch.name.contains("/")),
        )
        no_sep = (await db.execute(no_separator_q)).scalar() or 0
        pct = round((no_sep / total_branches) * 100, 1) if total_branches else 0

        if pct > 50:
            findings.append(RawFinding(
                category=CATEGORY,
                severity="info",
                slug="branch-naming",
                title=f"{pct}% of branches lack a naming convention separator",
                description=(
                    f"{no_sep} of {total_branches} branches don't use a '/' separator "
                    f"(e.g. feature/xyz, bugfix/abc), suggesting no enforced naming convention."
                ),
                recommendation="Adopt a branch naming convention like type/description (e.g. feature/user-auth).",
                metric_data={
                    "total_branches": total_branches,
                    "no_separator": no_sep,
                    "pct": pct,
                },
            ))

    return findings
