"""Contributor PR Quality analyzers: review turnaround, PR iterations, abandonment, review depth, network diversity, time-to-first-review."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, distinct, and_, extract, case, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.pull_request import PullRequest
from app.db.models.review import Review
from app.db.models.repository import Repository
from app.services.insights.types import RawFinding

CATEGORY = "pr_quality"


async def analyze_review_turnaround(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Median time between PR creation and this person submitting a review (as reviewer)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    q = select(
        func.percentile_cont(0.5).within_group(
            extract("epoch", Review.submitted_at - PullRequest.created_at) / 3600
        ),
        func.count(),
    ).select_from(
        Review.__table__.join(PullRequest.__table__, Review.pull_request_id == PullRequest.id)
    ).where(
        Review.reviewer_id == contributor_id,
        Review.submitted_at >= cutoff,
    )
    row = (await db.execute(q)).one()
    median_hours = round(float(row[0] or 0), 1)
    count = row[1] or 0

    if count < 5:
        return []

    findings: list[RawFinding] = []

    if median_hours > 24:
        severity = "warning" if median_hours > 48 else "info"
        findings.append(RawFinding(
            category=CATEGORY,
            severity=severity,
            slug="slow-review-turnaround",
            title=f"Review turnaround median is {round(median_hours)}h ({count} reviews)",
            description=(
                f"When this contributor is assigned as a reviewer, it takes a median of "
                f"{round(median_hours)} hours to submit a review. Slow reviews block teammates "
                f"and increase cycle time for the entire team."
            ),
            recommendation=(
                "Set aside dedicated review time (e.g. first thing in the morning). Use notifications "
                "or a review dashboard to stay on top of pending reviews. Consider setting a team SLA "
                "for review turnaround (e.g. 4 business hours)."
            ),
            metric_data={
                "median_turnaround_hours": median_hours,
                "reviews_analyzed": count,
            },
        ))

    return findings


async def analyze_pr_iteration_count(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Average iteration count on authored PRs."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    q = select(
        func.avg(PullRequest.iteration_count),
        func.max(PullRequest.iteration_count),
        func.count(),
    ).where(
        PullRequest.contributor_id == contributor_id,
        PullRequest.created_at >= cutoff,
        PullRequest.iteration_count > 0,
    )
    row = (await db.execute(q)).one()
    avg_iterations = round(float(row[0] or 0), 1)
    max_iterations = row[1] or 0
    count = row[2] or 0

    if count < 5:
        return []

    findings: list[RawFinding] = []

    if avg_iterations > 3:
        severity = "warning" if avg_iterations > 5 else "info"
        findings.append(RawFinding(
            category=CATEGORY,
            severity=severity,
            slug="high-pr-iterations",
            title=f"PRs require an average of {avg_iterations} review iterations",
            description=(
                f"Across {count} PRs, this contributor's pull requests average {avg_iterations} "
                f"review iterations (max: {max_iterations}). High iteration counts slow delivery "
                f"and may indicate unclear requirements, incomplete implementation, or misaligned "
                f"coding standards."
            ),
            recommendation=(
                "Review coding standards before submitting. Write clear PR descriptions explaining "
                "the 'why'. Consider running a self-review checklist before requesting reviews. "
                "For large changes, discuss the approach upfront to avoid rework."
            ),
            metric_data={
                "avg_iterations": avg_iterations,
                "max_iterations": max_iterations,
                "prs_analyzed": count,
            },
        ))

    return findings


async def analyze_pr_abandonment(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """PRs opened but neither merged nor closed after 30 days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    abandoned_q = select(
        func.count(),
        func.array_agg(PullRequest.title),
    ).where(
        PullRequest.contributor_id == contributor_id,
        PullRequest.state == "open",
        PullRequest.created_at < cutoff,
        PullRequest.merged_at.is_(None),
        PullRequest.closed_at.is_(None),
    )
    row = (await db.execute(abandoned_q)).one()
    abandoned_count = row[0] or 0
    titles = row[1] or []

    if abandoned_count == 0:
        return []

    total_open_q = select(func.count()).select_from(PullRequest).where(
        PullRequest.contributor_id == contributor_id,
        PullRequest.state == "open",
    )
    total_open = (await db.execute(total_open_q)).scalar() or 0

    findings: list[RawFinding] = []

    findings.append(RawFinding(
        category=CATEGORY,
        severity="warning" if abandoned_count > 3 else "info",
        slug="abandoned-prs",
        title=f"{abandoned_count} open PRs older than 30 days",
        description=(
            f"This contributor has {abandoned_count} pull requests that have been open for more than "
            f"30 days without being merged or closed. Stale PRs accumulate merge conflicts and create "
            f"confusion about the state of the codebase."
        ),
        recommendation=(
            "Close PRs that are no longer needed. For PRs that are still relevant, rebase and "
            "re-request reviews. Consider a weekly PR grooming session to keep the list clean."
        ),
        metric_data={
            "abandoned_count": abandoned_count,
            "total_open_prs": total_open,
            "stale_titles": titles[:10],
        },
    ))

    return findings


async def analyze_review_depth(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Check if this reviewer gives zero-comment approvals frequently."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    q = select(
        func.count(),
        func.sum(case((Review.comment_count == 0, 1), else_=0)),
        func.avg(Review.comment_count),
    ).where(
        Review.reviewer_id == contributor_id,
        Review.submitted_at >= cutoff,
    )
    row = (await db.execute(q)).one()
    total_reviews = row[0] or 0
    zero_comment = int(row[1] or 0)
    avg_comments = round(float(row[2] or 0), 1)

    if total_reviews < 5:
        return []

    zero_pct = round((zero_comment / total_reviews) * 100, 1) if total_reviews else 0

    findings: list[RawFinding] = []

    if zero_pct > 60:
        findings.append(RawFinding(
            category=CATEGORY,
            severity="info",
            slug="shallow-reviews",
            title=f"{zero_pct}% of reviews have zero comments ({zero_comment}/{total_reviews})",
            description=(
                f"This reviewer approved or submitted {zero_pct}% of their reviews without "
                f"any inline comments. Average comment count per review is {avg_comments}. "
                f"While not every review needs extensive comments, consistently zero-comment "
                f"approvals may mean reviews aren't catching issues."
            ),
            recommendation=(
                "Even brief comments (noting what was checked, or a positive observation) add value. "
                "Use a review checklist to ensure thorough reviews. Consider pairing on reviews "
                "for complex PRs."
            ),
            metric_data={
                "total_reviews": total_reviews,
                "zero_comment_reviews": zero_comment,
                "zero_comment_pct": zero_pct,
                "avg_comments_per_review": avg_comments,
            },
        ))

    return findings


async def analyze_review_network_diversity(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """How many distinct people review their PRs / they review."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    # Distinct reviewers on this person's PRs
    reviewers_of_me_q = (
        select(func.count(distinct(Review.reviewer_id)))
        .select_from(
            Review.__table__.join(PullRequest.__table__, Review.pull_request_id == PullRequest.id)
        )
        .where(
            PullRequest.contributor_id == contributor_id,
            Review.submitted_at >= cutoff,
            Review.reviewer_id != contributor_id,
        )
    )
    reviewers_of_me = (await db.execute(reviewers_of_me_q)).scalar() or 0

    # Distinct people this person reviews
    i_review_q = (
        select(func.count(distinct(PullRequest.contributor_id)))
        .select_from(
            Review.__table__.join(PullRequest.__table__, Review.pull_request_id == PullRequest.id)
        )
        .where(
            Review.reviewer_id == contributor_id,
            Review.submitted_at >= cutoff,
            PullRequest.contributor_id != contributor_id,
        )
    )
    i_review = (await db.execute(i_review_q)).scalar() or 0

    total_network = reviewers_of_me + i_review

    if total_network == 0:
        return []

    findings: list[RawFinding] = []

    if reviewers_of_me <= 1 and i_review <= 1:
        findings.append(RawFinding(
            category=CATEGORY,
            severity="warning",
            slug="review-silo",
            title=f"Review network limited to {total_network} unique connections",
            description=(
                f"This contributor's PRs are reviewed by only {reviewers_of_me} distinct reviewer(s), "
                f"and they review work from only {i_review} other contributor(s). A narrow review "
                f"network concentrates knowledge and creates bottlenecks."
            ),
            recommendation=(
                "Rotate reviewers across the team. Request reviews from people outside the immediate "
                "circle to spread knowledge. Review PRs in unfamiliar areas to build breadth."
            ),
            metric_data={
                "reviewers_of_my_prs": reviewers_of_me,
                "people_i_review": i_review,
            },
        ))

    return findings


async def analyze_time_to_first_review(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Median time from PR creation to first_review_at on authored PRs."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    q = select(
        func.percentile_cont(0.5).within_group(
            extract("epoch", PullRequest.first_review_at - PullRequest.created_at) / 3600
        ),
        func.percentile_cont(0.9).within_group(
            extract("epoch", PullRequest.first_review_at - PullRequest.created_at) / 3600
        ),
        func.count(),
    ).where(
        PullRequest.contributor_id == contributor_id,
        PullRequest.first_review_at.isnot(None),
        PullRequest.created_at >= cutoff,
    )
    row = (await db.execute(q)).one()
    median_hours = round(float(row[0] or 0), 1)
    p90_hours = round(float(row[1] or 0), 1)
    count = row[2] or 0

    if count < 5:
        return []

    findings: list[RawFinding] = []

    if median_hours > 24:
        severity = "warning" if median_hours > 48 else "info"
        findings.append(RawFinding(
            category=CATEGORY,
            severity=severity,
            slug="slow-first-review",
            title=f"PRs wait a median of {round(median_hours)}h before first review",
            description=(
                f"Across {count} PRs, the median time from opening a PR to receiving the first review "
                f"is {round(median_hours)} hours (P90: {round(p90_hours)}h). Long wait times reduce "
                f"developer momentum and increase context-switching costs."
            ),
            recommendation=(
                "This is often a team-level issue, not individual. Discuss a team review SLA. "
                "Tag reviewers explicitly when creating PRs. Smaller PRs tend to get reviewed faster. "
                "Consider pair-reviewing for high-priority changes."
            ),
            metric_data={
                "median_wait_hours": median_hours,
                "p90_wait_hours": p90_hours,
                "prs_analyzed": count,
            },
        ))

    return findings
