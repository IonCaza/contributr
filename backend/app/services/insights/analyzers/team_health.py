"""Team-focused analyzers: velocity, collaboration, workload, process, knowledge."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from sqlalchemy import select, func, distinct, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.commit import Commit
from app.db.models.commit_file import CommitFile
from app.db.models.repository import Repository
from app.db.models.pull_request import PullRequest, PRState
from app.db.models.review import Review
from app.db.models.work_item import WorkItem
from app.db.models.iteration import Iteration
from app.db.models.team import TeamMember
from app.db.models.contributor import Contributor
from app.services.insights.types import RawFinding


async def _get_member_ids(db: AsyncSession, team_id: uuid.UUID) -> list[uuid.UUID]:
    rows = (await db.execute(
        select(TeamMember.contributor_id).where(TeamMember.team_id == team_id)
    )).scalars().all()
    return list(rows)


async def _get_member_names(db: AsyncSession, member_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not member_ids:
        return {}
    rows = (await db.execute(
        select(Contributor.id, Contributor.canonical_name).where(Contributor.id.in_(member_ids))
    )).all()
    return {r.id: r.canonical_name for r in rows}


async def analyze_velocity_consistency(
    db: AsyncSession, team_id: uuid.UUID, project_id: uuid.UUID,
) -> list[RawFinding]:
    """Flag erratic sprint velocity (high variance or declining trend)."""
    member_ids = await _get_member_ids(db, team_id)
    if not member_ids:
        return []

    iters_q = (
        select(Iteration)
        .where(
            Iteration.project_id == project_id,
            Iteration.end_date.isnot(None),
            Iteration.end_date <= datetime.now(timezone.utc).date(),
        )
        .order_by(Iteration.end_date.desc())
        .limit(6)
    )
    iterations = (await db.execute(iters_q)).scalars().all()
    if len(iterations) < 3:
        return []

    velocities: list[dict] = []
    for it in reversed(iterations):
        q = select(func.coalesce(func.sum(WorkItem.story_points), 0)).where(
            WorkItem.project_id == project_id,
            WorkItem.iteration_id == it.id,
            WorkItem.assigned_to_id.in_(member_ids),
            WorkItem.resolved_at.isnot(None),
        )
        completed_sp = float((await db.execute(q)).scalar() or 0)
        velocities.append({"name": it.name, "velocity": completed_sp})

    vals = [v["velocity"] for v in velocities]
    avg_vel = sum(vals) / len(vals) if vals else 0
    if avg_vel == 0:
        return []

    variance = sum((v - avg_vel) ** 2 for v in vals) / len(vals)
    cv = (variance ** 0.5) / avg_vel if avg_vel else 0

    findings: list[RawFinding] = []

    if cv > 0.5:
        severity = "warning" if cv > 0.7 else "info"
        findings.append(RawFinding(
            category="velocity",
            severity=severity,
            slug="team-velocity-erratic",
            title=f"Sprint velocity varies widely (CV={round(cv, 2)})",
            description=(
                f"Over the last {len(velocities)} sprints, completed story points ranged from "
                f"{min(vals):.0f} to {max(vals):.0f} (avg {avg_vel:.1f}). A coefficient of variation "
                f"above 0.5 makes forecasting unreliable."
            ),
            recommendation=(
                "Review sprint planning accuracy. Ensure stories are right-sized and the team "
                "isn't taking on work they can't commit to. Stable velocity enables better delivery "
                "predictability for stakeholders."
            ),
            metric_data={
                "sprints": velocities,
                "avg_velocity": round(avg_vel, 1),
                "cv": round(cv, 2),
                "min": round(min(vals), 1),
                "max": round(max(vals), 1),
            },
        ))

    recent_half = vals[len(vals) // 2:]
    older_half = vals[: len(vals) // 2]
    if older_half and recent_half:
        recent_avg = sum(recent_half) / len(recent_half)
        older_avg = sum(older_half) / len(older_half)
        if older_avg > 0 and recent_avg < older_avg * 0.7:
            drop_pct = round((1 - recent_avg / older_avg) * 100, 1)
            findings.append(RawFinding(
                category="velocity",
                severity="warning",
                slug="team-velocity-declining",
                title=f"Team velocity declining by {drop_pct}%",
                description=(
                    f"Recent sprints average {recent_avg:.1f} SP vs {older_avg:.1f} SP earlier. "
                    f"Declining velocity may signal blockers, scope creep, or team capacity issues."
                ),
                recommendation=(
                    "Investigate root causes: are there more interruptions, knowledge gaps from "
                    "attrition, or increasing tech debt? A focused retrospective on velocity trends "
                    "can uncover actionable improvements."
                ),
                metric_data={
                    "recent_avg": round(recent_avg, 1),
                    "older_avg": round(older_avg, 1),
                    "decline_pct": drop_pct,
                },
            ))

    return findings


async def analyze_work_distribution(
    db: AsyncSession, team_id: uuid.UUID, project_id: uuid.UUID,
) -> list[RawFinding]:
    """Check if work is concentrated on a few members (Gini coefficient)."""
    member_ids = await _get_member_ids(db, team_id)
    if len(member_ids) < 2:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    q = (
        select(Commit.contributor_id, func.count().label("cnt"))
        .join(Repository, Repository.id == Commit.repository_id)
        .where(
            Repository.project_id == project_id,
            Commit.contributor_id.in_(member_ids),
            Commit.authored_at >= cutoff,
            Commit.is_merge.is_(False),
        )
        .group_by(Commit.contributor_id)
    )
    rows = (await db.execute(q)).all()
    if not rows:
        return []

    names = await _get_member_names(db, member_ids)
    counts = sorted([r.cnt for r in rows])
    n = len(counts)
    total = sum(counts)
    if total == 0 or n < 2:
        return []

    numerator = sum((2 * (i + 1) - n - 1) * c for i, c in enumerate(counts))
    gini = numerator / (n * total)

    findings: list[RawFinding] = []
    if gini > 0.5:
        severity = "warning" if gini > 0.65 else "info"
        top = max(rows, key=lambda r: r.cnt)
        top_name = names.get(top.contributor_id, "Unknown")
        top_pct = round((top.cnt / total) * 100, 1)
        findings.append(RawFinding(
            category="workload",
            severity=severity,
            slug="team-work-concentration",
            title=f"Work is concentrated (Gini={round(gini, 2)}): {top_name} has {top_pct}% of commits",
            description=(
                f"In the last 30 days, commit distribution across the team is uneven "
                f"(Gini={round(gini, 2)}). The top contributor accounts for {top_pct}% of "
                f"all commits. Imbalanced workload leads to burnout and knowledge silos."
            ),
            recommendation=(
                "Redistribute tasks more evenly. Pair lower-output members with the lead "
                "contributor for knowledge transfer. Review sprint planning to balance assignments."
            ),
            metric_data={
                "gini": round(gini, 2),
                "total_commits": total,
                "member_count": len(member_ids),
                "active_members": n,
                "top_contributor": top_name,
                "top_pct": top_pct,
            },
            affected_entities={
                "contributors": [
                    {"id": str(r.contributor_id), "name": names.get(r.contributor_id, ""), "commits": r.cnt}
                    for r in sorted(rows, key=lambda r: r.cnt, reverse=True)
                ],
            },
        ))

    return findings


async def analyze_review_reciprocity(
    db: AsyncSession, team_id: uuid.UUID, project_id: uuid.UUID,
) -> list[RawFinding]:
    """Check if team members review each other's PRs (intra-team review rate)."""
    member_ids = await _get_member_ids(db, team_id)
    if len(member_ids) < 2:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    team_prs_q = (
        select(PullRequest.id)
        .join(Repository, Repository.id == PullRequest.repository_id)
        .where(
            Repository.project_id == project_id,
            PullRequest.contributor_id.in_(member_ids),
            PullRequest.created_at >= cutoff,
        )
    )
    pr_ids = (await db.execute(team_prs_q)).scalars().all()
    if not pr_ids:
        return []

    total_reviews_q = select(func.count()).select_from(Review).where(
        Review.pull_request_id.in_(pr_ids),
        Review.submitted_at >= cutoff,
    )
    total_reviews = (await db.execute(total_reviews_q)).scalar() or 0

    intra_reviews_q = select(func.count()).select_from(Review).where(
        Review.pull_request_id.in_(pr_ids),
        Review.reviewer_id.in_(member_ids),
        Review.submitted_at >= cutoff,
    )
    intra_reviews = (await db.execute(intra_reviews_q)).scalar() or 0

    if total_reviews < 3:
        return []

    intra_pct = round((intra_reviews / total_reviews) * 100, 1) if total_reviews else 0

    findings: list[RawFinding] = []
    if intra_pct < 40:
        severity = "warning" if intra_pct < 20 else "info"
        findings.append(RawFinding(
            category="collaboration",
            severity=severity,
            slug="team-low-intra-review",
            title=f"Only {intra_pct}% of reviews on team PRs come from teammates",
            description=(
                f"Out of {total_reviews} reviews on team PRs, only {intra_reviews} came from "
                f"within the team. Low intra-team review rates reduce shared code understanding "
                f"and increase knowledge silos."
            ),
            recommendation=(
                "Encourage team members to prioritize reviewing each other's PRs. "
                "Set a team norm that at least one review per PR comes from a teammate. "
                "This builds shared ownership and catches domain-specific issues early."
            ),
            metric_data={
                "total_reviews": total_reviews,
                "intra_team_reviews": intra_reviews,
                "intra_pct": intra_pct,
                "team_prs": len(pr_ids),
            },
        ))

    return findings


async def analyze_sprint_completion(
    db: AsyncSession, team_id: uuid.UUID, project_id: uuid.UUID,
) -> list[RawFinding]:
    """Analyze team sprint completion rate over recent iterations."""
    member_ids = await _get_member_ids(db, team_id)
    if not member_ids:
        return []

    iters_q = (
        select(Iteration)
        .where(
            Iteration.project_id == project_id,
            Iteration.end_date.isnot(None),
            Iteration.end_date <= datetime.now(timezone.utc).date(),
        )
        .order_by(Iteration.end_date.desc())
        .limit(5)
    )
    iterations = (await db.execute(iters_q)).scalars().all()
    if len(iterations) < 2:
        return []

    sprint_data: list[dict] = []
    for it in reversed(iterations):
        planned_q = select(func.coalesce(func.sum(WorkItem.story_points), 0)).where(
            WorkItem.project_id == project_id,
            WorkItem.iteration_id == it.id,
            WorkItem.assigned_to_id.in_(member_ids),
        )
        planned = float((await db.execute(planned_q)).scalar() or 0)

        completed_q = select(func.coalesce(func.sum(WorkItem.story_points), 0)).where(
            WorkItem.project_id == project_id,
            WorkItem.iteration_id == it.id,
            WorkItem.assigned_to_id.in_(member_ids),
            WorkItem.resolved_at.isnot(None),
        )
        completed = float((await db.execute(completed_q)).scalar() or 0)

        rate = round((completed / planned) * 100, 1) if planned > 0 else 100.0
        sprint_data.append({"name": it.name, "planned": planned, "completed": completed, "rate": rate})

    rates = [s["rate"] for s in sprint_data if s["planned"] > 0]
    if not rates:
        return []

    avg_rate = sum(rates) / len(rates)
    findings: list[RawFinding] = []

    if avg_rate < 70:
        severity = "critical" if avg_rate < 50 else "warning"
        findings.append(RawFinding(
            category="velocity",
            severity=severity,
            slug="team-low-sprint-completion",
            title=f"Average sprint completion is {avg_rate:.0f}%",
            description=(
                f"Across the last {len(rates)} sprints, the team completes an average of "
                f"{avg_rate:.0f}% of planned story points. Consistently low completion erodes "
                f"stakeholder trust and indicates over-commitment or external disruptions."
            ),
            recommendation=(
                "Right-size sprint commitments based on historical velocity. Leave a buffer "
                "for unplanned work. Focus sprint planning on achievable goals and discuss "
                "carry-over patterns in retrospectives."
            ),
            metric_data={
                "avg_completion_rate": round(avg_rate, 1),
                "sprints": sprint_data,
            },
        ))

    return findings


async def analyze_wip_balance(
    db: AsyncSession, team_id: uuid.UUID, project_id: uuid.UUID,
) -> list[RawFinding]:
    """Check WIP balance across team members — flag overloaded individuals."""
    member_ids = await _get_member_ids(db, team_id)
    if not member_ids:
        return []

    active_states = ("Active", "In Progress", "Committed", "active", "in progress", "committed")

    q = (
        select(WorkItem.assigned_to_id, func.count().label("wip"))
        .where(
            WorkItem.project_id == project_id,
            WorkItem.assigned_to_id.in_(member_ids),
            WorkItem.state.in_(active_states),
        )
        .group_by(WorkItem.assigned_to_id)
    )
    rows = (await db.execute(q)).all()
    if not rows:
        return []

    names = await _get_member_names(db, member_ids)
    wip_counts = {r.assigned_to_id: r.wip for r in rows}
    max_wip = max(wip_counts.values())
    min_wip = min(wip_counts.values()) if wip_counts else 0

    findings: list[RawFinding] = []

    overloaded = [(mid, cnt) for mid, cnt in wip_counts.items() if cnt > 5]
    if overloaded:
        severity = "critical" if any(cnt > 10 for _, cnt in overloaded) else "warning"
        overloaded_names = [
            f"{names.get(mid, 'Unknown')} ({cnt})" for mid, cnt in overloaded
        ]
        findings.append(RawFinding(
            category="workload",
            severity=severity,
            slug="team-wip-overloaded",
            title=f"{len(overloaded)} member(s) exceed WIP limit of 5",
            description=(
                f"Overloaded: {', '.join(overloaded_names)}. "
                f"High WIP increases context-switching, reduces focus, and slows throughput."
            ),
            recommendation=(
                "Enforce WIP limits at the team level. Help overloaded members complete or "
                "hand off items before taking new ones. Discuss blockers in daily standups."
            ),
            metric_data={
                "overloaded_members": len(overloaded),
                "max_wip": max_wip,
            },
            affected_entities={
                "contributors": [
                    {"id": str(mid), "name": names.get(mid, ""), "wip": cnt}
                    for mid, cnt in overloaded
                ],
            },
        ))

    if len(wip_counts) >= 2 and max_wip > 0 and min_wip > 0 and max_wip / min_wip > 3:
        imbalance = round(max_wip / min_wip, 1)
        findings.append(RawFinding(
            category="workload",
            severity="info",
            slug="team-wip-imbalanced",
            title=f"WIP imbalance: highest has {max_wip} items, lowest has {min_wip} ({imbalance}x)",
            description=(
                f"Work-in-progress is unevenly distributed. A {imbalance}x spread suggests "
                f"some members are blocked or idle while others are overwhelmed."
            ),
            recommendation=(
                "Redistribute active work items. Use daily standups to identify members "
                "who can pick up tasks and those who need help finishing current work."
            ),
            metric_data={
                "max_wip": max_wip,
                "min_wip": min_wip,
                "imbalance_ratio": imbalance,
            },
        ))

    return findings


async def analyze_knowledge_silos(
    db: AsyncSession, team_id: uuid.UUID, project_id: uuid.UUID,
) -> list[RawFinding]:
    """Find repos where only one team member has contributed (bus factor = 1)."""
    member_ids = await _get_member_ids(db, team_id)
    if len(member_ids) < 2:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    q = (
        select(
            Repository.id,
            Repository.name,
            func.count(distinct(Commit.contributor_id)).label("contributors"),
            func.count(distinct(Commit.id)).label("commits"),
        )
        .join(Commit, Commit.repository_id == Repository.id)
        .where(
            Repository.project_id == project_id,
            Commit.contributor_id.in_(member_ids),
            Commit.authored_at >= cutoff,
            Commit.is_merge.is_(False),
        )
        .group_by(Repository.id, Repository.name)
        .having(func.count(distinct(Commit.id)) >= 5)
    )
    rows = (await db.execute(q)).all()

    solo_repos = [r for r in rows if r.contributors == 1]
    if not solo_repos:
        return []

    findings: list[RawFinding] = []
    severity = "warning" if len(solo_repos) >= 3 else "info"
    repo_names = [r.name for r in solo_repos[:10]]

    findings.append(RawFinding(
        category="knowledge",
        severity=severity,
        slug="team-knowledge-silos",
        title=f"{len(solo_repos)} repo(s) have only a single team contributor",
        description=(
            f"Repositories with a bus factor of 1 within the team: {', '.join(repo_names)}. "
            f"If the sole contributor is unavailable, no one on the team can maintain these repos."
        ),
        recommendation=(
            "Schedule pairing sessions or assign secondary reviewers from the team for these repos. "
            "Even occasional contributions build familiarity and reduce risk."
        ),
        metric_data={
            "solo_repo_count": len(solo_repos),
            "repos_analyzed": len(rows),
        },
        affected_entities={
            "repos": [{"name": r.name, "commits": r.commits} for r in solo_repos[:10]],
        },
    ))

    return findings


async def analyze_team_cycle_time(
    db: AsyncSession, team_id: uuid.UUID, project_id: uuid.UUID,
) -> list[RawFinding]:
    """Compare team median cycle time to the project average."""
    member_ids = await _get_member_ids(db, team_id)
    if not member_ids:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    def _cycle_time_query(contributor_filter=None):
        q = select(
            func.extract("epoch", WorkItem.resolved_at - WorkItem.activated_at).label("ct_seconds"),
        ).where(
            WorkItem.project_id == project_id,
            WorkItem.resolved_at.isnot(None),
            WorkItem.activated_at.isnot(None),
            WorkItem.resolved_at >= cutoff,
        )
        if contributor_filter is not None:
            q = q.where(WorkItem.assigned_to_id.in_(contributor_filter))
        return q

    team_rows = (await db.execute(_cycle_time_query(member_ids))).all()
    project_rows = (await db.execute(_cycle_time_query())).all()

    if len(team_rows) < 5 or len(project_rows) < 5:
        return []

    team_cts = sorted([r.ct_seconds / 86400 for r in team_rows if r.ct_seconds and r.ct_seconds > 0])
    proj_cts = sorted([r.ct_seconds / 86400 for r in project_rows if r.ct_seconds and r.ct_seconds > 0])

    if not team_cts or not proj_cts:
        return []

    team_median = team_cts[len(team_cts) // 2]
    proj_median = proj_cts[len(proj_cts) // 2]

    if proj_median == 0:
        return []

    ratio = team_median / proj_median

    findings: list[RawFinding] = []
    if ratio > 1.5:
        severity = "warning" if ratio > 2.0 else "info"
        findings.append(RawFinding(
            category="velocity",
            severity=severity,
            slug="team-cycle-time-high",
            title=f"Team cycle time is {ratio:.1f}x the project average ({team_median:.1f}d vs {proj_median:.1f}d)",
            description=(
                f"Team median cycle time is {team_median:.1f} days compared to the project "
                f"median of {proj_median:.1f} days. Longer cycle times reduce delivery throughput "
                f"and delay feedback loops."
            ),
            recommendation=(
                "Analyze which stages of the workflow take longest. Common bottlenecks: "
                "waiting for review, unclear requirements, or insufficient testing infrastructure. "
                "Consider breaking work into smaller increments."
            ),
            metric_data={
                "team_median_days": round(team_median, 1),
                "project_median_days": round(proj_median, 1),
                "ratio": round(ratio, 1),
                "team_items": len(team_cts),
                "project_items": len(proj_cts),
            },
        ))

    return findings


async def analyze_collaboration_density(
    db: AsyncSession, team_id: uuid.UUID, project_id: uuid.UUID,
) -> list[RawFinding]:
    """Measure how much team members interact through reviews and co-contributions."""
    member_ids = await _get_member_ids(db, team_id)
    if len(member_ids) < 2:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    team_prs_q = (
        select(PullRequest.id, PullRequest.contributor_id)
        .join(Repository, Repository.id == PullRequest.repository_id)
        .where(
            Repository.project_id == project_id,
            PullRequest.contributor_id.in_(member_ids),
            PullRequest.created_at >= cutoff,
        )
    )
    team_prs = (await db.execute(team_prs_q)).all()
    if len(team_prs) < 3:
        return []

    pr_ids = [p.id for p in team_prs]

    cross_review_q = select(func.count(distinct(Review.id))).where(
        Review.pull_request_id.in_(pr_ids),
        Review.reviewer_id.in_(member_ids),
        Review.submitted_at >= cutoff,
    )
    cross_reviews = (await db.execute(cross_review_q)).scalar() or 0

    reviewers_q = select(func.count(distinct(Review.reviewer_id))).where(
        Review.pull_request_id.in_(pr_ids),
        Review.reviewer_id.in_(member_ids),
        Review.submitted_at >= cutoff,
    )
    active_reviewers = (await db.execute(reviewers_q)).scalar() or 0

    authors_q = select(func.count(distinct(PullRequest.contributor_id))).where(
        PullRequest.id.in_(pr_ids),
    )
    active_authors = (await db.execute(authors_q)).scalar() or 0

    reviews_per_pr = round(cross_reviews / len(pr_ids), 2) if pr_ids else 0
    participation_pct = round(
        ((active_reviewers + active_authors) / len(member_ids)) * 100, 1
    ) if member_ids else 0

    findings: list[RawFinding] = []

    if reviews_per_pr < 0.5 and len(pr_ids) >= 5:
        findings.append(RawFinding(
            category="collaboration",
            severity="warning" if reviews_per_pr < 0.2 else "info",
            slug="team-low-collaboration",
            title=f"Low team collaboration: {reviews_per_pr} intra-team reviews per PR",
            description=(
                f"Team members authored {len(pr_ids)} PRs but only gave {cross_reviews} "
                f"reviews to each other ({reviews_per_pr} per PR). Strong teams aim for at "
                f"least 1 intra-team review per PR to build shared understanding."
            ),
            recommendation=(
                "Establish a team agreement that every PR gets at least one review from a teammate. "
                "Rotate review assignments to spread knowledge evenly. Consider pair programming "
                "for complex changes."
            ),
            metric_data={
                "team_prs": len(pr_ids),
                "intra_reviews": cross_reviews,
                "reviews_per_pr": reviews_per_pr,
                "active_reviewers": active_reviewers,
                "active_authors": active_authors,
                "participation_pct": participation_pct,
            },
        ))

    if participation_pct < 60 and len(member_ids) >= 3:
        findings.append(RawFinding(
            category="collaboration",
            severity="info",
            slug="team-low-participation",
            title=f"Only {participation_pct}% of team members are active in code activities",
            description=(
                f"Out of {len(member_ids)} team members, only {active_authors} authored PRs "
                f"and {active_reviewers} reviewed code in the last 30 days. Low participation "
                f"may indicate capacity issues, role mismatches, or disengagement."
            ),
            recommendation=(
                "Check in with less active members to understand blockers. Ensure everyone "
                "has clear assignments. Consider if team composition matches the work required."
            ),
            metric_data={
                "total_members": len(member_ids),
                "active_authors": active_authors,
                "active_reviewers": active_reviewers,
                "participation_pct": participation_pct,
            },
        ))

    return findings
