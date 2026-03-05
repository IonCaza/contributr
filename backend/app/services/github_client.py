import logging

from github import Github, GithubException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Repository, PullRequest, Review, Contributor
from app.db.models.pull_request import PRState
from app.db.models.review import ReviewState
from app.services.identity import resolve_contributor

logger = logging.getLogger(__name__)

STATE_MAP = {"open": PRState.OPEN, "closed": PRState.CLOSED, "merged": PRState.MERGED}
REVIEW_STATE_MAP = {
    "APPROVED": ReviewState.APPROVED,
    "CHANGES_REQUESTED": ReviewState.CHANGES_REQUESTED,
    "COMMENTED": ReviewState.COMMENTED,
}


async def fetch_github_prs(db: AsyncSession, repo: Repository, token: str | None = None) -> int:
    """Fetch PRs and reviews from GitHub. Returns count of new PRs."""
    if not repo.platform_owner or not repo.platform_repo:
        return 0

    gh = Github(token) if token else Github()
    try:
        gh_repo = gh.get_repo(f"{repo.platform_owner}/{repo.platform_repo}")
    except GithubException as e:
        logger.error("GitHub API error for %s/%s: %s", repo.platform_owner, repo.platform_repo, e)
        return 0

    existing = await db.execute(
        select(PullRequest.platform_pr_id).where(PullRequest.repository_id == repo.id)
    )
    existing_ids = set(existing.scalars().all())
    new_count = 0

    for pr in gh_repo.get_pulls(state="all", sort="updated", direction="desc"):
        if pr.number in existing_ids:
            continue

        author_email = pr.user.email or f"{pr.user.login}@github.com"
        contributor = await resolve_contributor(db, pr.user.login, author_email)

        state = PRState.MERGED if pr.merged else STATE_MAP.get(pr.state, PRState.OPEN)
        db_pr = PullRequest(
            repository_id=repo.id,
            contributor_id=contributor.id,
            platform_pr_id=pr.number,
            title=(pr.title or "")[:1024],
            state=state,
            lines_added=pr.additions or 0,
            lines_deleted=pr.deletions or 0,
            created_at=pr.created_at,
            merged_at=pr.merged_at,
            closed_at=pr.closed_at,
        )
        db.add(db_pr)
        await db.flush()

        for review in pr.get_reviews():
            review_state = REVIEW_STATE_MAP.get(review.state)
            if not review_state:
                continue
            reviewer_email = (review.user.email if review.user else None) or f"{review.user.login}@github.com"
            reviewer = await resolve_contributor(db, review.user.login, reviewer_email)
            db.add(Review(
                pull_request_id=db_pr.id,
                reviewer_id=reviewer.id,
                state=review_state,
                submitted_at=review.submitted_at,
            ))

        new_count += 1

    await db.flush()
    gh.close()
    return new_count
