"""Contributor insight orchestrator — runs all contributor analyzers and deduplicates findings."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.contributor_insight import ContributorInsightRun, ContributorInsightFinding
from app.services.insights.types import RawFinding

from app.services.insights.analyzers.contributor_growth import (
    analyze_commit_consistency,
    analyze_commit_message_habits,
    analyze_pr_authoring,
    analyze_review_engagement,
    analyze_knowledge_breadth,
    analyze_growth_trajectory,
    analyze_commit_size_patterns,
    analyze_weekend_work,
)
from app.services.insights.analyzers.contributor_delivery import (
    analyze_throughput_trends,
    analyze_cycle_time,
    analyze_estimation_accuracy,
    analyze_wip_overload,
    analyze_sprint_commitment,
    analyze_bug_ratio,
)
from app.services.insights.analyzers.contributor_pr_quality import (
    analyze_review_turnaround,
    analyze_pr_iteration_count,
    analyze_pr_abandonment,
    analyze_review_depth,
    analyze_review_network_diversity,
    analyze_time_to_first_review,
)
from app.services.insights.analyzers.contributor_code_quality import (
    analyze_hotspot_ownership,
    analyze_code_churn_on_own_work,
    analyze_test_coverage_habits,
)

logger = logging.getLogger(__name__)

ALL_CONTRIBUTOR_ANALYZERS = [
    # habits / growth / knowledge (original)
    analyze_commit_consistency,
    analyze_commit_message_habits,
    analyze_pr_authoring,
    analyze_review_engagement,
    analyze_knowledge_breadth,
    analyze_growth_trajectory,
    analyze_commit_size_patterns,
    analyze_weekend_work,
    # delivery
    analyze_throughput_trends,
    analyze_cycle_time,
    analyze_estimation_accuracy,
    analyze_wip_overload,
    analyze_sprint_commitment,
    analyze_bug_ratio,
    # PR quality
    analyze_review_turnaround,
    analyze_pr_iteration_count,
    analyze_pr_abandonment,
    analyze_review_depth,
    analyze_review_network_diversity,
    analyze_time_to_first_review,
    # code quality
    analyze_hotspot_ownership,
    analyze_code_churn_on_own_work,
    analyze_test_coverage_habits,
]


async def run_contributor_analysis(
    db: AsyncSession, run: ContributorInsightRun, slog=None,
) -> list[RawFinding]:
    """Execute all contributor analyzers and return raw findings."""
    contributor_id = run.contributor_id
    all_findings: list[RawFinding] = []

    total = len(ALL_CONTRIBUTOR_ANALYZERS)
    for i, analyzer in enumerate(ALL_CONTRIBUTOR_ANALYZERS, 1):
        name = analyzer.__name__
        short_name = name.replace("analyze_", "")
        if slog:
            slog.info("analyzer", f"[{i}/{total}] Running {short_name}...")
        try:
            findings = await analyzer(db, contributor_id)
            all_findings.extend(findings)
            if findings:
                logger.info("Analyzer %s produced %d findings", name, len(findings))
                if slog:
                    slog.info("analyzer", f"[{i}/{total}] {short_name}: {len(findings)} findings")
            else:
                if slog:
                    slog.info("analyzer", f"[{i}/{total}] {short_name}: clean")
        except Exception:
            logger.exception("Analyzer %s failed for contributor %s", name, contributor_id)
            if slog:
                slog.warning("analyzer", f"[{i}/{total}] {short_name}: FAILED (skipped)")

    if slog:
        slog.info("summary", f"Analysis complete: {len(all_findings)} raw findings from {total} analyzers")
    return all_findings


async def persist_contributor_findings(
    db: AsyncSession,
    run: ContributorInsightRun,
    raw_findings: list[RawFinding],
) -> int:
    """Deduplicate and persist contributor findings. Returns count."""
    contributor_id = run.contributor_id
    now = datetime.now(timezone.utc)

    seen_slugs: set[str] = set()

    for rf in raw_findings:
        seen_slugs.add(rf.slug)

        existing_q = select(ContributorInsightFinding).where(
            ContributorInsightFinding.contributor_id == contributor_id,
            ContributorInsightFinding.slug == rf.slug,
            ContributorInsightFinding.status == "active",
        )
        existing = (await db.execute(existing_q)).scalar_one_or_none()

        if existing:
            existing.run_id = run.id
            existing.last_detected_at = now
            existing.severity = rf.severity
            existing.title = rf.title
            existing.description = rf.description
            existing.recommendation = rf.recommendation
            existing.metric_data = rf.metric_data
            existing.affected_entities = rf.affected_entities
        else:
            finding = ContributorInsightFinding(
                run_id=run.id,
                contributor_id=contributor_id,
                category=rf.category,
                severity=rf.severity,
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

    stale_q = select(ContributorInsightFinding).where(
        ContributorInsightFinding.contributor_id == contributor_id,
        ContributorInsightFinding.status == "active",
        ContributorInsightFinding.slug.notin_(seen_slugs) if seen_slugs else True,
    )
    stale = (await db.execute(stale_q)).scalars().all()
    for f in stale:
        f.status = "resolved"
        f.resolved_at = now

    run.findings_count = len(raw_findings)
    run.status = "completed"
    run.finished_at = now

    await db.commit()
    return len(raw_findings)
