"""Git operations for Architecture Decision Records.

Uses the existing bare-mirror infrastructure and platform credentials
to read/write ADR files, create branches, commits, and PRs.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Repository
from app.db.models.adr import Adr, AdrRepository as AdrRepoConfig, AdrStatus
from app.db.models.platform_credential import PlatformCredential
from app.db.models.repository import Platform

logger = logging.getLogger(__name__)

GIT_TIMEOUT = 30


def _open_git_repo(path: str):
    from git import Repo as GitRepo
    return GitRepo(path)


async def _get_platform_token(db: AsyncSession, platform: Platform) -> tuple[str | None, str | None]:
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


async def sync_adrs_from_repo(db: AsyncSession, project_id) -> int:
    """Scan the ADR directory in the configured repo and reconcile with DB.

    The repository is the source of truth for committed ADRs:
    - Files in repo but not DB → create
    - Files in both → update content/title/status from repo
    - DB ADRs with file_path that no longer exist in repo → delete
    - DB ADRs without file_path (never committed) → leave untouched
    """
    config = (await db.execute(
        select(AdrRepoConfig).where(AdrRepoConfig.project_id == project_id)
    )).scalar_one_or_none()
    if not config or not config.repository_id:
        return 0

    repo = (await db.execute(
        select(Repository).where(Repository.id == config.repository_id)
    )).scalar_one_or_none()
    if not repo:
        return 0

    bare_path = os.path.join(settings.repos_cache_dir, str(repo.id))
    if not os.path.isdir(bare_path):
        return 0

    git_repo = _open_git_repo(bare_path)

    token, base_url = await _get_platform_token(db, repo.platform)
    if token:
        remote_url = _build_remote_url(repo, token, base_url)
        try:
            git_repo.git.fetch(remote_url, kill_after_timeout=GIT_TIMEOUT)
        except Exception as e:
            logger.warning("ADR sync fetch failed: %s", e)
    else:
        logger.warning("ADR sync: no platform credentials, using local mirror only")

    default_branch = repo.default_branch or "main"
    try:
        ref = git_repo.git.rev_parse(f"refs/heads/{default_branch}", kill_after_timeout=GIT_TIMEOUT)
    except Exception:
        try:
            ref = git_repo.git.rev_parse("HEAD", kill_after_timeout=GIT_TIMEOUT)
        except Exception:
            return 0

    adr_dir = config.directory_path or "docs/adr"

    repo_files: set[str] = set()
    try:
        listing = git_repo.git.ls_tree("--name-only", f"{ref}:{adr_dir}", kill_after_timeout=GIT_TIMEOUT)
        for fname in listing.strip().split("\n"):
            if fname.endswith(".md"):
                repo_files.add(f"{adr_dir}/{fname}")
    except Exception:
        pass

    existing = (await db.execute(
        select(Adr).where(Adr.project_id == project_id)
    )).scalars().all()
    existing_by_path = {a.file_path: a for a in existing if a.file_path}

    admin_result = await db.execute(select(__import__("app.db.models", fromlist=["User"]).User.id).limit(1))
    admin_id = admin_result.scalar()

    synced = 0

    for file_path in repo_files:
        fname = file_path.rsplit("/", 1)[-1]
        try:
            content = git_repo.git.show(f"{ref}:{file_path}", kill_after_timeout=GIT_TIMEOUT)
        except Exception:
            continue

        title, status, adr_number = _parse_adr_metadata(content, fname)

        if file_path in existing_by_path:
            adr = existing_by_path[file_path]
            adr.content = content
            adr.title = title or adr.title
            if status:
                adr.status = status
            adr.updated_at = datetime.now(timezone.utc)
        else:
            if adr_number is None:
                adr_number = config.next_number
                config.next_number += 1
            adr = Adr(
                project_id=project_id,
                adr_number=adr_number,
                title=title or fname.replace(".md", ""),
                slug=Adr.make_slug(title or fname.replace(".md", "")),
                status=status or AdrStatus.PROPOSED,
                content=content,
                file_path=file_path,
                created_by_id=admin_id,
            )
            db.add(adr)

        synced += 1

    removed = 0
    for path, adr in existing_by_path.items():
        if path not in repo_files:
            await db.delete(adr)
            removed += 1

    if removed:
        logger.info("ADR sync: removed %d ADR(s) no longer in repo", removed)

    await db.flush()
    return synced


def _parse_adr_metadata(content: str, filename: str) -> tuple[str | None, AdrStatus | None, int | None]:
    """Extract title, status, and number from an ADR markdown file."""
    title = None
    status = None
    number = None

    num_match = re.match(r"(\d+)", filename)
    if num_match:
        number = int(num_match.group(1))

    for line in content.split("\n")[:20]:
        line = line.strip()
        if line.startswith("# ") and not title:
            t = line[2:].strip()
            num_prefix = re.match(r"\d+\.\s*", t)
            if num_prefix:
                t = t[num_prefix.end():]
                if number is None:
                    number = int(num_prefix.group().strip(". "))
            title = t

        status_match = re.match(r"(?:\*{0,2})?[Ss]tatus:?\s*(?:\*{0,2})?\s*(\w+)", line.lstrip("- "))
        if status_match:
            raw = status_match.group(1).lower()
            status_map = {
                "proposed": AdrStatus.PROPOSED,
                "accepted": AdrStatus.ACCEPTED,
                "deprecated": AdrStatus.DEPRECATED,
                "superseded": AdrStatus.SUPERSEDED,
                "rejected": AdrStatus.REJECTED,
            }
            status = status_map.get(raw)

    return title, status, number


async def write_adr_to_repo(db: AsyncSession, adr: Adr) -> tuple[str, str]:
    """Write an ADR to a new branch and commit. Returns (branch_name, sha)."""
    config = (await db.execute(
        select(AdrRepoConfig).where(AdrRepoConfig.project_id == adr.project_id)
    )).scalar_one_or_none()
    if not config or not config.repository_id:
        raise RuntimeError("ADR repository not configured for this project.")

    repo = (await db.execute(
        select(Repository).where(Repository.id == config.repository_id)
    )).scalar_one_or_none()
    if not repo:
        raise RuntimeError("Repository not found.")

    bare_path = os.path.join(settings.repos_cache_dir, str(repo.id))
    if not os.path.isdir(bare_path):
        raise RuntimeError("Repository not synced locally.")

    adr_dir = config.directory_path or "docs/adr"
    slug = Adr.make_slug(adr.title)
    file_name = config.naming_convention.format(number=adr.adr_number, slug=slug)
    file_path = f"{adr_dir}/{file_name}"

    branch_name = f"adr/{adr.adr_number}-{slug}"

    default_branch = repo.default_branch or "main"

    bare_repo = _open_git_repo(bare_path)
    try:
        bare_repo.git.rev_parse(f"refs/heads/{default_branch}")
        needs_default_branch = False
    except Exception:
        needs_default_branch = True

    work_dir = tempfile.mkdtemp(prefix="adr_")
    try:
        from git import Repo as GitRepo, Actor
        author = Actor("Contributr", "contributr@noreply.local")
        work_repo = GitRepo.clone_from(bare_path, work_dir)

        if needs_default_branch:
            if len(work_repo.heads) == 0:
                work_repo.git.checkout("--orphan", default_branch)
            else:
                work_repo.git.checkout("-b", default_branch)
            readme_path = os.path.join(work_dir, "README.md")
            if not os.path.exists(readme_path):
                with open(readme_path, "w") as f:
                    f.write(f"# {repo.name}\n\nArchitecture Decision Records\n")
                work_repo.index.add(["README.md"])
                work_repo.index.commit(
                    "Initial commit", author=author, committer=author,
                )

        try:
            work_repo.git.checkout("-b", branch_name)
        except Exception:
            work_repo.git.checkout(branch_name)

        full_path = os.path.join(work_dir, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(adr.content)

        work_repo.index.add([file_path])
        commit = work_repo.index.commit(
            f"ADR-{adr.adr_number}: {adr.title}",
            author=author,
            committer=author,
        )

        if needs_default_branch:
            bare_repo.git.fetch(
                work_dir,
                f"+refs/heads/{default_branch}:refs/heads/{default_branch}",
                kill_after_timeout=GIT_TIMEOUT,
            )
        bare_repo.git.fetch(
            work_dir,
            f"+refs/heads/{branch_name}:refs/heads/{branch_name}",
            kill_after_timeout=GIT_TIMEOUT,
        )

        adr.file_path = file_path
        adr.last_committed_sha = str(commit.hexsha)
        adr.updated_at = datetime.now(timezone.utc)

        return branch_name, str(commit.hexsha)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


async def create_adr_pr(db: AsyncSession, adr: Adr, branch: str) -> str:
    """Create a PR on the platform for the ADR branch. Returns the PR URL."""
    config = (await db.execute(
        select(AdrRepoConfig).where(AdrRepoConfig.project_id == adr.project_id)
    )).scalar_one_or_none()
    if not config or not config.repository_id:
        raise RuntimeError("ADR repository not configured.")

    repo = (await db.execute(
        select(Repository).where(Repository.id == config.repository_id)
    )).scalar_one_or_none()
    if not repo:
        raise RuntimeError("Repository not found.")

    if not repo.default_branch:
        raise RuntimeError("Repository has no default branch configured. Check repository settings.")

    token, base_url = await _get_platform_token(db, repo.platform)
    if not token:
        raise RuntimeError(f"No platform credentials configured for {repo.platform.value}.")

    pr_title = f"ADR-{adr.adr_number}: {adr.title}"
    pr_body = f"Architecture Decision Record: {adr.title}\n\nStatus: {adr.status.value}"

    bare_path = os.path.join(settings.repos_cache_dir, str(repo.id))
    bare_repo = _open_git_repo(bare_path)
    remote_url = _build_remote_url(repo, token, base_url)

    try:
        bare_repo.git.push(
            remote_url,
            f"refs/heads/{repo.default_branch}:refs/heads/{repo.default_branch}",
            kill_after_timeout=GIT_TIMEOUT,
        )
    except Exception:
        pass

    try:
        bare_repo.git.push(
            remote_url,
            f"+refs/heads/{branch}:refs/heads/{branch}",
            kill_after_timeout=GIT_TIMEOUT,
        )
    except Exception as e:
        raise RuntimeError(f"Failed to push branch '{branch}' to remote: {e}")

    if repo.platform == Platform.GITHUB:
        from github import Github
        gh = Github(token)
        try:
            gh_repo = gh.get_repo(f"{repo.platform_owner}/{repo.platform_repo}")
            pr = gh_repo.create_pull(title=pr_title, body=pr_body, head=branch, base=repo.default_branch)
            pr_url = pr.html_url
        finally:
            gh.close()
    elif repo.platform == Platform.GITLAB:
        import gitlab as gl_lib
        url = base_url or "https://gitlab.com"
        gl = gl_lib.Gitlab(url, private_token=token)
        project = gl.projects.get(f"{repo.platform_owner}/{repo.platform_repo}")
        mr = project.mergerequests.create({
            "source_branch": branch,
            "target_branch": repo.default_branch,
            "title": pr_title,
            "description": pr_body,
        })
        pr_url = mr.web_url
    elif repo.platform == Platform.AZURE:
        from azure.devops.connection import Connection
        from msrest.authentication import BasicAuthentication
        conn = Connection(base_url=base_url, creds=BasicAuthentication("", token))
        git_client = conn.clients.get_git_client()
        owner = repo.platform_owner or ""
        parts = owner.split("/", 1)
        project_name = parts[1] if len(parts) > 1 else parts[0]
        pr_obj = git_client.create_pull_request(
            {
                "source_ref_name": f"refs/heads/{branch}",
                "target_ref_name": f"refs/heads/{repo.default_branch}",
                "title": pr_title,
                "description": pr_body,
            },
            repo.platform_repo,
            project=project_name,
        )
        from urllib.parse import quote
        org = base_url.rstrip("/")
        pr_url = f"{org}/{quote(project_name, safe='')}/_git/{repo.platform_repo}/pullrequest/{pr_obj.pull_request_id}"
    else:
        raise RuntimeError(f"Unsupported platform: {repo.platform.value}")

    adr.pr_url = pr_url
    adr.updated_at = datetime.now(timezone.utc)
    return pr_url


async def merge_adr_pr(db: AsyncSession, adr: Adr) -> bool:
    """Attempt to merge the ADR's open PR. Returns True if successful."""
    if not adr.pr_url:
        raise RuntimeError("No PR URL set on this ADR.")

    config = (await db.execute(
        select(AdrRepoConfig).where(AdrRepoConfig.project_id == adr.project_id)
    )).scalar_one_or_none()
    if not config or not config.repository_id:
        raise RuntimeError("ADR repository not configured.")

    repo = (await db.execute(
        select(Repository).where(Repository.id == config.repository_id)
    )).scalar_one_or_none()
    if not repo:
        raise RuntimeError("Repository not found.")

    token, base_url = await _get_platform_token(db, repo.platform)
    if not token:
        raise RuntimeError("No platform credentials configured.")

    if repo.platform == Platform.GITHUB:
        from github import Github
        pr_number = int(adr.pr_url.rstrip("/").split("/")[-1])
        gh = Github(token)
        try:
            gh_repo = gh.get_repo(f"{repo.platform_owner}/{repo.platform_repo}")
            pr = gh_repo.get_pull(pr_number)
            pr.merge()
        finally:
            gh.close()
    elif repo.platform == Platform.GITLAB:
        import gitlab as gl_lib
        mr_iid = int(adr.pr_url.rstrip("/").split("/")[-1])
        url = base_url or "https://gitlab.com"
        gl = gl_lib.Gitlab(url, private_token=token)
        project = gl.projects.get(f"{repo.platform_owner}/{repo.platform_repo}")
        mr = project.mergerequests.get(mr_iid)
        mr.merge()
    elif repo.platform == Platform.AZURE:
        from azure.devops.connection import Connection
        from msrest.authentication import BasicAuthentication
        pr_id = int(adr.pr_url.rstrip("/").split("/")[-1])
        conn = Connection(base_url=base_url, creds=BasicAuthentication("", token))
        git_client = conn.clients.get_git_client()
        owner = repo.platform_owner or ""
        parts = owner.split("/", 1)
        project_name = parts[1] if len(parts) > 1 else parts[0]
        pr_obj = git_client.get_pull_request_by_id(pr_id, project=project_name)
        git_client.update_pull_request(
            {"status": "completed", "last_merge_source_commit": pr_obj.last_merge_source_commit},
            repo.platform_repo,
            pr_id,
            project=project_name,
        )

    adr.updated_at = datetime.now(timezone.utc)
    return True


def _build_remote_url(repo: Repository, token: str, base_url: str | None) -> str:
    from urllib.parse import quote

    if repo.platform == Platform.GITHUB:
        return f"https://x-access-token:{token}@github.com/{repo.platform_owner}/{repo.platform_repo}.git"
    elif repo.platform == Platform.GITLAB:
        host = (base_url or "https://gitlab.com").replace("https://", "").replace("http://", "")
        return f"https://oauth2:{token}@{host}/{repo.platform_owner}/{repo.platform_repo}.git"
    elif repo.platform == Platform.AZURE:
        org_url = (base_url or "").rstrip("/")
        org_host = org_url.replace("https://", "").replace("http://", "")
        owner = repo.platform_owner or ""
        parts = owner.split("/", 1)
        org_name = parts[0]
        project_name = parts[1] if len(parts) > 1 else parts[0]
        project_enc = quote(project_name, safe="")
        repo_enc = quote(repo.platform_repo, safe="")
        if org_host.endswith(f"/{org_name}"):
            return f"https://{token}@{org_host}/{project_enc}/_git/{repo_enc}"
        return f"https://{token}@{org_host}/{quote(org_name, safe='')}/{project_enc}/_git/{repo_enc}"
    return ""
