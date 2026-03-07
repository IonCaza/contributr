"""Insight analysis orchestrator — runs all analyzers and deduplicates findings."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.insight import (
    InsightRun, InsightFinding, InsightRunStatus,
    InsightCategory, InsightSeverity, InsightStatus,
)
from app.services.insights.types import RawFinding

from app.services.insights.analyzers.process_health import (
    analyze_commit_message_quality,
    analyze_pr_process_compliance,
    analyze_pr_size_distribution,
    analyze_branch_hygiene,
)
from app.services.insights.analyzers.delivery_efficiency import (
    analyze_cycle_time_trends,
    analyze_sprint_predictability,
    analyze_sprint_scope_creep,
    analyze_wip_limits,
)
from app.services.insights.analyzers.team_balance import (
    analyze_work_distribution,
    analyze_review_culture,
    analyze_team_balance,
)
from app.services.insights.analyzers.code_quality import (
    analyze_hotspot_risk,
    analyze_churn_patterns,
)
from app.services.insights.analyzers.intersection import (
    analyze_commit_work_item_linkage,
    analyze_estimation_accuracy,
)

logger = logging.getLogger(__name__)

ALL_ANALYZERS = [
    analyze_commit_message_quality,
    analyze_pr_process_compliance,
    analyze_pr_size_distribution,
    analyze_branch_hygiene,
    analyze_cycle_time_trends,
    analyze_sprint_predictability,
    analyze_sprint_scope_creep,
    analyze_wip_limits,
    analyze_work_distribution,
    analyze_review_culture,
    analyze_team_balance,
    analyze_hotspot_risk,
    analyze_churn_patterns,
    analyze_commit_work_item_linkage,
    analyze_estimation_accuracy,
]


async def run_analysis(db: AsyncSession, run: InsightRun, slog=None) -> list[RawFinding]:
    """Execute all analyzers and return raw findings."""
    project_id = run.project_id
    all_findings: list[RawFinding] = []

    total = len(ALL_ANALYZERS)
    for i, analyzer in enumerate(ALL_ANALYZERS, 1):
        name = analyzer.__name__
        short_name = name.replace("analyze_", "")
        if slog:
            slog.info("analyzer", f"[{i}/{total}] Running {short_name}...")
        try:
            findings = await analyzer(db, project_id)
            all_findings.extend(findings)
            if findings:
                logger.info("Analyzer %s produced %d findings", name, len(findings))
                if slog:
                    slog.info("analyzer", f"[{i}/{total}] {short_name}: {len(findings)} findings")
            else:
                if slog:
                    slog.info("analyzer", f"[{i}/{total}] {short_name}: clean")
        except Exception:
            logger.exception("Analyzer %s failed for project %s", name, project_id)
            if slog:
                slog.warning("analyzer", f"[{i}/{total}] {short_name}: FAILED (skipped)")

    if slog:
        slog.info("summary", f"Analysis complete: {len(all_findings)} raw findings from {total} analyzers")
    return all_findings


async def persist_findings(
    db: AsyncSession,
    run: InsightRun,
    raw_findings: list[RawFinding],
) -> int:
    """Deduplicate and persist findings. Returns count of findings stored."""
    project_id = run.project_id
    now = datetime.now(timezone.utc)

    seen_slugs: set[str] = set()

    for rf in raw_findings:
        seen_slugs.add(rf.slug)

        existing_q = select(InsightFinding).where(
            InsightFinding.project_id == project_id,
            InsightFinding.slug == rf.slug,
            InsightFinding.status == InsightStatus.ACTIVE,
        )
        existing = (await db.execute(existing_q)).scalar_one_or_none()

        if existing:
            existing.run_id = run.id
            existing.last_detected_at = now
            existing.severity = InsightSeverity(rf.severity)
            existing.title = rf.title
            existing.description = rf.description
            existing.recommendation = rf.recommendation
            existing.metric_data = rf.metric_data
            existing.affected_entities = rf.affected_entities
        else:
            finding = InsightFinding(
                run_id=run.id,
                project_id=project_id,
                category=InsightCategory(rf.category),
                severity=InsightSeverity(rf.severity),
                slug=rf.slug,
                title=rf.title,
                description=rf.description,
                recommendation=rf.recommendation,
                metric_data=rf.metric_data,
                affected_entities=rf.affected_entities,
                first_detected_at=now,
                last_detected_at=now,
            )
            db.add(finding)

    # Mark previously-active findings not seen in this run as resolved
    stale_q = select(InsightFinding).where(
        InsightFinding.project_id == project_id,
        InsightFinding.status == InsightStatus.ACTIVE,
        InsightFinding.slug.notin_(seen_slugs) if seen_slugs else True,
    )
    stale = (await db.execute(stale_q)).scalars().all()
    for f in stale:
        f.status = InsightStatus.RESOLVED
        f.resolved_at = now

    run.findings_count = len(raw_findings)
    run.status = InsightRunStatus.COMPLETED
    run.finished_at = now

    await db.commit()
    return len(raw_findings)
