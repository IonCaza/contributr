import asyncio
import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.workers.celery_app import celery
from app.db.base import Base
from app.db.models import Repository, SyncJob
from app.db.models.sync_job import SyncStatus
from app.db.models.repository import Platform
from app.services.git_analyzer import clone_and_analyze
from app.services.github_client import fetch_github_prs
from app.services.gitlab_client import fetch_gitlab_mrs
from app.services.metrics import rebuild_daily_stats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _get_session() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class SyncCancelled(Exception):
    pass


async def _check_cancelled(db: AsyncSession, job_id: uuid.UUID) -> None:
    await db.refresh(await db.get(SyncJob, job_id))
    job = await db.get(SyncJob, job_id)
    if job and job.status == SyncStatus.CANCELLED:
        raise SyncCancelled()


async def _run_sync(repo_id: str, job_id: str) -> None:
    logger.info("Starting sync for repo=%s job=%s", repo_id, job_id)
    Session = _get_session()
    async with Session() as db:
        repo = await db.get(Repository, uuid.UUID(repo_id))
        job = await db.get(SyncJob, uuid.UUID(job_id))
        if not repo or not job:
            logger.error("Repo or job not found: repo=%s job=%s", repo_id, job_id)
            return

        if job.status == SyncStatus.CANCELLED:
            logger.info("Job %s already cancelled before start", job_id)
            return

        try:
            job.status = SyncStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info("Job %s marked RUNNING, cloning repo %s (%s)", job_id, repo.name, repo.ssh_url or repo.clone_url)

            new_commits = await clone_and_analyze(db, repo)
            logger.info("Repo %s: %d new commits extracted", repo.name, new_commits)

            await _check_cancelled(db, uuid.UUID(job_id))

            if repo.platform == Platform.GITHUB:
                pr_count = await fetch_github_prs(db, repo)
                logger.info("Fetched %d PRs from GitHub", pr_count)
            elif repo.platform == Platform.GITLAB:
                mr_count = await fetch_gitlab_mrs(db, repo)
                logger.info("Fetched %d MRs from GitLab", mr_count)

            await _check_cancelled(db, uuid.UUID(job_id))

            logger.info("Rebuilding daily stats for repo %s", repo.name)
            await rebuild_daily_stats(db, repo.id)

            await _check_cancelled(db, uuid.UUID(job_id))

            from app.db.models.project import project_contributors
            from app.db.models import Commit
            contributor_ids = (
                await db.execute(
                    select(Commit.contributor_id)
                    .where(Commit.repository_id == repo.id)
                    .distinct()
                )
            ).scalars().all()

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

            repo.last_synced_at = datetime.now(timezone.utc)
            job.status = SyncStatus.COMPLETED
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info("Sync COMPLETED for repo %s", repo.name)

        except SyncCancelled:
            logger.info("Sync CANCELLED for repo %s (job %s)", repo_id, job_id)
            job.status = SyncStatus.CANCELLED
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()

        except Exception as e:
            logger.exception("Sync FAILED for repo %s: %s", repo_id, e)
            job.status = SyncStatus.FAILED
            job.error_message = str(e)[:2000]
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()


@celery.task(name="sync_repository")
def sync_repository(repo_id: str, job_id: str) -> dict:
    logger.info("Celery task sync_repository called: repo=%s job=%s", repo_id, job_id)
    asyncio.run(_run_sync(repo_id, job_id))
    return {"repo_id": repo_id, "job_id": job_id}
