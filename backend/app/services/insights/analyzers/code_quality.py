"""Code Quality analyzers: hotspot risk, churn patterns."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.commit import Commit
from app.db.models.commit_file import CommitFile
from app.db.models.repository import Repository
from app.services.insights.types import RawFinding

CATEGORY = "code_quality"


async def analyze_hotspot_risk(
    db: AsyncSession, project_id: uuid.UUID,
) -> list[RawFinding]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    repo_ids = select(Repository.id).where(Repository.project_id == project_id)

    file_stats_q = (
        select(
            CommitFile.file_path,
            func.count(func.distinct(CommitFile.commit_id)).label("commit_count"),
            func.count(func.distinct(Commit.contributor_id)).label("contributor_count"),
            func.sum(CommitFile.lines_added + CommitFile.lines_deleted).label("churn"),
        )
        .join(Commit, CommitFile.commit_id == Commit.id)
        .where(
            Commit.repository_id.in_(repo_ids),
            Commit.authored_at >= cutoff,
        )
        .group_by(CommitFile.file_path)
        .order_by(func.count(func.distinct(CommitFile.commit_id)).desc())
        .limit(200)
    )
    rows = (await db.execute(file_stats_q)).all()

    if len(rows) < 10:
        return []

    top_10_pct_idx = max(1, len(rows) // 10)
    hotspots = [
        r for r in rows[:top_10_pct_idx]
        if r.contributor_count >= 3
    ]

    if not hotspots:
        return []

    hotspot_data = [
        {
            "path": r.file_path,
            "commits": r.commit_count,
            "contributors": r.contributor_count,
            "churn": int(r.churn or 0),
        }
        for r in hotspots[:10]
    ]

    return [RawFinding(
        category=CATEGORY,
        severity="warning",
        slug="code-hotspots",
        title=f"{len(hotspots)} files are high-churn hotspots with many contributors",
        description=(
            f"These files are in the top 10% by commit frequency AND have 3+ contributors, "
            f"making them merge-conflict magnets and complexity risks. "
            f"Top hotspot: {hotspot_data[0]['path']} ({hotspot_data[0]['commits']} commits, "
            f"{hotspot_data[0]['contributors']} contributors)."
        ),
        recommendation=(
            "Consider refactoring large hotspot files to reduce coupling. "
            "Assign clear ownership and break them into smaller modules."
        ),
        metric_data={"hotspot_files": hotspot_data},
    )]


async def analyze_churn_patterns(
    db: AsyncSession, project_id: uuid.UUID,
) -> list[RawFinding]:
    now = datetime.now(timezone.utc)
    repo_ids = select(Repository.id).where(Repository.project_id == project_id)

    async def _churn_ratio(start: datetime, end: datetime) -> tuple[int, int]:
        q = select(
            func.coalesce(func.sum(Commit.lines_added), 0),
            func.coalesce(func.sum(Commit.lines_deleted), 0),
        ).where(
            Commit.repository_id.in_(repo_ids),
            Commit.authored_at >= start,
            Commit.authored_at < end,
            Commit.is_merge.is_(False),
        )
        r = (await db.execute(q)).one()
        return int(r[0]), int(r[1])

    added_cur, deleted_cur = await _churn_ratio(now - timedelta(days=30), now)
    added_prev, deleted_prev = await _churn_ratio(now - timedelta(days=60), now - timedelta(days=30))

    if added_cur == 0 or added_prev == 0:
        return []

    ratio_cur = round(deleted_cur / added_cur, 2)
    ratio_prev = round(deleted_prev / added_prev, 2)

    findings: list[RawFinding] = []

    if ratio_cur > 0.8 and ratio_cur > ratio_prev * 1.2:
        findings.append(RawFinding(
            category=CATEGORY,
            severity="warning",
            slug="high-churn-ratio",
            title=f"Code churn ratio is {ratio_cur} (delete/add), up from {ratio_prev}",
            description=(
                f"This month: {added_cur} lines added, {deleted_cur} deleted (ratio {ratio_cur}). "
                f"Last month: ratio was {ratio_prev}. A rising churn ratio may indicate rework or instability."
            ),
            recommendation="Investigate which files are being repeatedly modified. Consider if requirements are changing too often.",
            metric_data={
                "current_ratio": ratio_cur,
                "previous_ratio": ratio_prev,
                "current_added": added_cur,
                "current_deleted": deleted_cur,
                "previous_added": added_prev,
                "previous_deleted": deleted_prev,
            },
        ))

    return findings
