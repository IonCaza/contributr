import logging

import gitlab
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Repository, PullRequest, Review
from app.db.models.pull_request import PRState
from app.db.models.review import ReviewState
from app.services.identity import resolve_contributor

if __import__("typing").TYPE_CHECKING:
    from app.services.sync_logger import SyncLogger

logger = logging.getLogger(__name__)

STATE_MAP = {"opened": PRState.OPEN, "closed": PRState.CLOSED, "merged": PRState.MERGED}


async def fetch_gitlab_mrs(
    db: AsyncSession, repo: Repository, token: str | None = None,
    url: str = "https://gitlab.com", sync_log: "SyncLogger | None" = None,
) -> int:
    """Fetch merge requests and approvals from GitLab. Returns count of new MRs."""
    if not repo.platform_owner or not repo.platform_repo:
        return 0

    gl = gitlab.Gitlab(url, private_token=token)
    project_path = f"{repo.platform_owner}/{repo.platform_repo}"

    try:
        gl_project = gl.projects.get(project_path)
        if sync_log:
            sync_log.info("prs", f"Connected to GitLab: {project_path}")
    except gitlab.exceptions.GitlabGetError as e:
        logger.error("GitLab API error for %s: %s", project_path, e)
        if sync_log:
            sync_log.error("prs", f"GitLab API error: {e}")
        return 0

    existing = await db.execute(
        select(PullRequest.platform_pr_id).where(PullRequest.repository_id == repo.id)
    )
    existing_ids = set(existing.scalars().all())
    new_count = 0

    for mr in gl_project.mergerequests.list(state="all", order_by="updated_at", sort="desc", iterator=True):
        if mr.iid in existing_ids:
            continue

        author = mr.author or {}
        author_email = author.get("email") or f"{author.get('username', 'unknown')}@gitlab.com"
        author_name = author.get("name") or author.get("username", "unknown")
        contributor = await resolve_contributor(db, author_name, author_email)

        state = STATE_MAP.get(mr.state, PRState.OPEN)
        db_pr = PullRequest(
            repository_id=repo.id,
            contributor_id=contributor.id,
            platform_pr_id=mr.iid,
            title=(mr.title or "")[:1024],
            state=state,
            lines_added=getattr(mr, "changes_count", 0) or 0,
            lines_deleted=0,
            created_at=mr.created_at,
            merged_at=getattr(mr, "merged_at", None),
            closed_at=getattr(mr, "closed_at", None),
        )
        db.add(db_pr)
        await db.flush()

        try:
            mr_detail = gl_project.mergerequests.get(mr.iid)
            for approver in getattr(mr_detail, "approved_by", []) or []:
                user = approver.get("user", {})
                rev_email = user.get("email") or f"{user.get('username', 'unknown')}@gitlab.com"
                reviewer = await resolve_contributor(db, user.get("name", "unknown"), rev_email)
                db.add(Review(
                    pull_request_id=db_pr.id,
                    reviewer_id=reviewer.id,
                    state=ReviewState.APPROVED,
                    submitted_at=mr.updated_at,
                ))
        except Exception as e:
            logger.warning("Could not fetch approvals for MR %s: %s", mr.iid, e)

        new_count += 1

    await db.flush()
    return new_count
