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
from app.db.models import Repository, Commit, SSHCredential, Branch
from app.db.models.branch import commit_branches
from app.services.ssh_manager import decrypt_private_key
from app.services.identity import resolve_contributor

logger = logging.getLogger(__name__)

NUMSTAT_RE = re.compile(r"^(\d+|-)\t(\d+|-)\t(.+)$")


def _parse_numstat(text: str) -> tuple[int, int, int]:
    added = deleted = files = 0
    for line in text.strip().split("\n"):
        m = NUMSTAT_RE.match(line.strip())
        if m:
            a, d, _ = m.groups()
            if a != "-":
                added += int(a)
            if d != "-":
                deleted += int(d)
            files += 1
    return added, deleted, files


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


async def clone_and_analyze(db: AsyncSession, repo: Repository) -> int:
    """Clone a repository and extract all commits. Returns count of new commits."""
    cache_dir = os.path.join(settings.repos_cache_dir, str(repo.id))
    key_file = None
    env = {}

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

        url = repo.ssh_url or repo.clone_url
        if not url:
            raise ValueError(f"Repository {repo.id} has no clone URL")

        if os.path.exists(cache_dir):
            if os.path.isdir(os.path.join(cache_dir, "objects")) and os.path.isdir(os.path.join(cache_dir, "refs")):
                git_repo = GitRepo(cache_dir)
                git_repo.git.update_environment(**env)
                git_repo.remotes.origin.fetch("+refs/*:refs/*", prune=True)
            else:
                logger.warning("Corrupt cache dir for repo %s, re-cloning", repo.id)
                shutil.rmtree(cache_dir)
                os.makedirs(cache_dir, exist_ok=True)
                git_repo = GitRepo.clone_from(url, cache_dir, mirror=True, env=env)
        else:
            os.makedirs(cache_dir, exist_ok=True)
            git_repo = GitRepo.clone_from(url, cache_dir, mirror=True, env=env)

        existing_shas_result = await db.execute(
            select(Commit.sha).where(Commit.repository_id == repo.id)
        )
        existing_shas = set(existing_shas_result.scalars().all())

        new_count = 0
        for git_commit in git_repo.iter_commits("--all"):
            if git_commit.hexsha in existing_shas:
                continue

            try:
                numstat_output = git_repo.git.diff(
                    git_commit.hexsha + "~1", git_commit.hexsha, numstat=True
                )
            except Exception:
                numstat_output = ""

            added, deleted, files = _parse_numstat(numstat_output) if numstat_output else (0, 0, 0)

            author_email = git_commit.author.email or "unknown@unknown"
            author_name = git_commit.author.name or "Unknown"
            contributor = await resolve_contributor(db, author_name, author_email)

            commit = Commit(
                repository_id=repo.id,
                contributor_id=contributor.id,
                sha=git_commit.hexsha,
                message=(git_commit.message or "")[:4096],
                is_merge=len(git_commit.parents) > 1,
                lines_added=added,
                lines_deleted=deleted,
                files_changed=files,
                authored_at=datetime.fromtimestamp(git_commit.authored_date, tz=timezone.utc),
                committed_at=datetime.fromtimestamp(git_commit.committed_date, tz=timezone.utc),
            )
            db.add(commit)
            new_count += 1

            if new_count % 500 == 0:
                await db.flush()

        await db.flush()

        await _populate_branches(db, repo, git_repo)

        return new_count

    finally:
        if key_file and os.path.exists(key_file):
            os.unlink(key_file)
