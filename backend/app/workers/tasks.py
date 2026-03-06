import asyncio
import uuid
import logging
from datetime import datetime, timezone

from celery.signals import worker_ready
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.config import settings
from app.workers.celery_app import celery
from app.db.base import Base
from app.db.models import Repository, SyncJob, PlatformCredential
from app.db.models.sync_job import SyncStatus
from app.db.models.repository import Platform
from app.services.git_analyzer import clone_and_analyze
from app.services.github_client import fetch_github_prs
from app.services.gitlab_client import fetch_gitlab_mrs
from app.services.azure_client import fetch_azure_prs
from app.services.metrics import rebuild_daily_stats
from app.services.sync_logger import SyncLogger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _get_session() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _cleanup_orphaned_running_jobs() -> None:
    Session = _get_session()
    async with Session() as db:
        result = await db.execute(
            select(SyncJob).where(SyncJob.status == SyncStatus.RUNNING)
        )
        orphaned = result.scalars().all()
        if not orphaned:
            return
        now = datetime.now(timezone.utc)
        for job in orphaned:
            job.status = SyncStatus.FAILED
            job.error_message = "Worker restarted; task was interrupted"
            job.finished_at = now
            logger.info("Cleaned up orphaned RUNNING job %s on worker startup", job.id)
        await db.commit()


@worker_ready.connect
def _on_worker_ready(sender, **kwargs):
    try:
        asyncio.run(_cleanup_orphaned_running_jobs())
    except Exception:
        logger.exception("Failed to clean up orphaned jobs on startup")


class SyncCancelled(Exception):
    pass


async def _check_cancelled(db: AsyncSession, job_id: uuid.UUID) -> None:
    await db.refresh(await db.get(SyncJob, job_id))
    job = await db.get(SyncJob, job_id)
    if job and job.status == SyncStatus.CANCELLED:
        raise SyncCancelled()


async def _resolve_platform_token(
    db: AsyncSession, platform: Platform | None = None,
) -> tuple[str | None, str | None]:
    """Auto-discover a platform credential matching the repo's platform."""
    from app.api.platform_credentials import decrypt_token

    if not platform:
        return None, None

    result = await db.execute(
        select(PlatformCredential).where(
            PlatformCredential.platform == platform
        ).order_by(PlatformCredential.created_at.desc()).limit(1)
    )
    cred = result.scalar_one_or_none()

    if not cred:
        logger.warning("No platform credential found for %s — PR/review data will not be fetched", platform.value)
        return None, None

    logger.info("Auto-matched credential '%s' for platform %s", cred.name, platform.value)

    try:
        token = decrypt_token(cred.token_encrypted)
    except Exception as e:
        logger.error("Failed to decrypt platform credential '%s': %s", cred.name, e)
        return None, None

    return token, cred.base_url


def _derive_azure_org_url(repo: Repository) -> str | None:
    """Derive Azure DevOps org URL from platform_owner (format: 'org/project')."""
    owner = repo.platform_owner or ""
    org = owner.split("/", 1)[0] if "/" in owner else owner
    if org:
        return f"https://dev.azure.com/{org}"
    return None


async def _run_sync(repo_id: str, job_id: str) -> None:
    slog = SyncLogger(job_id)
    slog.info("init", f"Starting sync for repo={repo_id}")
    Session = _get_session()
    async with Session() as db:
        repo = await db.get(Repository, uuid.UUID(repo_id))
        job = await db.get(SyncJob, uuid.UUID(job_id))
        if not repo or not job:
            slog.error("init", f"Repo or job not found: repo={repo_id} job={job_id}")
            slog.fail("Repo or job not found")
            slog.close()
            return

        if job.status == SyncStatus.CANCELLED:
            slog.cancel()
            slog.close()
            return

        try:
            job.status = SyncStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            await db.commit()
            slog.info("clone", f"Cloning/fetching {repo.name} ({repo.ssh_url or repo.clone_url})")

            new_commits = await clone_and_analyze(db, repo, sync_log=slog)
            slog.info("commits", f"Extracted {new_commits} new commits from {repo.name}")

            await _check_cancelled(db, uuid.UUID(job_id))

            slog.info("prs", f"Resolving platform credentials for {repo.platform.value if repo.platform else 'unknown'}...")
            token, base_url = await _resolve_platform_token(db, platform=repo.platform)

            if repo.platform == Platform.GITHUB:
                slog.info("prs", f"Fetching PRs from GitHub ({repo.platform_owner}/{repo.platform_repo})...")
                pr_count = await fetch_github_prs(db, repo, token=token, sync_log=slog)
                slog.info("prs", f"Fetched {pr_count} PRs from GitHub")
            elif repo.platform == Platform.GITLAB:
                gl_url = base_url or "https://gitlab.com"
                slog.info("prs", f"Fetching MRs from GitLab ({repo.platform_owner}/{repo.platform_repo})...")
                mr_count = await fetch_gitlab_mrs(db, repo, token=token, url=gl_url, sync_log=slog)
                slog.info("prs", f"Fetched {mr_count} MRs from GitLab")
            elif repo.platform == Platform.AZURE:
                org_url = base_url or _derive_azure_org_url(repo)
                if not org_url or not token:
                    slog.warning("prs", f"Skipping Azure PR fetch — org_url={'set' if org_url else 'MISSING'}, token={'present' if token else 'MISSING'}")
                else:
                    slog.info("prs", f"Fetching PRs from Azure DevOps ({repo.platform_owner}/{repo.platform_repo})...")
                    pr_count = await fetch_azure_prs(db, repo, org_url=org_url, token=token, sync_log=slog)
                    slog.info("prs", f"Fetched {pr_count} PRs from Azure DevOps")

            await _check_cancelled(db, uuid.UUID(job_id))

            slog.info("stats", f"Rebuilding daily contributor stats for {repo.name}...")
            await rebuild_daily_stats(db, repo.id)
            slog.info("stats", "Daily stats rebuilt")

            await _check_cancelled(db, uuid.UUID(job_id))

            slog.info("assigning", "Assigning contributors to project...")
            from app.db.models.project import project_contributors
            from app.db.models import Commit
            contributor_ids = (
                await db.execute(
                    select(Commit.contributor_id)
                    .where(Commit.repository_id == repo.id)
                    .distinct()
                )
            ).scalars().all()

            assigned = 0
            for cid in contributor_ids:
                if cid is None:
                    continue
                existing = await db.execute(
                    select(project_contributors).where(
                        project_contributors.c.project_id == repo.project_id,
                        project_contributors.c.contributor_id == cid,
                    )
                )
                if not existing.first():
                    await db.execute(
                        project_contributors.insert().values(
                            project_id=repo.project_id, contributor_id=cid
                        )
                    )
                    assigned += 1
            slog.info("assigning", f"Linked {assigned} new contributors to project")

            repo.last_synced_at = datetime.now(timezone.utc)
            job.status = SyncStatus.COMPLETED
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
            slog.complete()

        except SyncCancelled:
            job.status = SyncStatus.CANCELLED
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
            slog.cancel()

        except Exception as e:
            logger.exception("Sync FAILED for repo %s: %s", repo_id, e)
            job.status = SyncStatus.FAILED
            job.error_message = str(e)[:2000]
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
            slog.fail(str(e)[:500])

        finally:
            slog.close()


async def _mark_job_failed(job_id: str, error: str) -> None:
    Session = _get_session()
    async with Session() as db:
        job = await db.get(SyncJob, uuid.UUID(job_id))
        if job and job.status in (SyncStatus.QUEUED, SyncStatus.RUNNING):
            job.status = SyncStatus.FAILED
            job.error_message = f"Task failed unexpectedly: {error[:2000]}"
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info("Marked stale job %s as FAILED via on_failure hook", job_id)


class _SyncTask(celery.Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        if args and len(args) >= 2:
            try:
                asyncio.run(_mark_job_failed(args[1], str(exc)))
            except Exception:
                logger.exception("on_failure hook could not mark job as failed")


@celery.task(name="sync_repository", base=_SyncTask)
def sync_repository(repo_id: str, job_id: str) -> dict:
    logger.info("Celery task sync_repository called: repo=%s job=%s", repo_id, job_id)
    asyncio.run(_run_sync(repo_id, job_id))
    return {"repo_id": repo_id, "job_id": job_id}
