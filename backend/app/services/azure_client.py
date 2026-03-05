import logging

from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Repository, PullRequest, Review
from app.db.models.pull_request import PRState
from app.db.models.review import ReviewState
from app.services.identity import resolve_contributor

logger = logging.getLogger(__name__)

VOTE_MAP = {10: ReviewState.APPROVED, 5: ReviewState.APPROVED, -5: ReviewState.CHANGES_REQUESTED, -10: ReviewState.CHANGES_REQUESTED}


async def fetch_azure_prs(
    db: AsyncSession,
    repo: Repository,
    org_url: str | None = None,
    token: str | None = None,
) -> int:
    """Fetch PRs and reviews from Azure DevOps. Returns count of new PRs."""
    if not org_url or not token or not repo.platform_owner or not repo.platform_repo:
        return 0

    credentials = BasicAuthentication("", token)
    connection = Connection(base_url=org_url, creds=credentials)
    git_client = connection.clients.get_git_client()

    existing = await db.execute(
        select(PullRequest.platform_pr_id).where(PullRequest.repository_id == repo.id)
    )
    existing_ids = set(existing.scalars().all())
    new_count = 0

    try:
        prs = git_client.get_pull_requests(
            repo.platform_repo,
            project=repo.platform_owner,
            search_criteria={"status": "all"},
        )
    except Exception as e:
        logger.error("Azure DevOps API error: %s", e)
        return 0

    for pr in prs:
        if pr.pull_request_id in existing_ids:
            continue

        author_name = pr.created_by.display_name or "unknown"
        author_email = pr.created_by.unique_name or f"{author_name}@azure.com"
        contributor = await resolve_contributor(db, author_name, author_email)

        if pr.status == "completed":
            state = PRState.MERGED
        elif pr.status == "abandoned":
            state = PRState.CLOSED
        else:
            state = PRState.OPEN

        db_pr = PullRequest(
            repository_id=repo.id,
            contributor_id=contributor.id,
            platform_pr_id=pr.pull_request_id,
            title=(pr.title or "")[:1024],
            state=state,
            lines_added=0,
            lines_deleted=0,
            created_at=pr.creation_date,
            merged_at=pr.closed_date if state == PRState.MERGED else None,
            closed_at=pr.closed_date,
        )
        db.add(db_pr)
        await db.flush()

        for reviewer in pr.reviewers or []:
            vote = reviewer.vote or 0
            review_state = VOTE_MAP.get(vote, ReviewState.COMMENTED)
            rev_email = reviewer.unique_name or f"{reviewer.display_name}@azure.com"
            rev_contributor = await resolve_contributor(db, reviewer.display_name or "unknown", rev_email)
            db.add(Review(
                pull_request_id=db_pr.id,
                reviewer_id=rev_contributor.id,
                state=review_state,
                submitted_at=pr.creation_date,
            ))

        new_count += 1

    await db.flush()
    return new_count
