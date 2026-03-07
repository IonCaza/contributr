"""Contributor-focused analyzers: habits, code craft, collaboration, growth, knowledge."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from sqlalchemy import select, func, case, and_, distinct, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.commit import Commit
from app.db.models.commit_file import CommitFile
from app.db.models.repository import Repository
from app.db.models.pull_request import PullRequest, PRState
from app.db.models.review import Review, ReviewState
from app.db.models.branch import Branch
from app.db.models.contributor import Contributor
from app.services.insights.types import RawFinding

WI_REF_RE = re.compile(r"(?:AB)?#\d{2,}")


async def analyze_commit_consistency(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Check how consistently the contributor commits over time."""
    now = datetime.now(timezone.utc)
    cutoff_90 = now - timedelta(days=90)

    day_counts_q = (
        select(
            func.date_trunc("day", Commit.authored_at).label("d"),
            func.count().label("cnt"),
        )
        .where(
            Commit.contributor_id == contributor_id,
            Commit.authored_at >= cutoff_90,
            Commit.is_merge.is_(False),
        )
        .group_by(text("1"))
    )
    rows = (await db.execute(day_counts_q)).all()
    if len(rows) < 5:
        return []

    active_days = len(rows)
    total_days = 90
    consistency_pct = round((active_days / total_days) * 100, 1)

    weekly_buckets: dict[int, int] = defaultdict(int)
    for r in rows:
        week = (now - r.d.replace(tzinfo=timezone.utc)).days // 7
        weekly_buckets[week] += r.cnt

    weekly_counts = [weekly_buckets.get(w, 0) for w in range(13)]
    weeks_with_no_commits = sum(1 for w in weekly_counts if w == 0)
    avg_per_active_day = round(sum(r.cnt for r in rows) / active_days, 1)

    findings: list[RawFinding] = []

    if weeks_with_no_commits >= 4 and active_days < 40:
        findings.append(RawFinding(
            category="habits",
            severity="info",
            slug="inconsistent-commit-cadence",
            title=f"Active on only {active_days} of the last 90 days ({consistency_pct}%)",
            description=(
                f"This contributor had {weeks_with_no_commits} weeks with zero commits out of the last 13. "
                f"Inconsistent cadence can indicate context-switching, blockers, or work not being captured in commits."
            ),
            recommendation=(
                "Try to commit smaller increments more frequently. If blockers are causing gaps, "
                "raise them earlier. Consider breaking large tasks into daily-committable chunks."
            ),
            metric_data={
                "active_days": active_days,
                "total_days": total_days,
                "consistency_pct": consistency_pct,
                "weeks_without_commits": weeks_with_no_commits,
                "avg_commits_per_active_day": avg_per_active_day,
                "weekly_commit_counts": weekly_counts,
            },
        ))

    if avg_per_active_day > 15:
        findings.append(RawFinding(
            category="habits",
            severity="warning",
            slug="commit-batching",
            title=f"Averaging {avg_per_active_day} commits on active days — possible batching",
            description=(
                f"On days when commits happen, the average is {avg_per_active_day} commits. "
                f"High batch counts may indicate work is being saved up and pushed in bulk "
                f"rather than committed incrementally."
            ),
            recommendation=(
                "Commit early and often throughout the day. Frequent, small commits make code "
                "easier to review, bisect for bugs, and integrate with the team."
            ),
            metric_data={
                "avg_commits_per_active_day": avg_per_active_day,
                "active_days": active_days,
            },
        ))

    return findings


async def analyze_commit_message_habits(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Check the quality of this contributor's commit messages."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    total_q = select(func.count()).select_from(Commit).where(
        Commit.contributor_id == contributor_id,
        Commit.authored_at >= cutoff,
        Commit.is_merge.is_(False),
    )
    total = (await db.execute(total_q)).scalar() or 0
    if total < 10:
        return []

    msgs_q = select(Commit.message).where(
        Commit.contributor_id == contributor_id,
        Commit.authored_at >= cutoff,
        Commit.is_merge.is_(False),
        Commit.message.isnot(None),
    )
    messages = (await db.execute(msgs_q)).scalars().all()

    short_count = sum(1 for m in messages if m and len(m.strip()) < 10)
    no_ref_count = sum(1 for m in messages if m and not WI_REF_RE.search(m))
    generic_patterns = re.compile(r"^(fix|update|wip|test|changes?|stuff|misc|tmp)\s*$", re.IGNORECASE)
    generic_count = sum(1 for m in messages if m and generic_patterns.match(m.strip().split("\n")[0]))

    findings: list[RawFinding] = []

    bad_count = short_count + generic_count
    bad_pct = round((bad_count / total) * 100, 1) if total else 0

    if bad_pct > 20:
        severity = "warning" if bad_pct > 40 else "info"
        sample_bad = [m.strip()[:80] for m in messages if m and (len(m.strip()) < 10 or generic_patterns.match(m.strip().split("\n")[0]))][:5]
        findings.append(RawFinding(
            category="code_craft",
            severity=severity,
            slug="poor-commit-messages",
            title=f"{bad_pct}% of commits have vague or too-short messages",
            description=(
                f"Out of {total} commits, {bad_count} ({bad_pct}%) have messages under 10 characters "
                f"or use generic terms like 'fix', 'update', 'wip'. Good commit messages help teammates "
                f"and your future self understand why a change was made."
            ),
            recommendation=(
                "Write commit messages that explain the 'why', not just the 'what'. Use the format: "
                "'<type>: <short summary>' (e.g. 'fix: prevent null pointer in user lookup'). "
                "Aim for at least 20 characters in the subject line."
            ),
            metric_data={
                "total_commits": total,
                "poor_messages": bad_count,
                "poor_pct": bad_pct,
                "short_count": short_count,
                "generic_count": generic_count,
                "sample_poor_messages": sample_bad,
            },
        ))

    no_ref_pct = round((no_ref_count / total) * 100, 1) if total else 0
    if no_ref_pct > 70:
        findings.append(RawFinding(
            category="code_craft",
            severity="info",
            slug="no-work-item-references",
            title=f"{no_ref_pct}% of commits lack a work item reference",
            description=(
                f"{no_ref_count} of {total} commits don't link to a ticket or work item (e.g. #1234). "
                f"Traceability between code and requirements improves debugging and auditing."
            ),
            recommendation=(
                "Include a ticket reference in every commit message. Many teams use "
                "pre-commit hooks or IDE templates to make this automatic."
            ),
            metric_data={
                "total_commits": total,
                "no_reference": no_ref_count,
                "no_ref_pct": no_ref_pct,
            },
        ))

    return findings


async def analyze_pr_authoring(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Analyze how this contributor authors pull requests."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    prs_q = (
        select(
            PullRequest.id,
            PullRequest.title,
            PullRequest.lines_added,
            PullRequest.lines_deleted,
            PullRequest.state,
        )
        .where(
            PullRequest.author_id == contributor_id,
            PullRequest.created_at >= cutoff,
        )
    )
    prs = (await db.execute(prs_q)).all()
    if len(prs) < 3:
        return []

    findings: list[RawFinding] = []
    sizes = [(p.lines_added or 0) + (p.lines_deleted or 0) for p in prs]
    oversized = [s for s in sizes if s > 500]
    oversized_pct = round((len(oversized) / len(prs)) * 100, 1)

    if oversized_pct > 30:
        median_size = sorted(sizes)[len(sizes) // 2]
        max_size = max(sizes)
        findings.append(RawFinding(
            category="code_craft",
            severity="warning",
            slug="large-prs",
            title=f"{oversized_pct}% of PRs exceed 500 lines ({len(oversized)} of {len(prs)})",
            description=(
                f"Large PRs are harder to review thoroughly, leading to more bugs slipping through. "
                f"Median PR size: {median_size} lines, largest: {max_size} lines."
            ),
            recommendation=(
                "Break changes into smaller, focused PRs. A good target is under 400 lines. "
                "Use stacked PRs or feature flags to ship incremental progress."
            ),
            metric_data={
                "total_prs": len(prs),
                "oversized_count": len(oversized),
                "oversized_pct": oversized_pct,
                "median_size": median_size,
                "max_size": max_size,
            },
        ))

    merged_q = (
        select(PullRequest.id)
        .outerjoin(Review, Review.pull_request_id == PullRequest.id)
        .where(
            PullRequest.author_id == contributor_id,
            PullRequest.state == PRState.MERGED,
            PullRequest.merged_at >= cutoff,
        )
        .group_by(PullRequest.id)
        .having(func.count(Review.id) == 0)
    )
    no_review_sub = select(func.count()).select_from(merged_q.subquery())
    self_merged = (await db.execute(no_review_sub)).scalar() or 0

    total_merged = sum(1 for p in prs if p.state == PRState.MERGED)
    if self_merged > 0 and total_merged > 0:
        self_merge_pct = round((self_merged / total_merged) * 100, 1)
        if self_merge_pct > 25:
            findings.append(RawFinding(
                category="collaboration",
                severity="warning",
                slug="self-merging",
                title=f"{self_merged} of {total_merged} merged PRs had no reviews ({self_merge_pct}%)",
                description=(
                    f"Merging without peer review bypasses an important quality gate. "
                    f"Even for small changes, a second pair of eyes catches bugs and shares knowledge."
                ),
                recommendation=(
                    "Request a review on every PR before merging. If urgency requires a quick merge, "
                    "tag a reviewer for a post-merge review within 24 hours."
                ),
                metric_data={
                    "self_merged": self_merged,
                    "total_merged": total_merged,
                    "self_merge_pct": self_merge_pct,
                },
            ))

    return findings


async def analyze_review_engagement(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Analyze review give/receive ratio and responsiveness."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    reviews_given_q = select(func.count()).select_from(Review).where(
        Review.reviewer_id == contributor_id,
        Review.submitted_at >= cutoff,
    )
    reviews_given = (await db.execute(reviews_given_q)).scalar() or 0

    prs_authored_q = select(func.count()).select_from(PullRequest).where(
        PullRequest.author_id == contributor_id,
        PullRequest.created_at >= cutoff,
    )
    prs_authored = (await db.execute(prs_authored_q)).scalar() or 0

    findings: list[RawFinding] = []

    if prs_authored >= 5 and reviews_given == 0:
        findings.append(RawFinding(
            category="collaboration",
            severity="warning",
            slug="no-reviews-given",
            title=f"Authored {prs_authored} PRs but gave 0 code reviews in 90 days",
            description=(
                "Code review is a two-way street. Reviewing others' code helps you learn different "
                "approaches, catch patterns you might adopt, and builds shared understanding of the codebase."
            ),
            recommendation=(
                "Aim to review at least as many PRs as you author. Start by picking one PR "
                "per day from your team's queue. Focus on understanding the intent, not just the syntax."
            ),
            metric_data={
                "prs_authored": prs_authored,
                "reviews_given": reviews_given,
                "ratio": 0,
            },
        ))
    elif prs_authored >= 5 and reviews_given > 0:
        ratio = round(reviews_given / prs_authored, 2)
        if ratio < 0.3:
            findings.append(RawFinding(
                category="collaboration",
                severity="info",
                slug="low-review-ratio",
                title=f"Review ratio is {ratio}x ({reviews_given} reviews for {prs_authored} PRs authored)",
                description=(
                    f"A healthy review ratio is at least 1x — one review given per PR authored. "
                    f"At {ratio}x, more review participation would strengthen the team's code quality."
                ),
                recommendation=(
                    "Schedule 15-30 minutes daily for code reviews. Prioritize PRs that have been "
                    "waiting the longest. Even a quick 'looks good' with questions builds team trust."
                ),
                metric_data={
                    "prs_authored": prs_authored,
                    "reviews_given": reviews_given,
                    "ratio": ratio,
                },
            ))

    return findings


async def analyze_knowledge_breadth(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Check how broadly the contributor touches the codebase."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    repo_counts_q = (
        select(
            Repository.id,
            Repository.name,
            func.count(distinct(Commit.id)).label("commit_count"),
        )
        .join(Commit, Commit.repository_id == Repository.id)
        .where(
            Commit.contributor_id == contributor_id,
            Commit.authored_at >= cutoff,
            Commit.is_merge.is_(False),
        )
        .group_by(Repository.id, Repository.name)
    )
    repo_rows = (await db.execute(repo_counts_q)).all()

    if len(repo_rows) < 2:
        return []

    total_commits = sum(r.commit_count for r in repo_rows)
    sorted_repos = sorted(repo_rows, key=lambda r: r.commit_count, reverse=True)
    top_repo = sorted_repos[0]
    top_repo_pct = round((top_repo.commit_count / total_commits) * 100, 1) if total_commits else 0

    findings: list[RawFinding] = []

    if top_repo_pct > 85 and len(repo_rows) >= 3:
        findings.append(RawFinding(
            category="knowledge",
            severity="info",
            slug="single-repo-focus",
            title=f"{top_repo_pct}% of commits are in a single repository ({top_repo.name})",
            description=(
                f"While depth is valuable, {top_repo_pct}% concentration in one repository "
                f"({top_repo.commit_count} of {total_commits} commits) creates knowledge silos. "
                f"If this contributor is unavailable, others may struggle with that codebase."
            ),
            recommendation=(
                "Consider occasional contributions to other repos through bug fixes or reviews. "
                "Pair programming on unfamiliar codebases is an effective way to spread knowledge."
            ),
            metric_data={
                "repos_touched": len(repo_rows),
                "top_repo": top_repo.name,
                "top_repo_commits": top_repo.commit_count,
                "top_repo_pct": top_repo_pct,
                "total_commits": total_commits,
                "repo_breakdown": [
                    {"name": r.name, "commits": r.commit_count}
                    for r in sorted_repos[:5]
                ],
            },
        ))

    dir_q = (
        select(
            func.split_part(CommitFile.file_path, "/", 1).label("top_dir"),
            func.count(distinct(CommitFile.commit_id)).label("cnt"),
        )
        .join(Commit, CommitFile.commit_id == Commit.id)
        .where(
            Commit.contributor_id == contributor_id,
            Commit.authored_at >= cutoff,
            CommitFile.file_path.contains("/"),
        )
        .group_by(text("1"))
        .order_by(func.count(distinct(CommitFile.commit_id)).desc())
    )
    dir_rows = (await db.execute(dir_q)).all()

    if len(dir_rows) >= 3:
        total_dir_commits = sum(r.cnt for r in dir_rows)
        top_dir = dir_rows[0]
        top_dir_pct = round((top_dir.cnt / total_dir_commits) * 100, 1) if total_dir_commits else 0

        if top_dir_pct > 80 and len(dir_rows) > 5:
            findings.append(RawFinding(
                category="knowledge",
                severity="info",
                slug="narrow-directory-focus",
                title=f"{top_dir_pct}% of changes are under the '{top_dir.top_dir}/' directory",
                description=(
                    f"Strong focus on one area of the codebase. Expanding to adjacent areas "
                    f"builds a more holistic understanding and makes you a more versatile contributor."
                ),
                recommendation=(
                    "Pick a small task in an unfamiliar area of the codebase each sprint. "
                    "Review PRs outside your usual domain to build familiarity."
                ),
                metric_data={
                    "directories_touched": len(dir_rows),
                    "top_directory": top_dir.top_dir,
                    "top_dir_pct": top_dir_pct,
                    "dir_breakdown": [
                        {"dir": r.top_dir, "commits": r.cnt}
                        for r in dir_rows[:8]
                    ],
                },
            ))

    return findings


async def analyze_growth_trajectory(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Compare recent activity to prior period for growth signals."""
    now = datetime.now(timezone.utc)
    recent_start = now - timedelta(days=30)
    prior_start = now - timedelta(days=60)

    async def _period_stats(start: datetime, end: datetime) -> dict:
        q = select(
            func.count().label("commits"),
            func.coalesce(func.sum(Commit.lines_added), 0).label("added"),
            func.coalesce(func.sum(Commit.lines_deleted), 0).label("deleted"),
            func.count(distinct(Commit.repository_id)).label("repos"),
        ).where(
            Commit.contributor_id == contributor_id,
            Commit.authored_at >= start,
            Commit.authored_at < end,
            Commit.is_merge.is_(False),
        )
        row = (await db.execute(q)).one()
        return {
            "commits": row.commits or 0,
            "added": int(row.added or 0),
            "deleted": int(row.deleted or 0),
            "repos": row.repos or 0,
        }

    recent = await _period_stats(recent_start, now)
    prior = await _period_stats(prior_start, recent_start)

    if prior["commits"] < 5 or recent["commits"] < 5:
        return []

    findings: list[RawFinding] = []

    commit_delta = recent["commits"] - prior["commits"]
    commit_delta_pct = round((commit_delta / prior["commits"]) * 100, 1) if prior["commits"] else 0

    recent_reviews_q = select(func.count()).select_from(Review).where(
        Review.reviewer_id == contributor_id,
        Review.submitted_at >= recent_start,
    )
    recent_reviews = (await db.execute(recent_reviews_q)).scalar() or 0

    prior_reviews_q = select(func.count()).select_from(Review).where(
        Review.reviewer_id == contributor_id,
        Review.submitted_at >= prior_start,
        Review.submitted_at < recent_start,
    )
    prior_reviews = (await db.execute(prior_reviews_q)).scalar() or 0

    if commit_delta_pct < -50:
        findings.append(RawFinding(
            category="growth",
            severity="info",
            slug="declining-output",
            title=f"Commit volume down {abs(commit_delta_pct)}% compared to prior 30 days",
            description=(
                f"Recent period: {recent['commits']} commits. Prior period: {prior['commits']} commits. "
                f"A significant drop may indicate blockers, context-switching to non-code work, "
                f"or a focus shift that's worth discussing."
            ),
            recommendation=(
                "If the drop is due to blockers, escalate them. If it's a role shift (more reviews, "
                "planning, mentoring), make sure that's recognized and aligned with team goals."
            ),
            metric_data={
                "recent_commits": recent["commits"],
                "prior_commits": prior["commits"],
                "delta_pct": commit_delta_pct,
                "recent_reviews": recent_reviews,
                "prior_reviews": prior_reviews,
            },
        ))

    if commit_delta_pct > 80 and recent["commits"] > 20:
        findings.append(RawFinding(
            category="growth",
            severity="info",
            slug="output-surge",
            title=f"Commit volume up {commit_delta_pct}% ({recent['commits']} vs {prior['commits']})",
            description=(
                f"Great momentum! Output has increased significantly. Make sure this pace is sustainable "
                f"and code quality isn't being sacrificed for speed."
            ),
            recommendation=(
                "Keep it up, but watch for signs of burnout. Ensure PRs are still getting reviewed "
                "and commit quality remains high. Sustainable pace beats sprint-and-crash."
            ),
            metric_data={
                "recent_commits": recent["commits"],
                "prior_commits": prior["commits"],
                "delta_pct": commit_delta_pct,
            },
        ))

    if recent_reviews > prior_reviews * 2 and recent_reviews >= 5:
        findings.append(RawFinding(
            category="growth",
            severity="info",
            slug="review-engagement-growth",
            title=f"Code review participation doubled ({recent_reviews} vs {prior_reviews})",
            description=(
                f"Review engagement has grown significantly. This is a strong signal of technical "
                f"leadership and contributes to team code quality."
            ),
            recommendation=(
                "Excellent growth area. Consider mentoring others on effective review practices "
                "and sharing your review methodology with the team."
            ),
            metric_data={
                "recent_reviews": recent_reviews,
                "prior_reviews": prior_reviews,
            },
        ))

    return findings


async def analyze_commit_size_patterns(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Analyze average commit size and flag if too large."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    q = select(
        (Commit.lines_added + Commit.lines_deleted).label("size"),
    ).where(
        Commit.contributor_id == contributor_id,
        Commit.authored_at >= cutoff,
        Commit.is_merge.is_(False),
    )
    rows = (await db.execute(q)).all()
    if len(rows) < 10:
        return []

    sizes = [r.size for r in rows if r.size is not None]
    if not sizes:
        return []

    avg_size = round(sum(sizes) / len(sizes))
    sorted_sizes = sorted(sizes)
    median_size = sorted_sizes[len(sorted_sizes) // 2]
    p90_size = sorted_sizes[int(len(sorted_sizes) * 0.9)]
    large_count = sum(1 for s in sizes if s > 300)
    large_pct = round((large_count / len(sizes)) * 100, 1)

    findings: list[RawFinding] = []

    if median_size > 200:
        findings.append(RawFinding(
            category="code_craft",
            severity="info" if median_size < 400 else "warning",
            slug="large-commit-sizes",
            title=f"Median commit size is {median_size} lines (target: under 150)",
            description=(
                f"Average: {avg_size} lines, median: {median_size} lines, P90: {p90_size} lines. "
                f"{large_pct}% of commits exceed 300 lines. Smaller commits are easier to review, "
                f"revert if needed, and understand in git history."
            ),
            recommendation=(
                "Aim for atomic commits — each commit should represent one logical change. "
                "Use interactive staging (git add -p) to split large changes into focused commits."
            ),
            metric_data={
                "total_commits": len(sizes),
                "avg_size": avg_size,
                "median_size": median_size,
                "p90_size": p90_size,
                "large_commits": large_count,
                "large_pct": large_pct,
            },
        ))

    return findings


async def analyze_weekend_work(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Flag if contributor is working outside normal hours excessively."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    total_q = select(func.count()).select_from(Commit).where(
        Commit.contributor_id == contributor_id,
        Commit.authored_at >= cutoff,
    )
    total = (await db.execute(total_q)).scalar() or 0
    if total < 20:
        return []

    weekend_q = select(func.count()).select_from(Commit).where(
        Commit.contributor_id == contributor_id,
        Commit.authored_at >= cutoff,
        func.extract("isodow", Commit.authored_at).in_([6, 7]),
    )
    weekend_count = (await db.execute(weekend_q)).scalar() or 0
    weekend_pct = round((weekend_count / total) * 100, 1) if total else 0

    late_q = select(func.count()).select_from(Commit).where(
        Commit.contributor_id == contributor_id,
        Commit.authored_at >= cutoff,
        func.extract("hour", Commit.authored_at).between(22, 23) |
        func.extract("hour", Commit.authored_at).between(0, 5),
    )
    late_count = (await db.execute(late_q)).scalar() or 0
    late_pct = round((late_count / total) * 100, 1) if total else 0

    findings: list[RawFinding] = []

    if weekend_pct > 25:
        findings.append(RawFinding(
            category="habits",
            severity="warning",
            slug="frequent-weekend-work",
            title=f"{weekend_pct}% of commits are on weekends ({weekend_count} of {total})",
            description=(
                "Frequent weekend work can signal unsustainable workload, deadline pressure, "
                "or misaligned work estimates. Sustained weekend work leads to burnout."
            ),
            recommendation=(
                "If weekend work is needed, discuss workload with your manager. Consider if tasks "
                "can be better estimated or reprioritized. Protect time for recovery."
            ),
            metric_data={
                "weekend_commits": weekend_count,
                "total_commits": total,
                "weekend_pct": weekend_pct,
            },
        ))

    if late_pct > 20:
        findings.append(RawFinding(
            category="habits",
            severity="info",
            slug="late-night-commits",
            title=f"{late_pct}% of commits are between 10PM-6AM ({late_count} of {total})",
            description=(
                "Late-night coding may be a preference, but can also indicate workload issues. "
                "Code written during fatigue tends to have more defects."
            ),
            recommendation=(
                "If this is by choice, ensure you're getting enough rest. If driven by deadlines, "
                "it's worth flagging workload concerns with your team lead."
            ),
            metric_data={
                "late_commits": late_count,
                "total_commits": total,
                "late_pct": late_pct,
            },
        ))

    return findings
