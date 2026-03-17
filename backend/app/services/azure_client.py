import logging
import os
from datetime import datetime

from azure.devops.connection import Connection
from azure.devops.v7_1.git.models import GitPullRequestSearchCriteria
from git import Repo as GitRepo
from msrest.authentication import BasicAuthentication
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.db.models import Repository, PullRequest, Review, PRComment
from app.db.models.pull_request import PRState
from app.db.models.review import ReviewState
from app.db.models.pr_comment import PRCommentType
from app.services.identity import resolve_contributor
from app.config import settings

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

    bare_path = os.path.join(settings.repos_cache_dir, str(repo.id))

    existing = await db.execute(
        select(PullRequest.platform_pr_id, PullRequest.id, PullRequest.lines_added, PullRequest.lines_deleted)
        .where(PullRequest.repository_id == repo.id)
    )
    existing_rows = existing.all()
    existing_ids = {row[0] for row in existing_rows}
    zero_line_map = {row[0]: row[1] for row in existing_rows if row[2] == 0 and row[3] == 0}
    new_count = 0
    backfilled = 0

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
        source_commit = getattr(pr, "last_merge_source_commit", None)
        target_commit = getattr(pr, "last_merge_target_commit", None)
        source_sha = getattr(source_commit, "commit_id", None) if source_commit else None
        target_sha = getattr(target_commit, "commit_id", None) if target_commit else None

        if pr.pull_request_id in zero_line_map:
            added, deleted = _git_diff_stats(bare_path, source_sha, target_sha)
            if added > 0 or deleted > 0:
                await db.execute(
                    update(PullRequest)
                    .where(PullRequest.id == zero_line_map[pr.pull_request_id])
                    .values(lines_added=added, lines_deleted=deleted)
                )
                backfilled += 1

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

        comment_count, first_review_at, raw_comments = _fetch_threads(
            git_client, project, repo_name, pr.pull_request_id
        )

        iteration_count = _fetch_iteration_count(
            git_client, project, repo_name, pr.pull_request_id
        )

        lines_added, lines_deleted = _git_diff_stats(bare_path, source_sha, target_sha)

        db_pr = PullRequest(
            repository_id=repo.id,
            contributor_id=contributor.id,
            platform_pr_id=pr.pull_request_id,
            title=(pr.title or "")[:1024],
            state=state,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
            comment_count=comment_count,
            iteration_count=iteration_count,
            created_at=pr.creation_date,
            merged_at=pr.closed_date if state == PRState.MERGED else None,
            closed_at=pr.closed_date,
            first_review_at=first_review_at,
        )
        db.add(db_pr)
        await db.flush()

        for rc in raw_comments:
            author_contributor = None
            if rc["author_email"]:
                author_contributor = await resolve_contributor(db, rc["author_name"], rc["author_email"])
            ctype = PRCommentType.INLINE if rc["comment_type"] == "inline" else PRCommentType.GENERAL
            db.add(PRComment(
                pull_request_id=db_pr.id,
                author_name=rc["author_name"],
                author_id=author_contributor.id if author_contributor else None,
                body=rc["body"],
                thread_id=rc["thread_id"],
                file_path=rc["file_path"],
                line_number=rc["line_number"],
                comment_type=ctype,
                platform_comment_id=rc["platform_comment_id"],
                created_at=rc["created_at"] or pr.creation_date,
                updated_at=rc.get("updated_at"),
            ))

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
    if backfilled:
        logger.info("Azure DevOps: backfilled line stats for %d existing PRs in %s/%s", backfilled, project, repo_name)
        if sync_log:
            sync_log.info("prs", f"Backfilled line stats for {backfilled} existing PRs")
    logger.info("Azure DevOps: fetched %d new PRs for %s/%s", new_count, project, repo_name)
    return new_count


def _fetch_threads(
    git_client, project: str, repo_name: str, pr_id: int
) -> tuple[int, datetime | None, list[dict]]:
    """Fetch PR threads. Returns (comment_count, first_review_at, raw_comments)."""
    try:
        threads = git_client.get_threads(repo_name, pr_id, project=project)
    except Exception as e:
        logger.warning("Could not fetch threads for PR %d: %s", pr_id, e)
        return 0, None, []

    comment_count = 0
    first_review_at: datetime | None = None
    raw_comments: list[dict] = []

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

        thread_context = getattr(thread, "thread_context", None)
        file_path = None
        line_number = None
        if thread_context:
            file_path = getattr(thread_context, "file_path", None)
            right_pos = getattr(thread_context, "right_file_end", None) or getattr(thread_context, "right_file_start", None)
            if right_pos:
                line_number = getattr(right_pos, "line", None)

        thread_id_str = str(getattr(thread, "id", ""))
        for comment in comments:
            ctype = getattr(comment, "comment_type", None)
            if ctype == "system":
                continue
            author = getattr(comment, "author", None)
            raw_comments.append({
                "platform_comment_id": f"{thread_id_str}_{getattr(comment, 'id', '')}",
                "author_name": getattr(author, "display_name", "unknown") if author else "unknown",
                "author_email": (getattr(author, "unique_name", None) or "") if author else "",
                "body": getattr(comment, "content", "") or "",
                "thread_id": thread_id_str,
                "file_path": file_path,
                "line_number": line_number,
                "comment_type": "inline" if file_path else "general",
                "created_at": getattr(comment, "published_date", None),
                "updated_at": getattr(comment, "last_updated_date", None),
            })

    return comment_count, first_review_at, raw_comments


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


def _git_diff_stats(bare_path: str, source_sha: str | None, target_sha: str | None) -> tuple[int, int]:
    """Calculate lines added/deleted using local git diff on the bare mirror."""
    if not source_sha or not target_sha or not os.path.isdir(bare_path):
        return 0, 0
    try:
        local_repo = GitRepo(bare_path)
        merge_base = local_repo.git.merge_base(target_sha, source_sha).strip()
        numstat = local_repo.git.diff("--numstat", merge_base, source_sha)
        added = 0
        deleted = 0
        for line in numstat.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0] != "-":
                added += int(parts[0])
                deleted += int(parts[1])
        return added, deleted
    except Exception as e:
        logger.debug("Could not compute diff stats (%s..%s): %s", target_sha[:8] if target_sha else "?", source_sha[:8] if source_sha else "?", e)
        return 0, 0


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


async def sync_single_azure_pr(
    db: AsyncSession, repo: Repository, platform_pr_id: int,
    org_url: str | None = None, token: str | None = None,
) -> PullRequest | None:
    """Re-fetch a single PR from Azure DevOps, replacing existing reviews & comments."""
    if not org_url or not token or not repo.platform_owner or not repo.platform_repo:
        return None

    credentials = BasicAuthentication("", token)
    connection = Connection(base_url=org_url, creds=credentials)
    git_client = connection.clients.get_git_client()
    project, repo_name = _parse_project_and_repo(repo)
    bare_path = os.path.join(settings.repos_cache_dir, str(repo.id))

    try:
        pr = git_client.get_pull_request(repo_name, platform_pr_id, project=project)
    except Exception as e:
        logger.error("Azure DevOps API error fetching PR #%d: %s", platform_pr_id, e)
        return None

    result = await db.execute(
        select(PullRequest).where(
            PullRequest.repository_id == repo.id,
            PullRequest.platform_pr_id == platform_pr_id,
        )
    )
    db_pr = result.scalar_one_or_none()

    author_name = pr.created_by.display_name or "unknown"
    author_email = pr.created_by.unique_name or f"{author_name}@azure.com"
    contributor = await resolve_contributor(db, author_name, author_email)

    if pr.status == "completed":
        state = PRState.MERGED
    elif pr.status == "abandoned":
        state = PRState.CLOSED
    else:
        state = PRState.OPEN

    comment_count, first_review_at, raw_comments = _fetch_threads(
        git_client, project, repo_name, pr.pull_request_id
    )
    iteration_count = _fetch_iteration_count(
        git_client, project, repo_name, pr.pull_request_id
    )

    source_commit = getattr(pr, "last_merge_source_commit", None)
    target_commit = getattr(pr, "last_merge_target_commit", None)
    source_sha = getattr(source_commit, "commit_id", None) if source_commit else None
    target_sha = getattr(target_commit, "commit_id", None) if target_commit else None
    lines_added, lines_deleted = _git_diff_stats(bare_path, source_sha, target_sha)

    if db_pr:
        db_pr.title = (pr.title or "")[:1024]
        db_pr.state = state
        db_pr.contributor_id = contributor.id
        db_pr.lines_added = lines_added
        db_pr.lines_deleted = lines_deleted
        db_pr.comment_count = comment_count
        db_pr.iteration_count = iteration_count
        db_pr.created_at = pr.creation_date
        db_pr.merged_at = pr.closed_date if state == PRState.MERGED else None
        db_pr.closed_at = pr.closed_date
        db_pr.first_review_at = first_review_at
        await db.execute(delete(Review).where(Review.pull_request_id == db_pr.id))
        await db.execute(delete(PRComment).where(PRComment.pull_request_id == db_pr.id))
    else:
        db_pr = PullRequest(
            repository_id=repo.id,
            contributor_id=contributor.id,
            platform_pr_id=pr.pull_request_id,
            title=(pr.title or "")[:1024],
            state=state,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
            comment_count=comment_count,
            iteration_count=iteration_count,
            created_at=pr.creation_date,
            merged_at=pr.closed_date if state == PRState.MERGED else None,
            closed_at=pr.closed_date,
            first_review_at=first_review_at,
        )
        db.add(db_pr)
        await db.flush()

    for rc in raw_comments:
        author_contributor = None
        if rc["author_email"]:
            author_contributor = await resolve_contributor(db, rc["author_name"], rc["author_email"])
        ctype = PRCommentType.INLINE if rc["comment_type"] == "inline" else PRCommentType.GENERAL
        db.add(PRComment(
            pull_request_id=db_pr.id,
            author_name=rc["author_name"],
            author_id=author_contributor.id if author_contributor else None,
            body=rc["body"],
            thread_id=rc["thread_id"],
            file_path=rc["file_path"],
            line_number=rc["line_number"],
            comment_type=ctype,
            platform_comment_id=rc["platform_comment_id"],
            created_at=rc["created_at"] or pr.creation_date,
            updated_at=rc.get("updated_at"),
        ))

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

    await db.flush()
    return db_pr
