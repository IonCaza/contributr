"""Team insight orchestrator — runs all team analyzers and deduplicates findings."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.team_insight import TeamInsightRun, TeamInsightFinding
from app.services.insights.types import RawFinding

from app.services.insights.analyzers.team_health import (
    analyze_velocity_consistency,
    analyze_work_distribution,
    analyze_review_reciprocity,
    analyze_sprint_completion,
    analyze_wip_balance,
    analyze_knowledge_silos,
    analyze_team_cycle_time,
    analyze_collaboration_density,
)

logger = logging.getLogger(__name__)

ALL_TEAM_ANALYZERS = [
    analyze_velocity_consistency,
    analyze_work_distribution,
    analyze_review_reciprocity,
    analyze_sprint_completion,
    analyze_wip_balance,
    analyze_knowledge_silos,
    analyze_team_cycle_time,
    analyze_collaboration_density,
]


async def run_team_analysis(
    db: AsyncSession, run: TeamInsightRun, slog=None,
) -> list[RawFinding]:
    """Execute all team analyzers and return raw findings."""
    team_id = run.team_id
    project_id = run.project_id
    all_findings: list[RawFinding] = []

    total = len(ALL_TEAM_ANALYZERS)
    for i, analyzer in enumerate(ALL_TEAM_ANALYZERS, 1):
        name = analyzer.__name__
        short_name = name.replace("analyze_", "")
        if slog:
            slog.info("analyzer", f"[{i}/{total}] Running {short_name}...")
        try:
            findings = await analyzer(db, team_id, project_id)
            all_findings.extend(findings)
            if findings:
                logger.info("Analyzer %s produced %d findings", name, len(findings))
                if slog:
                    slog.info("analyzer", f"[{i}/{total}] {short_name}: {len(findings)} findings")
            else:
                if slog:
                    slog.info("analyzer", f"[{i}/{total}] {short_name}: clean")
        except Exception:
            logger.exception("Analyzer %s failed for team %s", name, team_id)
            if slog:
                slog.warning("analyzer", f"[{i}/{total}] {short_name}: FAILED (skipped)")

    if slog:
        slog.info("summary", f"Analysis complete: {len(all_findings)} raw findings from {total} analyzers")
    return all_findings


async def persist_team_findings(
    db: AsyncSession,
    run: TeamInsightRun,
    raw_findings: list[RawFinding],
) -> int:
    """Deduplicate and persist team findings. Returns count."""
    team_id = run.team_id
    project_id = run.project_id
    now = datetime.now(timezone.utc)

    seen_slugs: set[str] = set()

    for rf in raw_findings:
        seen_slugs.add(rf.slug)

        existing_q = select(TeamInsightFinding).where(
            TeamInsightFinding.team_id == team_id,
            TeamInsightFinding.slug == rf.slug,
            TeamInsightFinding.status == "active",
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
            finding = TeamInsightFinding(
                run_id=run.id,
                team_id=team_id,
                project_id=project_id,
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

    stale_q = select(TeamInsightFinding).where(
        TeamInsightFinding.team_id == team_id,
        TeamInsightFinding.status == "active",
        TeamInsightFinding.slug.notin_(seen_slugs) if seen_slugs else True,
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
