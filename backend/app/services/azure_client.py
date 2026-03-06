import logging
from datetime import datetime

from azure.devops.connection import Connection
from azure.devops.v7_1.git.models import GitPullRequestSearchCriteria
from msrest.authentication import BasicAuthentication
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Repository, PullRequest, Review
from app.db.models.pull_request import PRState
from app.db.models.review import ReviewState
from app.services.identity import resolve_contributor

if __import__("typing").TYPE_CHECKING:
    from app.services.sync_logger import SyncLogger

logger = logging.getLogger(__name__)

VOTE_MAP = {
    10: ReviewState.APPROVED,
    5: ReviewState.APPROVED,
    -5: ReviewState.CHANGES_REQUESTED,
    -10: ReviewState.CHANGES_REQUESTED,
}

_SYSTEM_THREAD_TYPES = frozenset({"System", "VoteUpdate", "StatusUpdate", "RefUpdate", "PolicyStatusUpdate"})


def _parse_project_and_repo(repo: Repository) -> tuple[str, str]:
    """Extract the Azure DevOps project name and repo name from platform fields.

    platform_owner is "org/project", platform_repo is the repo name.
    The API wants the project portion only.
    """
    owner = repo.platform_owner or ""
    parts = owner.split("/", 1)
    project = parts[1] if len(parts) > 1 else parts[0]
    return project, repo.platform_repo


async def fetch_azure_prs(
    db: AsyncSession,
    repo: Repository,
    org_url: str | None = None,
    token: str | None = None,
    sync_log: "SyncLogger | None" = None,
) -> int:
    """Fetch PRs, reviews, threads, and iterations from Azure DevOps."""
    if not org_url or not token or not repo.platform_owner or not repo.platform_repo:
        logger.info("Skipping Azure PR fetch – missing credentials or platform fields")
        if sync_log:
            sync_log.warning("prs", "Skipping Azure PR fetch — missing credentials or platform fields")
        return 0

    credentials = BasicAuthentication("", token)
    connection = Connection(base_url=org_url, creds=credentials)
    git_client = connection.clients.get_git_client()
    project, repo_name = _parse_project_and_repo(repo)
    if sync_log:
        sync_log.info("prs", f"Connected to Azure DevOps: {org_url} project={project} repo={repo_name}")

    existing = await db.execute(
        select(PullRequest.platform_pr_id).where(PullRequest.repository_id == repo.id)
    )
    existing_ids = set(existing.scalars().all())
    new_count = 0

    try:
        criteria = GitPullRequestSearchCriteria(status="all")
        prs = git_client.get_pull_requests(
            repo_name,
            project=project,
            search_criteria=criteria,
        )
        if sync_log:
            sync_log.info("prs", f"Found {len(prs) if prs else 0} total PRs, checking for new ones...")
    except Exception as e:
        logger.error("Azure DevOps PR list error for %s/%s: %s", project, repo_name, e)
        if sync_log:
            sync_log.error("prs", f"Azure DevOps API error: {e}")
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

        comment_count, first_review_at = _fetch_threads(
            git_client, project, repo_name, pr.pull_request_id
        )

        iteration_count = _fetch_iteration_count(
            git_client, project, repo_name, pr.pull_request_id
        )

        db_pr = PullRequest(
            repository_id=repo.id,
            contributor_id=contributor.id,
            platform_pr_id=pr.pull_request_id,
            title=(pr.title or "")[:1024],
            state=state,
            lines_added=0,
            lines_deleted=0,
            comment_count=comment_count,
            iteration_count=iteration_count,
            created_at=pr.creation_date,
            merged_at=pr.closed_date if state == PRState.MERGED else None,
            closed_at=pr.closed_date,
            first_review_at=first_review_at,
        )
        db.add(db_pr)
        await db.flush()

        reviewer_comments = _extract_reviewer_comments(
            git_client, project, repo_name, pr.pull_request_id
        )

        for reviewer_info in pr.reviewers or []:
            vote = reviewer_info.vote or 0
            if vote == 0:
                continue
            review_state = VOTE_MAP.get(vote, ReviewState.COMMENTED)
            rev_email = reviewer_info.unique_name or f"{reviewer_info.display_name}@azure.com"
            rev_contributor = await resolve_contributor(
                db, reviewer_info.display_name or "unknown", rev_email
            )
            rev_comment_count = reviewer_comments.get(rev_email.lower(), 0)
            db.add(Review(
                pull_request_id=db_pr.id,
                reviewer_id=rev_contributor.id,
                state=review_state,
                comment_count=rev_comment_count,
                submitted_at=first_review_at or pr.creation_date,
            ))

        new_count += 1

    await db.flush()
    logger.info("Azure DevOps: fetched %d new PRs for %s/%s", new_count, project, repo_name)
    return new_count


def _fetch_threads(
    git_client, project: str, repo_name: str, pr_id: int
) -> tuple[int, datetime | None]:
    """Fetch PR threads. Returns (comment_count, first_review_at)."""
    try:
        threads = git_client.get_threads(repo_name, pr_id, project=project)
    except Exception as e:
        logger.warning("Could not fetch threads for PR %d: %s", pr_id, e)
        return 0, None

    comment_count = 0
    first_review_at: datetime | None = None

    for thread in threads or []:
        props = thread.properties or {}
        thread_type = None
        if hasattr(props, "get"):
            thread_type = props.get("CodeReviewThreadType", {}).get("$value")
        elif isinstance(props, dict):
            thread_type = props.get("CodeReviewThreadType", {}).get("$value")

        if thread_type in _SYSTEM_THREAD_TYPES:
            continue

        comments = thread.comments or []
        if not comments:
            continue

        comment_count += len(comments)

        published = getattr(thread, "published_date", None)
        if published and (first_review_at is None or published < first_review_at):
            first_review_at = published

    return comment_count, first_review_at


def _fetch_iteration_count(
    git_client, project: str, repo_name: str, pr_id: int
) -> int:
    """Return number of push iterations for a PR."""
    try:
        iterations = git_client.get_pull_request_iterations(repo_name, pr_id, project=project)
        return len(iterations) if iterations else 0
    except Exception as e:
        logger.warning("Could not fetch iterations for PR %d: %s", pr_id, e)
        return 0


def _extract_reviewer_comments(
    git_client, project: str, repo_name: str, pr_id: int
) -> dict[str, int]:
    """Count non-system comments per reviewer email (lowercased)."""
    try:
        threads = git_client.get_threads(repo_name, pr_id, project=project)
    except Exception:
        return {}

    counts: dict[str, int] = {}
    for thread in threads or []:
        for comment in thread.comments or []:
            if getattr(comment, "comment_type", None) == "system":
                continue
            author = getattr(comment, "author", None)
            if author:
                email = (getattr(author, "unique_name", None) or "").lower()
                if email:
                    counts[email] = counts.get(email, 0) + 1
    return counts
