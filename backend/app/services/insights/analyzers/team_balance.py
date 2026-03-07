"""Team Balance analyzers: work distribution, review culture, team velocity balance."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.commit import Commit
from app.db.models.repository import Repository
from app.db.models.pull_request import PullRequest, PRState
from app.db.models.review import Review
from app.db.models.contributor import Contributor
from app.db.models.team import Team, TeamMember
from app.db.models.work_item import WorkItem
from app.services.insights.types import RawFinding

CATEGORY = "team_balance"


def _gini(values: list[int]) -> float:
    if not values or sum(values) == 0:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    cumulative = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(sorted_vals))
    return round(cumulative / (n * sum(sorted_vals)), 2)


async def analyze_work_distribution(
    db: AsyncSession, project_id: uuid.UUID,
) -> list[RawFinding]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    repo_ids = select(Repository.id).where(Repository.project_id == project_id)

    contrib_q = (
        select(Commit.contributor_id, func.count().label("cnt"))
        .where(
            Commit.repository_id.in_(repo_ids),
            Commit.authored_at >= cutoff,
            Commit.contributor_id.isnot(None),
        )
        .group_by(Commit.contributor_id)
    )
    rows = (await db.execute(contrib_q)).all()

    if len(rows) < 3:
        return []

    counts = [r.cnt for r in rows]
    gini = _gini(counts)

    findings: list[RawFinding] = []

    if gini > 0.6:
        severity = "critical" if gini > 0.8 else "warning"

        name_q = select(Contributor.id, Contributor.canonical_name).where(
            Contributor.id.in_([r.contributor_id for r in rows])
        )
        name_map = {r[0]: r[1] for r in (await db.execute(name_q)).all()}

        sorted_rows = sorted(rows, key=lambda r: r.cnt, reverse=True)
        top = [
            {"name": name_map.get(r.contributor_id, "?"), "commits": r.cnt}
            for r in sorted_rows[:5]
        ]

        findings.append(RawFinding(
            category=CATEGORY,
            severity=severity,
            slug="work-concentration",
            title=f"Work is concentrated among a few contributors (Gini={gini})",
            description=(
                f"The Gini coefficient of commit distribution is {gini} (0=even, 1=all from one person). "
                f"Top contributor: {top[0]['name']} with {top[0]['commits']} commits."
            ),
            recommendation="Spread code ownership through pair programming, rotation, and knowledge sharing sessions.",
            metric_data={
                "gini": gini,
                "contributor_count": len(rows),
                "top_contributors": top,
            },
        ))

    # Bus factor: repos where only 1 contributor committed in 30d
    bus_q = (
        select(
            Repository.id,
            Repository.name,
            func.count(func.distinct(Commit.contributor_id)).label("contributors"),
        )
        .join(Commit, Commit.repository_id == Repository.id)
        .where(
            Repository.project_id == project_id,
            Commit.authored_at >= cutoff,
            Commit.contributor_id.isnot(None),
        )
        .group_by(Repository.id)
        .having(func.count(func.distinct(Commit.contributor_id)) == 1)
    )
    bus_rows = (await db.execute(bus_q)).all()

    if bus_rows:
        repo_names = [r.name for r in bus_rows]
        findings.append(RawFinding(
            category=CATEGORY,
            severity="critical" if len(bus_rows) > 2 else "warning",
            slug="bus-factor-one",
            title=f"{len(bus_rows)} repositories have a bus factor of 1",
            description=(
                f"These repos had commits from only one contributor in the last 30 days: "
                f"{', '.join(repo_names[:5])}{'...' if len(repo_names) > 5 else ''}. "
                f"If that person is unavailable, no one can maintain the code."
            ),
            recommendation="Cross-train team members on critical repositories. Require code reviews from different people.",
            metric_data={"repos": repo_names},
            affected_entities={"repos": [str(r.id) for r in bus_rows]},
        ))

    return findings


async def analyze_review_culture(
    db: AsyncSession, project_id: uuid.UUID,
) -> list[RawFinding]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    repo_ids = select(Repository.id).where(Repository.project_id == project_id)

    review_counts_q = (
        select(Review.reviewer_id, func.count().label("cnt"))
        .join(PullRequest, Review.pull_request_id == PullRequest.id)
        .where(
            PullRequest.repository_id.in_(repo_ids),
            Review.submitted_at >= cutoff,
            Review.reviewer_id.isnot(None),
        )
        .group_by(Review.reviewer_id)
    )
    review_rows = (await db.execute(review_counts_q)).all()
    total_reviews = sum(r.cnt for r in review_rows)

    findings: list[RawFinding] = []

    if total_reviews > 0 and review_rows:
        top_reviewer = max(review_rows, key=lambda r: r.cnt)
        top_pct = round((top_reviewer.cnt / total_reviews) * 100, 1)

        if top_pct > 50:
            name_q = select(Contributor.canonical_name).where(
                Contributor.id == top_reviewer.reviewer_id
            )
            name = (await db.execute(name_q)).scalar() or "Unknown"
            findings.append(RawFinding(
                category=CATEGORY,
                severity="warning",
                slug="review-concentration",
                title=f"One reviewer handles {top_pct}% of all code reviews",
                description=(
                    f"{name} performed {top_reviewer.cnt} of {total_reviews} reviews in the last 30 days. "
                    f"This creates a bottleneck and single point of failure for the review process."
                ),
                recommendation="Distribute review responsibilities more evenly. Consider round-robin review assignment.",
                metric_data={
                    "top_reviewer": name,
                    "top_count": top_reviewer.cnt,
                    "total_reviews": total_reviews,
                    "top_pct": top_pct,
                },
                affected_entities={"contributors": [str(top_reviewer.reviewer_id)]},
            ))

    # Self-merges: PRs where author merged and has no reviews from others
    self_merge_q = (
        select(func.count())
        .select_from(PullRequest)
        .outerjoin(Review, Review.pull_request_id == PullRequest.id)
        .where(
            PullRequest.repository_id.in_(repo_ids),
            PullRequest.state == PRState.MERGED,
            PullRequest.merged_at >= cutoff,
        )
        .group_by(PullRequest.id)
        .having(func.count(Review.id) == 0)
    )
    self_merge_sub = select(func.count()).select_from(self_merge_q.subquery())
    self_merge_count = (await db.execute(self_merge_sub)).scalar() or 0

    if self_merge_count > 3:
        findings.append(RawFinding(
            category=CATEGORY,
            severity="warning",
            slug="self-merges",
            title=f"{self_merge_count} PRs self-merged without peer review",
            description=(
                f"{self_merge_count} PRs were merged by their author without any peer review in the last 30 days."
            ),
            recommendation="Require at least one peer review before merging. Even small changes benefit from a second pair of eyes.",
            metric_data={"self_merge_count": self_merge_count},
        ))

    return findings


async def analyze_team_balance(
    db: AsyncSession, project_id: uuid.UUID,
) -> list[RawFinding]:
    teams_q = (
        select(Team)
        .where(Team.project_id == project_id)
    )
    teams = (await db.execute(teams_q)).scalars().all()

    if len(teams) < 2:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    team_velocities: list[dict] = []

    for team in teams:
        member_ids_q = select(TeamMember.contributor_id).where(TeamMember.team_id == team.id)
        member_ids = (await db.execute(member_ids_q)).scalars().all()
        if not member_ids:
            continue

        member_count = len(member_ids)

        points_q = select(func.coalesce(func.sum(WorkItem.story_points), 0.0)).where(
            WorkItem.project_id == project_id,
            WorkItem.assigned_to_id.in_(member_ids),
            WorkItem.resolved_at.isnot(None),
            WorkItem.resolved_at >= cutoff,
        )
        total_points = float((await db.execute(points_q)).scalar() or 0)
        velocity_per_member = round(total_points / member_count, 1) if member_count else 0

        team_velocities.append({
            "team": team.name,
            "members": member_count,
            "points": total_points,
            "velocity_per_member": velocity_per_member,
        })

    if len(team_velocities) < 2:
        return []

    velocities = [t["velocity_per_member"] for t in team_velocities if t["velocity_per_member"] > 0]
    if not velocities:
        return []

    mean_vel = sum(velocities) / len(velocities)
    if mean_vel == 0:
        return []

    outliers = [
        t for t in team_velocities
        if t["velocity_per_member"] > 0 and (
            t["velocity_per_member"] > mean_vel * 2 or t["velocity_per_member"] < mean_vel / 2
        )
    ]

    if not outliers:
        return []

    return [RawFinding(
        category=CATEGORY,
        severity="warning",
        slug="team-velocity-imbalance",
        title=f"{len(outliers)} teams have velocity deviating >2x from the mean",
        description=(
            f"Mean normalized velocity is {round(mean_vel, 1)} points/member/month. "
            "Outlier teams: {}.".format(
                ", ".join("{} ({} pts/member)".format(o["team"], o["velocity_per_member"]) for o in outliers)
            )
        ),
        recommendation="Investigate if workload allocation, team composition, or estimation practices differ between teams.",
        metric_data={
            "teams": team_velocities,
            "mean_velocity_per_member": round(mean_vel, 1),
            "outlier_teams": [o["team"] for o in outliers],
        },
    )]
