import logging

from github import Github, GithubException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Repository, PullRequest, Review, Contributor, PRComment
from app.db.models.pull_request import PRState
from app.db.models.review import ReviewState
from app.db.models.pr_comment import PRCommentType
from app.services.identity import resolve_contributor

if __import__("typing").TYPE_CHECKING:
    from app.services.sync_logger import SyncLogger

logger = logging.getLogger(__name__)

STATE_MAP = {"open": PRState.OPEN, "closed": PRState.CLOSED, "merged": PRState.MERGED}
REVIEW_STATE_MAP = {
    "APPROVED": ReviewState.APPROVED,
    "CHANGES_REQUESTED": ReviewState.CHANGES_REQUESTED,
    "COMMENTED": ReviewState.COMMENTED,
}


async def fetch_github_prs(
    db: AsyncSession, repo: Repository, token: str | None = None,
    sync_log: "SyncLogger | None" = None,
) -> int:
    """Fetch PRs and reviews from GitHub. Returns count of new PRs."""
    if not repo.platform_owner or not repo.platform_repo:
        return 0

    gh = Github(token) if token else Github()
    try:
        gh_repo = gh.get_repo(f"{repo.platform_owner}/{repo.platform_repo}")
        if sync_log:
            sync_log.info("prs", f"Connected to GitHub: {repo.platform_owner}/{repo.platform_repo}")
    except GithubException as e:
        logger.error("GitHub API error for %s/%s: %s", repo.platform_owner, repo.platform_repo, e)
        if sync_log:
            sync_log.error("prs", f"GitHub API error: {e}")
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

        try:
            for rc in pr.get_review_comments():
                c_user = rc.user
                c_email = (c_user.email if c_user else None) or f"{c_user.login}@github.com"
                c_name = c_user.login if c_user else "unknown"
                c_contributor = await resolve_contributor(db, c_name, c_email)
                db.add(PRComment(
                    pull_request_id=db_pr.id,
                    author_name=c_name,
                    author_id=c_contributor.id,
                    body=rc.body or "",
                    thread_id=str(rc.pull_request_review_id) if rc.pull_request_review_id else None,
                    file_path=rc.path,
                    line_number=rc.original_line or rc.line,
                    comment_type=PRCommentType.INLINE if rc.path else PRCommentType.GENERAL,
                    platform_comment_id=str(rc.id),
                    created_at=rc.created_at,
                    updated_at=rc.updated_at,
                ))
            for ic in pr.get_issue_comments():
                ic_user = ic.user
                ic_email = (ic_user.email if ic_user else None) or f"{ic_user.login}@github.com"
                ic_name = ic_user.login if ic_user else "unknown"
                ic_contributor = await resolve_contributor(db, ic_name, ic_email)
                db.add(PRComment(
                    pull_request_id=db_pr.id,
                    author_name=ic_name,
                    author_id=ic_contributor.id,
                    body=ic.body or "",
                    comment_type=PRCommentType.GENERAL,
                    platform_comment_id=f"issue_{ic.id}",
                    created_at=ic.created_at,
                    updated_at=ic.updated_at,
                ))
        except GithubException as e:
            logger.warning("Could not fetch comments for PR %d: %s", pr.number, e)

        new_count += 1

    await db.flush()
    gh.close()
    return new_count
