"""Contributor Code Quality analyzers: sole-owner hotspots, self-churn, test coverage habits."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, distinct, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.commit import Commit
from app.db.models.commit_file import CommitFile
from app.services.insights.types import RawFinding

CATEGORY = "code_quality"


async def analyze_hotspot_ownership(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Files this person is the sole contributor to (bus factor = 1)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=180)

    files_by_contributor_q = (
        select(CommitFile.file_path)
        .join(Commit, CommitFile.commit_id == Commit.id)
        .where(
            Commit.contributor_id == contributor_id,
            Commit.authored_at >= cutoff,
        )
        .group_by(CommitFile.file_path)
        .having(func.count(distinct(Commit.id)) >= 3)
    )
    my_files = (await db.execute(files_by_contributor_q)).scalars().all()

    if not my_files:
        return []

    sole_owner_files: list[str] = []
    for fp in my_files:
        other_q = select(func.count(distinct(Commit.contributor_id))).select_from(
            CommitFile.__table__.join(Commit.__table__, CommitFile.commit_id == Commit.id)
        ).where(
            CommitFile.file_path == fp,
            Commit.authored_at >= cutoff,
            Commit.contributor_id != contributor_id,
            Commit.contributor_id.isnot(None),
        )
        other_count = (await db.execute(other_q)).scalar() or 0
        if other_count == 0:
            sole_owner_files.append(fp)

    if len(sole_owner_files) < 3:
        return []

    findings: list[RawFinding] = []
    findings.append(RawFinding(
        category=CATEGORY,
        severity="warning" if len(sole_owner_files) > 10 else "info",
        slug="sole-owner-hotspots",
        title=f"Sole owner of {len(sole_owner_files)} files (bus factor = 1)",
        description=(
            f"This contributor is the only person who has touched {len(sole_owner_files)} files "
            f"in the last 6 months. If they're unavailable, no one else has recent context on "
            f"these files. This is a knowledge concentration risk."
        ),
        recommendation=(
            "Schedule pair programming or code walkthroughs on critical sole-owner files. "
            "Write documentation for complex logic. Assign cross-training reviews to spread knowledge."
        ),
        metric_data={
            "sole_owner_count": len(sole_owner_files),
            "example_files": sole_owner_files[:20],
        },
    ))

    return findings


async def analyze_code_churn_on_own_work(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """How often lines this person added get deleted within 30 days (by anyone)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    my_commits_q = (
        select(Commit.id, CommitFile.file_path, CommitFile.lines_added)
        .join(CommitFile, CommitFile.commit_id == Commit.id)
        .where(
            Commit.contributor_id == contributor_id,
            Commit.authored_at >= cutoff,
            CommitFile.lines_added > 0,
        )
    )
    my_adds = (await db.execute(my_commits_q)).all()

    if len(my_adds) < 10:
        return []

    total_added = sum(r.lines_added for r in my_adds)
    if total_added < 100:
        return []

    my_files = {r.file_path for r in my_adds}

    churn_q = (
        select(func.sum(CommitFile.lines_deleted))
        .join(Commit, CommitFile.commit_id == Commit.id)
        .where(
            CommitFile.file_path.in_(my_files),
            Commit.authored_at >= cutoff,
        )
    )
    total_deleted_in_my_files = (await db.execute(churn_q)).scalar() or 0

    churn_ratio = round(total_deleted_in_my_files / total_added, 2) if total_added else 0

    findings: list[RawFinding] = []

    if churn_ratio > 0.5:
        findings.append(RawFinding(
            category=CATEGORY,
            severity="warning" if churn_ratio > 0.8 else "info",
            slug="high-self-churn",
            title=f"Code churn ratio of {churn_ratio} on files touched ({total_deleted_in_my_files} lines deleted vs {total_added} added)",
            description=(
                f"Files this contributor has added code to see a significant amount of deletions "
                f"({total_deleted_in_my_files} lines removed vs {total_added} lines added, ratio {churn_ratio}). "
                f"High churn may indicate exploratory coding, frequent rework, or instability in "
                f"the areas they work on."
            ),
            recommendation=(
                "Investigate whether churn is from refactoring (healthy) or rework (costly). "
                "Design before coding for complex features. Seek early feedback via draft PRs "
                "to avoid large-scale rewrites."
            ),
            metric_data={
                "lines_added": total_added,
                "lines_deleted_in_same_files": total_deleted_in_my_files,
                "churn_ratio": churn_ratio,
                "file_count": len(my_files),
            },
        ))

    return findings


async def analyze_test_coverage_habits(
    db: AsyncSession, contributor_id: uuid.UUID,
) -> list[RawFinding]:
    """Ratio of commits that touch test files vs only source files."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    total_commits_q = select(func.count()).select_from(Commit).where(
        Commit.contributor_id == contributor_id,
        Commit.authored_at >= cutoff,
        Commit.is_merge.is_(False),
    )
    total_commits = (await db.execute(total_commits_q)).scalar() or 0

    if total_commits < 10:
        return []

    test_pattern_q = (
        select(func.count(distinct(CommitFile.commit_id)))
        .join(Commit, CommitFile.commit_id == Commit.id)
        .where(
            Commit.contributor_id == contributor_id,
            Commit.authored_at >= cutoff,
            Commit.is_merge.is_(False),
            (
                CommitFile.file_path.ilike("%test%")
                | CommitFile.file_path.ilike("%spec%")
                | CommitFile.file_path.ilike("%.test.%")
                | CommitFile.file_path.ilike("%.spec.%")
                | CommitFile.file_path.ilike("%__tests__%")
            ),
        )
    )
    commits_with_tests = (await db.execute(test_pattern_q)).scalar() or 0

    test_pct = round((commits_with_tests / total_commits) * 100, 1) if total_commits else 0

    findings: list[RawFinding] = []

    if test_pct < 15 and total_commits >= 10:
        findings.append(RawFinding(
            category=CATEGORY,
            severity="warning" if test_pct < 5 else "info",
            slug="low-test-file-ratio",
            title=f"Only {test_pct}% of commits touch test files ({commits_with_tests}/{total_commits})",
            description=(
                f"Out of {total_commits} non-merge commits in the last 90 days, only "
                f"{commits_with_tests} ({test_pct}%) include changes to test files. "
                f"This could indicate that new code is being shipped without corresponding tests, "
                f"increasing regression risk."
            ),
            recommendation=(
                "Adopt a practice of including tests in the same commit or PR as the feature code. "
                "Use TDD for complex logic. Set a team goal for test-inclusive commit percentage."
            ),
            metric_data={
                "total_commits": total_commits,
                "commits_with_tests": commits_with_tests,
                "test_pct": test_pct,
            },
        ))

    return findings
