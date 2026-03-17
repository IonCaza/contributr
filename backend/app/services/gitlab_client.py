import logging

import gitlab
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.models import Repository, PullRequest, Review, PRComment
from app.db.models.pull_request import PRState
from app.db.models.review import ReviewState
from app.db.models.pr_comment import PRCommentType
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

        mr_detail = None
        lines_added = 0
        lines_deleted = 0
        try:
            mr_detail = gl_project.mergerequests.get(mr.iid)
            mr_changes = mr_detail.changes()
            for ch in mr_changes.get("changes", []):
                diff_text = ch.get("diff", "")
                for line in diff_text.split("\n"):
                    if line.startswith("+") and not line.startswith("+++"):
                        lines_added += 1
                    elif line.startswith("-") and not line.startswith("---"):
                        lines_deleted += 1
        except Exception:
            lines_added = getattr(mr, "changes_count", 0) or 0

        db_pr = PullRequest(
            repository_id=repo.id,
            contributor_id=contributor.id,
            platform_pr_id=mr.iid,
            title=(mr.title or "")[:1024],
            state=state,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
            created_at=mr.created_at,
            merged_at=getattr(mr, "merged_at", None),
            closed_at=getattr(mr, "closed_at", None),
        )
        db.add(db_pr)
        await db.flush()

        try:
            if not mr_detail:
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

        try:
            notes = mr_detail.notes.list(sort="asc", iterator=True) if mr_detail else []
            for note in notes:
                if getattr(note, "system", False):
                    continue
                n_author = note.author if isinstance(note.author, dict) else {}
                n_name = n_author.get("name") or n_author.get("username", "unknown")
                n_email = n_author.get("email") or f"{n_author.get('username', 'unknown')}@gitlab.com"
                n_contributor = await resolve_contributor(db, n_name, n_email)
                n_position = getattr(note, "position", None)
                n_file = None
                n_line = None
                ctype = PRCommentType.GENERAL
                if isinstance(n_position, dict) and n_position.get("new_path"):
                    n_file = n_position["new_path"]
                    n_line = n_position.get("new_line") or n_position.get("old_line")
                    ctype = PRCommentType.INLINE
                db.add(PRComment(
                    pull_request_id=db_pr.id,
                    author_name=n_name,
                    author_id=n_contributor.id,
                    body=getattr(note, "body", "") or "",
                    thread_id=str(getattr(note, "discussion_id", "")) or None,
                    file_path=n_file,
                    line_number=n_line,
                    comment_type=ctype,
                    platform_comment_id=str(note.id),
                    created_at=getattr(note, "created_at", mr.created_at),
                    updated_at=getattr(note, "updated_at", None),
                ))
        except Exception as e:
            logger.warning("Could not fetch notes for MR %s: %s", mr.iid, e)

        new_count += 1

    await db.flush()
    return new_count


async def sync_single_gitlab_mr(
    db: AsyncSession, repo: Repository, platform_pr_id: int,
    token: str | None = None, url: str = "https://gitlab.com",
) -> PullRequest | None:
    """Re-fetch a single MR from GitLab, replacing existing reviews & comments."""
    if not repo.platform_owner or not repo.platform_repo:
        return None

    gl = gitlab.Gitlab(url, private_token=token)
    project_path = f"{repo.platform_owner}/{repo.platform_repo}"
    try:
        gl_project = gl.projects.get(project_path)
        mr = gl_project.mergerequests.get(platform_pr_id)
    except Exception as e:
        logger.error("GitLab API error fetching MR !%d: %s", platform_pr_id, e)
        return None

    result = await db.execute(
        select(PullRequest).where(
            PullRequest.repository_id == repo.id,
            PullRequest.platform_pr_id == platform_pr_id,
        )
    )
    db_pr = result.scalar_one_or_none()

    author = mr.author or {}
    author_email = author.get("email") or f"{author.get('username', 'unknown')}@gitlab.com"
    author_name = author.get("name") or author.get("username", "unknown")
    contributor = await resolve_contributor(db, author_name, author_email)

    state = STATE_MAP.get(mr.state, PRState.OPEN)

    lines_added = 0
    lines_deleted = 0
    try:
        mr_changes = mr.changes()
        for ch in mr_changes.get("changes", []):
            diff_text = ch.get("diff", "")
            for line in diff_text.split("\n"):
                if line.startswith("+") and not line.startswith("+++"):
                    lines_added += 1
                elif line.startswith("-") and not line.startswith("---"):
                    lines_deleted += 1
    except Exception:
        lines_added = getattr(mr, "changes_count", 0) or 0

    if db_pr:
        db_pr.title = (mr.title or "")[:1024]
        db_pr.state = state
        db_pr.contributor_id = contributor.id
        db_pr.lines_added = lines_added
        db_pr.lines_deleted = lines_deleted
        db_pr.created_at = mr.created_at
        db_pr.merged_at = getattr(mr, "merged_at", None)
        db_pr.closed_at = getattr(mr, "closed_at", None)
        await db.execute(delete(Review).where(Review.pull_request_id == db_pr.id))
        await db.execute(delete(PRComment).where(PRComment.pull_request_id == db_pr.id))
    else:
        db_pr = PullRequest(
            repository_id=repo.id,
            contributor_id=contributor.id,
            platform_pr_id=mr.iid,
            title=(mr.title or "")[:1024],
            state=state,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
            created_at=mr.created_at,
            merged_at=getattr(mr, "merged_at", None),
            closed_at=getattr(mr, "closed_at", None),
        )
        db.add(db_pr)
        await db.flush()

    try:
        for approver in getattr(mr, "approved_by", []) or []:
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
        logger.warning("Could not fetch approvals for MR %s: %s", platform_pr_id, e)

    comment_count = 0
    first_review_at = None
    try:
        for note in mr.notes.list(sort="asc", iterator=True):
            if getattr(note, "system", False):
                continue
            n_author = note.author if isinstance(note.author, dict) else {}
            n_name = n_author.get("name") or n_author.get("username", "unknown")
            n_email = n_author.get("email") or f"{n_author.get('username', 'unknown')}@gitlab.com"
            n_contributor = await resolve_contributor(db, n_name, n_email)
            n_position = getattr(note, "position", None)
            n_file = None
            n_line = None
            ctype = PRCommentType.GENERAL
            if isinstance(n_position, dict) and n_position.get("new_path"):
                n_file = n_position["new_path"]
                n_line = n_position.get("new_line") or n_position.get("old_line")
                ctype = PRCommentType.INLINE
            created = getattr(note, "created_at", mr.created_at)
            db.add(PRComment(
                pull_request_id=db_pr.id,
                author_name=n_name,
                author_id=n_contributor.id,
                body=getattr(note, "body", "") or "",
                thread_id=str(getattr(note, "discussion_id", "")) or None,
                file_path=n_file,
                line_number=n_line,
                comment_type=ctype,
                platform_comment_id=str(note.id),
                created_at=created,
                updated_at=getattr(note, "updated_at", None),
            ))
            comment_count += 1
            if first_review_at is None or created < first_review_at:
                first_review_at = created
    except Exception as e:
        logger.warning("Could not fetch notes for MR %s: %s", platform_pr_id, e)

    db_pr.comment_count = comment_count
    db_pr.first_review_at = first_review_at
    await db.flush()
    return db_pr
