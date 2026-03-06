import fnmatch
import os
import re
import tempfile
import shutil
import logging
from datetime import datetime, timezone

from git import Repo as GitRepo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Repository, Commit, SSHCredential, Branch, CommitFile, FileExclusionPattern
from app.db.models.branch import commit_branches
from app.services.ssh_manager import decrypt_private_key
from app.services.identity import resolve_contributor

if __import__("typing").TYPE_CHECKING:
    from app.services.sync_logger import SyncLogger

logger = logging.getLogger(__name__)

NUMSTAT_RE = re.compile(r"^(\d+|-)\t(\d+|-)\t(.+)$")


def _is_excluded(path: str, patterns: list[str]) -> bool:
    basename = os.path.basename(path)
    for pat in patterns:
        if fnmatch.fnmatch(basename, pat) or fnmatch.fnmatch(path, pat):
            return True
    return False


def _parse_numstat(text: str, exclude_patterns: list[str] | None = None) -> tuple[int, int, int, list[tuple[str, int, int]]]:
    added = deleted = files = 0
    file_stats: list[tuple[str, int, int]] = []
    patterns = exclude_patterns or []
    for line in text.strip().split("\n"):
        m = NUMSTAT_RE.match(line.strip())
        if m:
            a, d, path = m.groups()
            if patterns and _is_excluded(path, patterns):
                continue
            fa = int(a) if a != "-" else 0
            fd = int(d) if d != "-" else 0
            added += fa
            deleted += fd
            files += 1
            file_stats.append((path, fa, fd))
    return added, deleted, files, file_stats


_SKIP_REF_PREFIXES = ("refs/pull/", "refs/merge-requests/", "refs/tags/", "refs/notes/")


async def _populate_branches(db: AsyncSession, repo: Repository, git_repo: GitRepo) -> None:
    """Discover branches and record which commits belong to each."""
    branch_refs: list[tuple[str, object]] = []
    for ref in git_repo.references:
        ref_path = str(ref)
        if ref_path == "HEAD":
            continue
        if any(ref_path.startswith(p) for p in _SKIP_REF_PREFIXES):
            continue
        if ref_path.startswith("refs/heads/"):
            branch_refs.append((ref_path.removeprefix("refs/heads/"), ref))
        elif not ref_path.startswith("refs/"):
            branch_refs.append((ref_path, ref))

    if not branch_refs:
        for ref in git_repo.references:
            ref_path = str(ref)
            if ref_path == "HEAD" or any(ref_path.startswith(p) for p in _SKIP_REF_PREFIXES):
                continue
            name = ref_path.removeprefix("refs/heads/").removeprefix("refs/remotes/origin/")
            branch_refs.append((name, ref))

    existing_branches_result = await db.execute(
        select(Branch).where(Branch.repository_id == repo.id)
    )
    existing_branches = {b.name: b for b in existing_branches_result.scalars().all()}

    all_commit_shas_result = await db.execute(
        select(Commit.sha, Commit.id).where(Commit.repository_id == repo.id)
    )
    sha_to_id = {row.sha: row.id for row in all_commit_shas_result.all()}

    existing_assoc_result = await db.execute(
        select(commit_branches.c.commit_id, commit_branches.c.branch_id)
    )
    existing_assoc = set((row.commit_id, row.branch_id) for row in existing_assoc_result.all())

    for branch_name, ref in branch_refs:
        if branch_name in existing_branches:
            branch_obj = existing_branches[branch_name]
        else:
            branch_obj = Branch(
                repository_id=repo.id,
                name=branch_name,
                is_default=(branch_name == repo.default_branch),
            )
            db.add(branch_obj)
            await db.flush()
            existing_branches[branch_name] = branch_obj

        batch = []
        try:
            for c in git_repo.iter_commits(ref):
                commit_id = sha_to_id.get(c.hexsha)
                if commit_id and (commit_id, branch_obj.id) not in existing_assoc:
                    batch.append({"commit_id": commit_id, "branch_id": branch_obj.id})
                    existing_assoc.add((commit_id, branch_obj.id))

                if len(batch) >= 1000:
                    await db.execute(commit_branches.insert(), batch)
                    batch = []
        except Exception:
            logger.warning("Skipping unresolvable ref %s in repo %s", ref, repo.name)
            continue

        if batch:
            await db.execute(commit_branches.insert(), batch)

    await db.flush()
    logger.info("Branch mapping complete: %d branches for repo %s", len(branch_refs), repo.name)


async def _load_exclusion_patterns(db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(FileExclusionPattern.pattern).where(FileExclusionPattern.enabled.is_(True))
    )
    return list(result.scalars().all())


async def clone_and_analyze(
    db: AsyncSession, repo: Repository, *, sync_log: "SyncLogger | None" = None,
) -> int:
    """Clone a repository and extract all commits. Returns count of new commits."""
    cache_dir = os.path.join(settings.repos_cache_dir, str(repo.id))
    key_file = None
    env = {}
    exclude_patterns = await _load_exclusion_patterns(db)
    if exclude_patterns and sync_log:
        sync_log.info("clone", f"Applying {len(exclude_patterns)} file exclusion patterns")

    try:
        if repo.ssh_credential_id:
            cred_result = await db.execute(select(SSHCredential).where(SSHCredential.id == repo.ssh_credential_id))
            cred = cred_result.scalar_one_or_none()
            if cred:
                key_bytes = decrypt_private_key(cred.private_key_encrypted)
                fd, key_file = tempfile.mkstemp(prefix="contributr_key_")
                os.write(fd, key_bytes)
                os.close(fd)
                os.chmod(key_file, 0o600)
                env["GIT_SSH_COMMAND"] = f"ssh -i {key_file} -o StrictHostKeyChecking=no"
                if sync_log:
                    sync_log.info("clone", "SSH key configured for authenticated clone")

        url = repo.ssh_url or repo.clone_url
        if not url:
            raise ValueError(f"Repository {repo.id} has no clone URL")

        if os.path.exists(cache_dir):
            if os.path.isdir(os.path.join(cache_dir, "objects")) and os.path.isdir(os.path.join(cache_dir, "refs")):
                if sync_log:
                    sync_log.info("clone", "Cache found — fetching latest refs...")
                git_repo = GitRepo(cache_dir)
                git_repo.git.update_environment(**env)
                git_repo.remotes.origin.fetch("+refs/*:refs/*", prune=True)
            else:
                if sync_log:
                    sync_log.warning("clone", "Corrupt cache detected, performing fresh clone")
                shutil.rmtree(cache_dir)
                os.makedirs(cache_dir, exist_ok=True)
                git_repo = GitRepo.clone_from(url, cache_dir, mirror=True, env=env)
        else:
            if sync_log:
                sync_log.info("clone", f"Cloning {url} (mirror)...")
            os.makedirs(cache_dir, exist_ok=True)
            git_repo = GitRepo.clone_from(url, cache_dir, mirror=True, env=env)

        if sync_log:
            sync_log.info("clone", "Repository fetched successfully")

        existing_shas_result = await db.execute(
            select(Commit.sha).where(Commit.repository_id == repo.id)
        )
        existing_shas = set(existing_shas_result.scalars().all())
        if sync_log:
            sync_log.info("commits", f"{len(existing_shas)} existing commits in database, scanning for new ones...")

        new_count = 0
        for git_commit in git_repo.iter_commits("--all"):
            if git_commit.hexsha in existing_shas:
                continue

            is_merge = len(git_commit.parents) > 1

            try:
                numstat_output = git_repo.git.diff(
                    git_commit.hexsha + "~1", git_commit.hexsha, numstat=True
                )
            except Exception:
                numstat_output = ""

            added, deleted, files, file_stats = _parse_numstat(numstat_output, exclude_patterns) if numstat_output else (0, 0, 0, [])

            author_email = git_commit.author.email or "unknown@unknown"
            author_name = git_commit.author.name or "Unknown"
            contributor = await resolve_contributor(db, author_name, author_email)

            commit = Commit(
                repository_id=repo.id,
                contributor_id=contributor.id,
                sha=git_commit.hexsha,
                message=(git_commit.message or "")[:4096],
                is_merge=is_merge,
                lines_added=added,
                lines_deleted=deleted,
                files_changed=files,
                authored_at=datetime.fromtimestamp(git_commit.authored_date, tz=timezone.utc),
                committed_at=datetime.fromtimestamp(git_commit.committed_date, tz=timezone.utc),
            )
            db.add(commit)
            await db.flush()

            if not is_merge:
                for fpath, fa, fd in file_stats:
                    db.add(CommitFile(
                        commit_id=commit.id,
                        file_path=fpath[:1024],
                        lines_added=fa,
                        lines_deleted=fd,
                    ))

            new_count += 1

            if new_count % 500 == 0:
                await db.flush()
                if sync_log:
                    sync_log.info("commits", f"Processed {new_count} new commits so far...")

        await db.flush()

        if sync_log:
            sync_log.info("branches", f"Mapping branches for {repo.name}...")
        await _populate_branches(db, repo, git_repo)
        if sync_log:
            sync_log.info("branches", "Branch mapping complete")

        return new_count

    finally:
        if key_file and os.path.exists(key_file):
            os.unlink(key_file)
