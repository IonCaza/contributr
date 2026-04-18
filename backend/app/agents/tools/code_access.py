"""Agent tools for source-code exploration and PR diff analysis.

Group A (local git): uses GitPython on the bare mirrors already cloned at
``settings.repos_cache_dir``.

Group B (platform API): uses PyGitHub / python-gitlab with encrypted
platform credentials for PR-specific data.
"""

from __future__ import annotations

import logging
import os

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Repository, Project
from app.db.models.agent_memory import AgentMemory
from app.db.models.platform_credential import PlatformCredential
from app.db.models.repository import Platform
from app.agents.tools.base import ToolDefinition
from app.agents.tools.registry import register_tool_category

logger = logging.getLogger(__name__)

CATEGORY = "code_access"

MAX_FILE_BYTES = 50_000
MAX_DIFF_BYTES = 100_000
MAX_SEARCH_RESULTS = 50
MAX_BLAME_LINES = 500
MAX_HISTORY_ENTRIES = 30
GIT_TIMEOUT = 30

DEFINITIONS = [
    ToolDefinition("list_directory", "List Directory", "Browse files and directories in a repository at a given ref", CATEGORY),
    ToolDefinition("read_file", "Read File", "Read the full contents of a file in a repository at a given ref", CATEGORY),
    ToolDefinition("search_code", "Search Code", "Grep for a pattern in a repository's codebase", CATEGORY),
    ToolDefinition("get_commit_diff", "Commit Diff", "Get the full diff for a specific commit", CATEGORY),
    ToolDefinition("get_file_blame", "File Blame", "Show blame annotations for a file", CATEGORY),
    ToolDefinition("get_file_history", "File History", "Commit history for a specific file", CATEGORY),
    ToolDefinition("get_pr_changed_files", "PR Changed Files", "List files changed in a pull request with status and line counts", CATEGORY),
    ToolDefinition("get_pr_file_diff", "PR File Diff", "Get the patch/diff for a single file in a pull request", CATEGORY),
    ToolDefinition("get_pr_review_comments", "PR Review Comments", "Get review discussion comments on a pull request", CATEGORY),
    ToolDefinition("get_project_standards", "Project Standards", "Retrieve project-level coding standards and conventions stored as reference memories", CATEGORY, concurrency_safe=True),
    ToolDefinition("post_review_comment", "Post Review Comment", "Post an inline review comment on a PR at a specific file and line", CATEGORY),
    ToolDefinition("submit_review", "Submit Review", "Submit a complete PR review with a verdict (approve, request_changes, comment)", CATEGORY),
]


# ── Helpers ────────────────────────────────────────────────────────────


async def _safe(db: AsyncSession, coro):
    try:
        async with db.begin_nested():
            return await coro
    except Exception as e:
        logger.warning("Tool query failed: %s", e)
        return f"Error: {e}"


def _truncate(text: str, limit: int, label: str = "output") -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n... [{label} truncated at {limit:,} characters] ..."


async def _resolve_repo(db: AsyncSession, name: str) -> tuple[Repository, str] | str:
    """Fuzzy-match a repository name and return (repo, bare_mirror_path) or an error string."""
    result = await db.execute(
        select(Repository).where(Repository.name.ilike(f"%{name}%")).order_by(Repository.name).limit(1)
    )
    repo = result.scalar_one_or_none()
    if not repo:
        return f"No repository found matching '{name}'."
    bare_path = os.path.join(settings.repos_cache_dir, str(repo.id))
    if not os.path.isdir(bare_path):
        return f"Repository '{repo.name}' has not been synced yet (no local clone)."
    return repo, bare_path


def _open_git_repo(bare_path: str):
    from git import Repo as GitRepo
    return GitRepo(bare_path)


def _default_ref(bare_path: str) -> str:
    """Resolve HEAD for a bare repo, falling back to 'main'."""
    try:
        repo = _open_git_repo(bare_path)
        return repo.git.rev_parse("HEAD", kill_after_timeout=GIT_TIMEOUT)
    except Exception:
        return "HEAD"


async def _resolve_platform_token(
    db: AsyncSession, platform: Platform,
) -> tuple[str | None, str | None]:
    from app.api.platform_credentials import decrypt_token

    result = await db.execute(
        select(PlatformCredential)
        .where(PlatformCredential.platform == platform)
        .order_by(PlatformCredential.created_at.desc())
        .limit(1)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        return None, None
    try:
        token = decrypt_token(cred.token_encrypted)
    except Exception:
        return None, None
    return token, cred.base_url


def _github_pr_files(repo: Repository, pr_number: int, token: str | None):
    """Return list of PullRequest File objects from GitHub."""
    from github import Github, GithubException
    gh = Github(token) if token else Github()
    try:
        gh_repo = gh.get_repo(f"{repo.platform_owner}/{repo.platform_repo}")
        pr = gh_repo.get_pull(pr_number)
        files = list(pr.get_files())
        return files, pr
    except GithubException as e:
        raise RuntimeError(f"GitHub API error: {e}") from e
    finally:
        gh.close()


def _gitlab_mr_changes(repo: Repository, mr_iid: int, token: str | None, base_url: str | None):
    """Return list of change dicts from GitLab."""
    import gitlab
    url = base_url or "https://gitlab.com"
    gl = gitlab.Gitlab(url, private_token=token)
    try:
        project = gl.projects.get(f"{repo.platform_owner}/{repo.platform_repo}")
        mr = project.mergerequests.get(mr_iid)
        changes = mr.changes()
        return changes.get("changes", []), mr
    except gitlab.exceptions.GitlabError as e:
        raise RuntimeError(f"GitLab API error: {e}") from e


_ADO_SYSTEM_THREAD_TYPES = frozenset({"System", "VoteUpdate", "StatusUpdate", "RefUpdate", "PolicyStatusUpdate"})


def _ado_connection(token: str | None, base_url: str | None):
    from azure.devops.connection import Connection
    from msrest.authentication import BasicAuthentication
    if not token or not base_url:
        raise RuntimeError("Azure DevOps credentials not configured.")
    creds = BasicAuthentication("", token)
    return Connection(base_url=base_url, creds=creds)


def _ado_parse(repo: "Repository") -> tuple[str, str]:
    owner = repo.platform_owner or ""
    parts = owner.split("/", 1)
    project = parts[1] if len(parts) > 1 else parts[0]
    return project, repo.platform_repo


async def _azure_pr_changed_files(repo, pr_number: int, token, base_url) -> str:
    conn = _ado_connection(token, base_url)
    git_client = conn.clients.get_git_client()
    project, repo_name = _ado_parse(repo)

    try:
        pr = git_client.get_pull_request_by_id(pr_number, project=project)
    except Exception as e:
        return f"Error fetching Azure PR #{pr_number}: {e}"

    try:
        iterations = git_client.get_pull_request_iterations(repo_name, pr_number, project=project)
    except Exception as e:
        return f"Error fetching iterations: {e}"

    if not iterations:
        return f"No iterations found for PR #{pr_number}."

    last_iter = iterations[-1]
    try:
        changes = git_client.get_pull_request_iteration_changes(
            repo_name, pr_number, last_iter.id, project=project,
        )
    except Exception as e:
        return f"Error fetching changes: {e}"

    entries = getattr(changes, "change_entries", []) or []
    title = getattr(pr, "title", "") or ""
    header = f"**PR #{pr_number}** {title} — {len(entries)} file(s) changed\n\n"

    rows = []
    for entry in entries:
        item = getattr(entry, "item", None)
        path = getattr(item, "path", "?") if item else "?"
        change_type = getattr(entry, "change_type", "edit") or "edit"
        rows.append(f"- `{path}` [{change_type}]")

    return header + "\n".join(rows[:200])


async def _azure_pr_file_diff(repo, pr_number: int, file_path: str, token, base_url) -> str:
    conn = _ado_connection(token, base_url)
    git_client = conn.clients.get_git_client()
    project, repo_name = _ado_parse(repo)

    try:
        pr = git_client.get_pull_request_by_id(pr_number, project=project)
    except Exception as e:
        return f"Error fetching Azure PR #{pr_number}: {e}"

    target_ref = getattr(pr, "target_ref_name", "refs/heads/main") or "refs/heads/main"
    source_ref = getattr(pr, "source_ref_name", "") or ""

    bare_path = os.path.join(settings.repos_cache_dir, str(repo.id))
    if not os.path.isdir(bare_path):
        return "Repository not synced locally. Cannot compute diff."

    git_repo = _open_git_repo(bare_path)
    target_branch = target_ref.replace("refs/heads/", "")
    source_branch = source_ref.replace("refs/heads/", "")

    try:
        diff = git_repo.git.diff(
            f"origin/{target_branch}...origin/{source_branch}",
            "--", file_path,
            kill_after_timeout=GIT_TIMEOUT,
        )
    except Exception:
        try:
            diff = git_repo.git.diff(
                f"{target_branch}...{source_branch}",
                "--", file_path,
                kill_after_timeout=GIT_TIMEOUT,
            )
        except Exception as e:
            return f"Error computing diff for '{file_path}': {e}"

    if not diff.strip():
        return f"No changes found for `{file_path}` in PR #{pr_number}."

    diff = _truncate(diff, MAX_DIFF_BYTES, "diff")
    header = f"**PR #{pr_number}** `{file_path}`\n\n"
    return header + f"```diff\n{diff}\n```"


async def _azure_pr_review_comments(repo, pr_number: int, token, base_url) -> str:
    conn = _ado_connection(token, base_url)
    git_client = conn.clients.get_git_client()
    project, repo_name = _ado_parse(repo)

    try:
        pr = git_client.get_pull_request_by_id(pr_number, project=project)
    except Exception as e:
        return f"Error fetching Azure PR #{pr_number}: {e}"

    try:
        threads = git_client.get_threads(repo_name, pr_number, project=project)
    except Exception as e:
        return f"Error fetching threads: {e}"

    title = getattr(pr, "title", "") or ""
    items = []
    for thread in threads or []:
        props = thread.properties or {}
        thread_type = None
        if hasattr(props, "get"):
            thread_type = props.get("CodeReviewThreadType", {}).get("$value")
        elif isinstance(props, dict):
            thread_type = props.get("CodeReviewThreadType", {}).get("$value")

        if thread_type in _ADO_SYSTEM_THREAD_TYPES:
            continue

        thread_context = getattr(thread, "thread_context", None)
        file_path = getattr(thread_context, "file_path", None) if thread_context else None

        for comment in (thread.comments or []):
            ctype = getattr(comment, "comment_type", None)
            if ctype == "system":
                continue
            author = getattr(comment, "author", None)
            name = getattr(author, "display_name", "unknown") if author else "unknown"
            body = (getattr(comment, "content", "") or "")[:500]
            line_info = ""
            if file_path:
                line_info = f" on `{file_path}`"
            items.append(f"**{name}**{line_info}\n> {body}\n")

    if not items:
        return f"No review comments on PR #{pr_number} ({title})."

    header = f"**PR #{pr_number}** {title} — {len(items)} comment(s)\n\n"
    return header + "\n".join(items[:50])


# ── Tool factory ───────────────────────────────────────────────────────


def _build_code_access_tools(db: AsyncSession) -> list:

    # ── Group A: local git tools ───────────────────────────────────────

    @tool
    async def list_directory(repo_name: str, path: str = "", ref: str = "") -> str:
        """Browse files and directories in a repository.

        Args:
            repo_name: Repository name (fuzzy match).
            path: Directory path relative to repo root. Empty string for root.
            ref: Git ref (branch, tag, SHA). Defaults to HEAD.
        """
        async def _impl():
            resolved = await _resolve_repo(db, repo_name)
            if isinstance(resolved, str):
                return resolved
            repo, bare_path = resolved
            git_repo = _open_git_repo(bare_path)

            target_ref = ref or _default_ref(bare_path)
            tree_ref = f"{target_ref}:{path}" if path else target_ref

            try:
                output = git_repo.git.ls_tree(
                    "--name-only", tree_ref,
                    kill_after_timeout=GIT_TIMEOUT,
                )
            except Exception as e:
                return f"Error listing directory: {e}"

            if not output.strip():
                return f"No files found at '{path}' on ref '{target_ref}'."

            entries = output.strip().split("\n")
            full_output = git_repo.git.ls_tree(tree_ref, kill_after_timeout=GIT_TIMEOUT)
            classified = []
            for line in full_output.strip().split("\n"):
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    kind = "dir/" if parts[1] == "tree" else ""
                    classified.append(f"{kind}{parts[3]}")

            header = f"**{repo.name}** `{path or '/'}` @ `{target_ref[:12]}`\n\n"
            return header + "\n".join(f"- `{e}`" for e in classified)

        return await _safe(db, _impl())

    @tool
    async def read_file(repo_name: str, file_path: str, ref: str = "") -> str:
        """Read the full contents of a file in a repository.

        Args:
            repo_name: Repository name (fuzzy match).
            file_path: Path relative to repo root (e.g. 'src/main.py').
            ref: Git ref (branch, tag, SHA). Defaults to HEAD.
        """
        async def _impl():
            resolved = await _resolve_repo(db, repo_name)
            if isinstance(resolved, str):
                return resolved
            repo, bare_path = resolved
            git_repo = _open_git_repo(bare_path)

            target_ref = ref or _default_ref(bare_path)
            try:
                content = git_repo.git.show(
                    f"{target_ref}:{file_path}",
                    kill_after_timeout=GIT_TIMEOUT,
                )
            except Exception as e:
                return f"Error reading '{file_path}': {e}"

            content = _truncate(content, MAX_FILE_BYTES, "file")
            lines = content.split("\n")
            numbered = "\n".join(f"{i + 1:>5} | {line}" for i, line in enumerate(lines))
            header = f"**{repo.name}** `{file_path}` @ `{target_ref[:12]}` ({len(lines)} lines)\n\n"
            return header + f"```\n{numbered}\n```"

        return await _safe(db, _impl())

    @tool
    async def search_code(repo_name: str, pattern: str, path: str = "", ref: str = "") -> str:
        """Grep for a pattern in a repository's codebase.

        Args:
            repo_name: Repository name (fuzzy match).
            pattern: Search pattern (regex supported).
            path: Limit search to this directory path. Empty for whole repo.
            ref: Git ref. Defaults to HEAD.
        """
        async def _impl():
            resolved = await _resolve_repo(db, repo_name)
            if isinstance(resolved, str):
                return resolved
            repo, bare_path = resolved
            git_repo = _open_git_repo(bare_path)

            target_ref = ref or _default_ref(bare_path)
            args = ["-n", "-I", "--max-count", str(MAX_SEARCH_RESULTS), pattern, target_ref]
            if path:
                args.extend(["--", path])

            try:
                output = git_repo.git.grep(*args, kill_after_timeout=GIT_TIMEOUT)
            except Exception as e:
                err_str = str(e)
                if "exit code(1)" in err_str:
                    return f"No matches found for '{pattern}' in {repo.name}."
                return f"Error searching: {e}"

            lines = output.strip().split("\n")
            header = f"**{repo.name}** search for `{pattern}` — {len(lines)} result(s)\n\n"
            return header + _truncate(output, MAX_FILE_BYTES, "search results")

        return await _safe(db, _impl())

    @tool
    async def get_commit_diff(repo_name: str, commit_sha: str) -> str:
        """Get the full diff for a specific commit.

        Args:
            repo_name: Repository name (fuzzy match).
            commit_sha: Full or abbreviated commit SHA.
        """
        async def _impl():
            resolved = await _resolve_repo(db, repo_name)
            if isinstance(resolved, str):
                return resolved
            repo, bare_path = resolved
            git_repo = _open_git_repo(bare_path)

            try:
                header_info = git_repo.git.show(
                    "--no-patch", "--format=%H%n%an%n%ae%n%ai%n%s", commit_sha,
                    kill_after_timeout=GIT_TIMEOUT,
                )
                parts = header_info.strip().split("\n", 4)
                sha, author, email, date_str, subject = (parts + [""] * 5)[:5]

                diff = git_repo.git.show(
                    "--stat", "--patch", "--format=", commit_sha,
                    kill_after_timeout=GIT_TIMEOUT,
                )
            except Exception as e:
                return f"Error getting diff for '{commit_sha}': {e}"

            diff = _truncate(diff, MAX_DIFF_BYTES, "diff")
            meta = (
                f"**Commit** `{sha[:12]}`\n"
                f"**Author:** {author} <{email}>\n"
                f"**Date:** {date_str}\n"
                f"**Subject:** {subject}\n\n"
            )
            return meta + f"```diff\n{diff}\n```"

        return await _safe(db, _impl())

    @tool
    async def get_file_blame(repo_name: str, file_path: str, ref: str = "") -> str:
        """Show blame annotations for a file (who wrote each line).

        Args:
            repo_name: Repository name (fuzzy match).
            file_path: Path relative to repo root.
            ref: Git ref. Defaults to HEAD.
        """
        async def _impl():
            resolved = await _resolve_repo(db, repo_name)
            if isinstance(resolved, str):
                return resolved
            repo, bare_path = resolved
            git_repo = _open_git_repo(bare_path)

            target_ref = ref or _default_ref(bare_path)
            try:
                output = git_repo.git.blame(
                    "--line-porcelain", target_ref, "--", file_path,
                    kill_after_timeout=GIT_TIMEOUT,
                )
            except Exception as e:
                return f"Error getting blame for '{file_path}': {e}"

            entries = []
            current: dict = {}
            for line in output.split("\n"):
                if line.startswith("author "):
                    current["author"] = line[7:]
                elif line.startswith("summary "):
                    current["summary"] = line[8:]
                elif line.startswith("\t"):
                    current["code"] = line[1:]
                    entries.append(current)
                    current = {}

            if len(entries) > MAX_BLAME_LINES:
                entries = entries[:MAX_BLAME_LINES]
                truncated = True
            else:
                truncated = False

            lines = []
            for i, e in enumerate(entries, 1):
                author = e.get("author", "?")[:20]
                code = e.get("code", "")
                lines.append(f"{i:>5} | {author:<20} | {code}")

            header = f"**{repo.name}** blame for `{file_path}` @ `{target_ref[:12]}` ({len(entries)} lines)\n\n"
            if truncated:
                header += f"_Showing first {MAX_BLAME_LINES} lines._\n\n"
            return header + "```\n" + "\n".join(lines) + "\n```"

        return await _safe(db, _impl())

    @tool
    async def get_file_history(repo_name: str, file_path: str, ref: str = "", limit: int = 20) -> str:
        """Show commit history for a specific file.

        Args:
            repo_name: Repository name (fuzzy match).
            file_path: Path relative to repo root.
            ref: Git ref. Defaults to HEAD.
            limit: Max number of commits to return (default 20, max 30).
        """
        async def _impl():
            resolved = await _resolve_repo(db, repo_name)
            if isinstance(resolved, str):
                return resolved
            repo, bare_path = resolved
            git_repo = _open_git_repo(bare_path)

            target_ref = ref or _default_ref(bare_path)
            n = min(int(limit), MAX_HISTORY_ENTRIES)
            try:
                output = git_repo.git.log(
                    f"--max-count={n}", "--follow",
                    "--format=%H|%an|%ai|%s",
                    target_ref, "--", file_path,
                    kill_after_timeout=GIT_TIMEOUT,
                )
            except Exception as e:
                return f"Error getting history for '{file_path}': {e}"

            if not output.strip():
                return f"No commit history found for '{file_path}'."

            rows = []
            for line in output.strip().split("\n"):
                parts = line.split("|", 3)
                if len(parts) >= 4:
                    sha, author, date_str, subject = parts
                    rows.append(f"- `{sha[:10]}` {date_str[:10]} **{author}** — {subject}")

            header = f"**{repo.name}** history for `{file_path}` ({len(rows)} commits)\n\n"
            return header + "\n".join(rows)

        return await _safe(db, _impl())

    # ── Group B: platform API tools ────────────────────────────────────

    @tool
    async def get_pr_changed_files(repo_name: str, pr_number: int) -> str:
        """List files changed in a pull request with status and line counts.

        Args:
            repo_name: Repository name (fuzzy match).
            pr_number: Pull request / merge request number on the platform.
        """
        async def _impl():
            resolved = await _resolve_repo(db, repo_name)
            if isinstance(resolved, str):
                return resolved
            repo, _ = resolved

            token, base_url = await _resolve_platform_token(db, repo.platform)

            if repo.platform == Platform.GITHUB:
                files, pr = _github_pr_files(repo, pr_number, token)
                header = f"**PR #{pr_number}** {pr.title} — {len(files)} file(s) changed\n\n"
                header += f"State: {pr.state} | +{pr.additions} -{pr.deletions}\n\n"
                rows = []
                for f in files:
                    status = getattr(f, "status", "modified")
                    rows.append(f"- `{f.filename}` [{status}] +{f.additions} -{f.deletions}")
                return header + "\n".join(rows)

            elif repo.platform == Platform.GITLAB:
                changes, mr = _gitlab_mr_changes(repo, pr_number, token, base_url)
                header = f"**MR !{pr_number}** {mr.title} — {len(changes)} file(s) changed\n\n"
                rows = []
                for c in changes:
                    new_path = c.get("new_path", "?")
                    status = "added" if c.get("new_file") else "deleted" if c.get("deleted_file") else "renamed" if c.get("renamed_file") else "modified"
                    rows.append(f"- `{new_path}` [{status}]")
                return header + "\n".join(rows)

            elif repo.platform == Platform.AZURE:
                return await _azure_pr_changed_files(repo, pr_number, token, base_url)

            return f"Unsupported platform: {repo.platform}"

        return await _safe(db, _impl())

    @tool
    async def get_pr_file_diff(repo_name: str, pr_number: int, file_path: str) -> str:
        """Get the patch/diff for a single file in a pull request.

        Args:
            repo_name: Repository name (fuzzy match).
            pr_number: Pull request / merge request number.
            file_path: Exact file path to get the diff for.
        """
        async def _impl():
            resolved = await _resolve_repo(db, repo_name)
            if isinstance(resolved, str):
                return resolved
            repo, _ = resolved

            token, base_url = await _resolve_platform_token(db, repo.platform)

            if repo.platform == Platform.GITHUB:
                files, pr = _github_pr_files(repo, pr_number, token)
                target = None
                for f in files:
                    if f.filename == file_path:
                        target = f
                        break
                if not target:
                    available = [f.filename for f in files[:20]]
                    return f"File '{file_path}' not found in PR #{pr_number}.\n\nFiles in this PR:\n" + "\n".join(f"- `{f}`" for f in available)

                patch = getattr(target, "patch", None) or "(no patch — binary file or too large)"
                patch = _truncate(patch, MAX_DIFF_BYTES, "patch")
                header = (
                    f"**PR #{pr_number}** `{file_path}` [{target.status}] "
                    f"+{target.additions} -{target.deletions}\n\n"
                )
                return header + f"```diff\n{patch}\n```"

            elif repo.platform == Platform.GITLAB:
                changes, mr = _gitlab_mr_changes(repo, pr_number, token, base_url)
                target = None
                for c in changes:
                    if c.get("new_path") == file_path or c.get("old_path") == file_path:
                        target = c
                        break
                if not target:
                    available = [c.get("new_path", "?") for c in changes[:20]]
                    return f"File '{file_path}' not found in MR !{pr_number}.\n\nFiles in this MR:\n" + "\n".join(f"- `{f}`" for f in available)

                diff_text = target.get("diff", "(no diff available)")
                diff_text = _truncate(diff_text, MAX_DIFF_BYTES, "diff")
                status = "added" if target.get("new_file") else "deleted" if target.get("deleted_file") else "modified"
                header = f"**MR !{pr_number}** `{file_path}` [{status}]\n\n"
                return header + f"```diff\n{diff_text}\n```"

            elif repo.platform == Platform.AZURE:
                return await _azure_pr_file_diff(repo, pr_number, file_path, token, base_url)

            return f"Unsupported platform: {repo.platform}"

        return await _safe(db, _impl())

    @tool
    async def get_pr_review_comments(repo_name: str, pr_number: int) -> str:
        """Get review discussion comments on a pull request.

        Args:
            repo_name: Repository name (fuzzy match).
            pr_number: Pull request / merge request number.
        """
        async def _impl():
            resolved = await _resolve_repo(db, repo_name)
            if isinstance(resolved, str):
                return resolved
            repo, _ = resolved

            token, base_url = await _resolve_platform_token(db, repo.platform)

            if repo.platform == Platform.GITHUB:
                from github import Github, GithubException
                gh = Github(token) if token else Github()
                try:
                    gh_repo = gh.get_repo(f"{repo.platform_owner}/{repo.platform_repo}")
                    pr = gh_repo.get_pull(pr_number)
                    comments = list(pr.get_review_comments())

                    if not comments:
                        return f"No review comments on PR #{pr_number} ({pr.title})."

                    header = f"**PR #{pr_number}** {pr.title} — {len(comments)} review comment(s)\n\n"
                    items = []
                    for c in comments[:50]:
                        user = c.user.login if c.user else "unknown"
                        path = c.path or ""
                        line = c.original_line or c.line or ""
                        body = (c.body or "")[:500]
                        items.append(
                            f"**{user}** on `{path}`"
                            + (f" line {line}" if line else "")
                            + f"\n> {body}\n"
                        )
                    return header + "\n".join(items)
                except GithubException as e:
                    return f"GitHub API error: {e}"
                finally:
                    gh.close()

            elif repo.platform == Platform.GITLAB:
                import gitlab as gl_lib
                url = base_url or "https://gitlab.com"
                gl = gl_lib.Gitlab(url, private_token=token)
                try:
                    project = gl.projects.get(f"{repo.platform_owner}/{repo.platform_repo}")
                    mr = project.mergerequests.get(pr_number)
                    notes = mr.notes.list(sort="asc", iterator=True)
                    discussion_notes = [n for n in notes if not getattr(n, "system", False)]

                    if not discussion_notes:
                        return f"No discussion notes on MR !{pr_number} ({mr.title})."

                    header = f"**MR !{pr_number}** {mr.title} — {len(discussion_notes)} note(s)\n\n"
                    items = []
                    for n in discussion_notes[:50]:
                        author = n.author.get("name", "unknown") if isinstance(n.author, dict) else "unknown"
                        body = (n.body or "")[:500]
                        items.append(f"**{author}**\n> {body}\n")
                    return header + "\n".join(items)
                except gl_lib.exceptions.GitlabError as e:
                    return f"GitLab API error: {e}"

            elif repo.platform == Platform.AZURE:
                return await _azure_pr_review_comments(repo, pr_number, token, base_url)

            return f"Unsupported platform: {repo.platform}"

        return await _safe(db, _impl())

    # ── Group C: standards & write-back tools ──────────────────────────

    @tool
    async def get_project_standards(project_name: str) -> str:
        """Retrieve project-level coding standards, conventions, and reference docs.

        Searches the project's reference memories for coding standards,
        style guides, and architectural conventions that should be enforced
        during code review.

        Args:
            project_name: Project name (fuzzy match).
        """
        async def _impl():
            result = await db.execute(
                select(Project).where(Project.name.ilike(f"%{project_name}%")).limit(1)
            )
            project = result.scalar_one_or_none()
            if not project:
                return f"No project found matching '{project_name}'."

            result = await db.execute(
                select(AgentMemory).where(
                    AgentMemory.project_id == project.id,
                    AgentMemory.type == "reference",
                ).order_by(AgentMemory.created_at.desc()).limit(20)
            )
            memories = result.scalars().all()

            if not memories:
                return f"No coding standards or reference documents found for project '{project.name}'. The team may not have configured project-level standards yet."

            header = f"**{project.name}** — {len(memories)} standard(s) / reference(s)\n\n"
            items = []
            for m in memories:
                items.append(f"### {m.name}\n_{m.description}_\n\n{m.content}\n")
            return header + "\n---\n".join(items)

        return await _safe(db, _impl())

    @tool
    async def post_review_comment(
        repo_name: str,
        pr_number: int,
        file_path: str,
        line: int,
        body: str,
        side: str = "RIGHT",
    ) -> str:
        """Post an inline review comment on a specific file and line in a PR.

        Args:
            repo_name: Repository name (fuzzy match).
            pr_number: Pull request / merge request number.
            file_path: The file path the comment applies to.
            line: The line number in the diff (new-file side by default).
            body: The comment text (markdown supported).
            side: Which side of the diff: RIGHT (new) or LEFT (old). Default RIGHT.
        """
        async def _impl():
            resolved = await _resolve_repo(db, repo_name)
            if isinstance(resolved, str):
                return resolved
            repo, _ = resolved

            token, base_url = await _resolve_platform_token(db, repo.platform)
            if not token:
                return f"No credentials configured for {repo.platform.value}. Cannot post comments."

            if repo.platform == Platform.GITHUB:
                return _github_post_review_comment(repo, pr_number, file_path, line, body, side, token)
            elif repo.platform == Platform.GITLAB:
                return _gitlab_post_review_comment(repo, pr_number, file_path, line, body, token, base_url)
            elif repo.platform == Platform.AZURE:
                return _azure_post_review_comment(repo, pr_number, file_path, line, body, token, base_url)

            return f"Unsupported platform: {repo.platform}"

        return await _safe(db, _impl())

    @tool
    async def submit_review(
        repo_name: str,
        pr_number: int,
        summary: str,
        verdict: str = "COMMENT",
    ) -> str:
        """Submit a complete PR review with an overall verdict.

        Args:
            repo_name: Repository name (fuzzy match).
            pr_number: Pull request / merge request number.
            summary: The overall review summary (markdown).
            verdict: One of APPROVE, REQUEST_CHANGES, or COMMENT (default COMMENT).
        """
        async def _impl():
            resolved = await _resolve_repo(db, repo_name)
            if isinstance(resolved, str):
                return resolved
            repo, _ = resolved

            token, base_url = await _resolve_platform_token(db, repo.platform)
            if not token:
                return f"No credentials configured for {repo.platform.value}. Cannot submit review."

            verdict_upper = verdict.upper()
            if verdict_upper not in ("APPROVE", "REQUEST_CHANGES", "COMMENT"):
                return f"Invalid verdict '{verdict}'. Must be APPROVE, REQUEST_CHANGES, or COMMENT."

            if repo.platform == Platform.GITHUB:
                return _github_submit_review(repo, pr_number, summary, verdict_upper, token)
            elif repo.platform == Platform.GITLAB:
                return _gitlab_submit_review(repo, pr_number, summary, token, base_url)
            elif repo.platform == Platform.AZURE:
                return _azure_submit_review(repo, pr_number, summary, verdict_upper, token, base_url)

            return f"Unsupported platform: {repo.platform}"

        return await _safe(db, _impl())

    return [
        list_directory,
        read_file,
        search_code,
        get_commit_diff,
        get_file_blame,
        get_file_history,
        get_pr_changed_files,
        get_pr_file_diff,
        get_pr_review_comments,
        get_project_standards,
        post_review_comment,
        submit_review,
    ]


# ── Platform write-back helpers ────────────────────────────────────────


def _github_post_review_comment(
    repo: Repository, pr_number: int, file_path: str,
    line: int, body: str, side: str, token: str,
) -> str:
    from github import Github, GithubException
    gh = Github(token)
    try:
        gh_repo = gh.get_repo(f"{repo.platform_owner}/{repo.platform_repo}")
        pr = gh_repo.get_pull(pr_number)
        commit = pr.get_commits().reversed[0]
        pr.create_review_comment(
            body=body, commit=commit, path=file_path, line=line, side=side,
        )
        return f"Posted inline comment on `{file_path}` line {line} in PR #{pr_number}."
    except GithubException as e:
        return f"GitHub API error posting comment: {e}"
    finally:
        gh.close()


def _github_submit_review(
    repo: Repository, pr_number: int, summary: str,
    verdict: str, token: str,
) -> str:
    from github import Github, GithubException
    gh = Github(token)
    try:
        gh_repo = gh.get_repo(f"{repo.platform_owner}/{repo.platform_repo}")
        pr = gh_repo.get_pull(pr_number)
        pr.create_review(body=summary, event=verdict)
        return f"Submitted {verdict} review on PR #{pr_number}."
    except GithubException as e:
        return f"GitHub API error submitting review: {e}"
    finally:
        gh.close()


def _gitlab_post_review_comment(
    repo: Repository, mr_iid: int, file_path: str,
    line: int, body: str, token: str | None, base_url: str | None,
) -> str:
    import gitlab
    url = base_url or "https://gitlab.com"
    gl = gitlab.Gitlab(url, private_token=token)
    try:
        project = gl.projects.get(f"{repo.platform_owner}/{repo.platform_repo}")
        mr = project.mergerequests.get(mr_iid)
        diff = mr.diffs.list()[0] if mr.diffs.list() else None
        position = {
            "base_sha": diff.base_commit_sha if diff else mr.diff_refs["base_sha"],
            "start_sha": diff.start_commit_sha if diff else mr.diff_refs["start_sha"],
            "head_sha": diff.head_commit_sha if diff else mr.diff_refs["head_sha"],
            "position_type": "text",
            "new_path": file_path,
            "new_line": line,
        }
        mr.discussions.create({"body": body, "position": position})
        return f"Posted inline comment on `{file_path}` line {line} in MR !{mr_iid}."
    except gitlab.exceptions.GitlabError as e:
        return f"GitLab API error posting comment: {e}"


def _gitlab_submit_review(
    repo: Repository, mr_iid: int, summary: str,
    token: str | None, base_url: str | None,
) -> str:
    import gitlab
    url = base_url or "https://gitlab.com"
    gl = gitlab.Gitlab(url, private_token=token)
    try:
        project = gl.projects.get(f"{repo.platform_owner}/{repo.platform_repo}")
        mr = project.mergerequests.get(mr_iid)
        mr.notes.create({"body": summary})
        return f"Posted review summary on MR !{mr_iid}."
    except gitlab.exceptions.GitlabError as e:
        return f"GitLab API error posting review: {e}"


def _azure_post_review_comment(
    repo: Repository, pr_number: int, file_path: str,
    line: int, body: str, token: str | None, base_url: str | None,
) -> str:
    from azure.devops.v7_0.git.models import (
        GitPullRequestCommentThread,
        Comment,
        CommentThreadContext,
        CommentPosition,
    )
    conn = _ado_connection(token, base_url)
    git_client = conn.clients.get_git_client()
    project, repo_name = _ado_parse(repo)

    position = CommentPosition(line=line, offset=1)
    thread_context = CommentThreadContext(
        file_path=file_path,
        right_file_start=position,
        right_file_end=position,
    )
    thread = GitPullRequestCommentThread(
        comments=[Comment(content=body)],
        thread_context=thread_context,
    )
    try:
        git_client.create_thread(thread, repo_name, pr_number, project=project)
        return f"Posted inline comment on `{file_path}` line {line} in PR #{pr_number}."
    except Exception as e:
        return f"Azure DevOps API error posting comment: {e}"


def _azure_submit_review(
    repo: Repository, pr_number: int, summary: str,
    verdict: str, token: str | None, base_url: str | None,
) -> str:
    from azure.devops.v7_0.git.models import (
        GitPullRequestCommentThread,
        Comment,
    )
    conn = _ado_connection(token, base_url)
    git_client = conn.clients.get_git_client()
    project, repo_name = _ado_parse(repo)

    _VERDICT_TO_ADO_VOTE = {"APPROVE": 10, "REQUEST_CHANGES": -10, "COMMENT": 0}
    vote = _VERDICT_TO_ADO_VOTE.get(verdict, 0)

    thread = GitPullRequestCommentThread(
        comments=[Comment(content=summary)],
        status=1,  # active
    )
    try:
        git_client.create_thread(thread, repo_name, pr_number, project=project)
    except Exception as e:
        return f"Azure DevOps API error posting review summary: {e}"

    try:
        reviewer = git_client.create_pull_request_reviewer(
            {"vote": vote}, repo_name, pr_number, reviewer_id="me", project=project,
        )
    except Exception:
        logger.debug("Could not set vote on Azure PR (may require specific permissions)")

    return f"Submitted review on PR #{pr_number} (vote={vote})."


register_tool_category(CATEGORY, DEFINITIONS, _build_code_access_tools, concurrency_safe=True)
