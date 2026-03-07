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
from app.db.models import Repository, SyncJob, PlatformCredential, Project, Commit
from app.db.models.sync_job import SyncStatus
from app.db.models.repository import Platform
from app.services.git_analyzer import clone_and_analyze
from app.services.github_client import fetch_github_prs
from app.services.gitlab_client import fetch_gitlab_mrs
from app.services.azure_client import fetch_azure_prs
from app.services.azure_workitems_client import (
    fetch_ado_teams, fetch_ado_iterations, fetch_ado_work_items,
    rebuild_daily_delivery_stats, _parse_ado_project,
)
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

            slog.info("wi_links", "Scanning commit messages for work item references...")
            from app.db.models.work_item import WorkItem
            from app.db.models.work_item_commit import WorkItemCommit
            import re as _re
            _WI_REF_RE = _re.compile(r'(?:AB)?#(\d{2,})')
            _link_commits = (
                await db.execute(
                    select(Commit).where(Commit.repository_id == repo.id)
                )
            ).scalars().all()
            _wi_ids_result = await db.execute(
                select(WorkItem.platform_work_item_id, WorkItem.id)
                .where(WorkItem.project_id == repo.project_id)
            )
            _wi_map = {row[0]: row[1] for row in _wi_ids_result.all()}
            _wi_link_count = 0
            for c in _link_commits:
                if not c.message:
                    continue
                refs = _WI_REF_RE.findall(c.message)
                for ref_str in refs:
                    ref_id = int(ref_str)
                    wi_uuid = _wi_map.get(ref_id)
                    if not wi_uuid:
                        continue
                    existing_link = await db.execute(
                        select(WorkItemCommit).where(
                            WorkItemCommit.work_item_id == wi_uuid,
                            WorkItemCommit.commit_id == c.id,
                        )
                    )
                    if not existing_link.scalar_one_or_none():
                        db.add(WorkItemCommit(
                            work_item_id=wi_uuid,
                            commit_id=c.id,
                            link_type="message_ref",
                        ))
                        _wi_link_count += 1
            if _wi_link_count:
                await db.flush()
            slog.info("wi_links", f"Found {_wi_link_count} commit-to-work-item links from messages")

            await _check_cancelled(db, uuid.UUID(job_id))

            slog.info("assigning", "Assigning contributors to project...")
            from app.db.models.project import project_contributors
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


async def _run_delivery_sync(project_id: str, job_id: str | None = None) -> dict:
    """Sync teams, iterations, and work items from Azure DevOps for a project."""
    slog = SyncLogger(f"delivery-{project_id}")
    slog.info("init", f"Starting delivery sync for project={project_id}")
    Session = _get_session()
    async with Session() as db:
        from sqlalchemy.orm import selectinload
        from app.db.models.delivery_sync_job import DeliverySyncJob

        job: DeliverySyncJob | None = None
        if job_id:
            r = await db.execute(select(DeliverySyncJob).where(DeliverySyncJob.id == uuid.UUID(job_id)))
            job = r.scalar_one_or_none()
            if job:
                job.status = SyncStatus.RUNNING
                job.started_at = datetime.now(timezone.utc)
                await db.commit()

        async def _fail_job(msg: str):
            if job:
                job.status = SyncStatus.FAILED
                job.finished_at = datetime.now(timezone.utc)
                job.error_message = msg[:2000]
                await db.commit()

        result = await db.execute(
            select(Project)
            .options(selectinload(Project.repositories))
            .where(Project.id == uuid.UUID(project_id))
        )
        project = result.scalar_one_or_none()
        if not project:
            slog.error("init", f"Project not found: {project_id}")
            slog.close()
            await _fail_job("Project not found")
            return {"error": "Project not found"}

        ado_project_name = _parse_ado_project(project)
        if not ado_project_name:
            slog.error("init", "No Azure DevOps repository found in project — cannot sync delivery data")
            slog.close()
            await _fail_job("No Azure repo in project")
            return {"error": "No Azure repo in project"}

        token, base_url = await _resolve_platform_token(db, Platform.AZURE)
        if not token:
            slog.error("init", "No Azure DevOps credential found")
            slog.close()
            await _fail_job("No Azure credential")
            return {"error": "No Azure credential"}

        azure_repo = next(
            (r for r in project.repositories if r.platform and r.platform.value == "azure"),
            None,
        )
        org_url = base_url or (_derive_azure_org_url(azure_repo) if azure_repo else None)
        if not org_url:
            slog.error("init", "Cannot determine Azure DevOps org URL")
            slog.close()
            await _fail_job("No org URL")
            return {"error": "No org URL"}

        try:
            slog.info("teams", "Fetching teams from Azure DevOps...")
            teams_count = await fetch_ado_teams(db, project, org_url, token, ado_project_name, slog)
            slog.info("teams", f"Synced {teams_count} teams")

            slog.info("iterations", "Fetching iterations from Azure DevOps...")
            iter_count = await fetch_ado_iterations(db, project, org_url, token, ado_project_name, slog)
            slog.info("iterations", f"Synced {iter_count} iterations")

            slog.info("work_items", "Fetching work items from Azure DevOps...")
            wi_count = await fetch_ado_work_items(db, project, org_url, token, ado_project_name, slog)
            slog.info("work_items", f"Synced {wi_count} work items")

            slog.info("stats", "Rebuilding daily delivery stats...")
            await rebuild_daily_delivery_stats(db, project.id)
            slog.info("stats", "Daily delivery stats rebuilt")

            if job:
                job.status = SyncStatus.COMPLETED
                job.finished_at = datetime.now(timezone.utc)

            await db.commit()
            slog.complete()
            return {"teams": teams_count, "iterations": iter_count, "work_items": wi_count}

        except Exception as e:
            logger.exception("Delivery sync FAILED for project %s: %s", project_id, e)
            slog.fail(str(e)[:500])
            await _fail_job(str(e)[:500])
            return {"error": str(e)}
        finally:
            slog.close()


@celery.task(name="sync_delivery")
def sync_delivery(project_id: str, job_id: str | None = None) -> dict:
    logger.info("Celery task sync_delivery called: project=%s job=%s", project_id, job_id)
    return asyncio.run(_run_delivery_sync(project_id, job_id))


async def _run_project_insights(run_id: str, project_id: str) -> None:
    from app.db.models.insight import InsightRun, InsightRunStatus
    from app.services.insights.engine import run_analysis, persist_findings
    from app.services.sync_logger import SyncLogger

    slog = SyncLogger(f"insights-{run_id}")

    Session = _get_session()
    async with Session() as db:
        run = await db.get(InsightRun, uuid.UUID(run_id))
        if not run:
            logger.error("InsightRun %s not found", run_id)
            slog.error("init", f"InsightRun {run_id} not found in database")
            slog.fail("Run not found")
            slog.close()
            return

        try:
            slog.info("init", f"Starting insights analysis for project {project_id}")

            raw_findings = await run_analysis(db, run, slog=slog)

            try:
                from app.services.insights.enhancer import enhance_findings
                slog.info("enhance", "Running AI enhancement on findings...")
                raw_findings = await enhance_findings(db, run.project_id, raw_findings, slog=slog)
                slog.info("enhance", "AI enhancement complete")
            except Exception:
                logger.warning("AI enhancement failed, using raw findings", exc_info=True)
                slog.warning("enhance", "AI enhancement failed — using raw findings")

            slog.info("persist", f"Persisting {len(raw_findings)} findings...")
            count = await persist_findings(db, run, raw_findings)
            logger.info("InsightRun %s completed with %d findings", run_id, count)
            slog.info("persist", f"Persisted {count} findings (deduplicated)")
            slog.complete()

        except Exception as e:
            logger.exception("InsightRun %s failed: %s", run_id, e)
            slog.fail(str(e)[:500])
            await db.rollback()
            run = await db.get(InsightRun, uuid.UUID(run_id))
            if run:
                run.status = InsightRunStatus.FAILED
                run.error_message = str(e)[:2000]
                run.finished_at = datetime.now(timezone.utc)
                await db.commit()
        finally:
            slog.close()


@celery.task(name="run_project_insights")
def run_project_insights(run_id: str, project_id: str) -> dict:
    logger.info("Celery task run_project_insights: run=%s project=%s", run_id, project_id)
    asyncio.run(_run_project_insights(run_id, project_id))
    return {"run_id": run_id, "project_id": project_id}


async def _schedule_all_project_insights() -> int:
    """Create an InsightRun for each project and dispatch tasks."""
    from app.db.models.insight import InsightRun, InsightRunStatus

    Session = _get_session()
    async with Session() as db:
        projects = (await db.execute(select(Project))).scalars().all()
        count = 0
        for project in projects:
            run = InsightRun(project_id=project.id, status=InsightRunStatus.RUNNING)
            db.add(run)
            await db.flush()
            run_project_insights.delay(str(run.id), str(project.id))
            count += 1
        await db.commit()
    return count


@celery.task(name="schedule_all_project_insights")
def schedule_all_project_insights() -> dict:
    logger.info("Scheduling insights analysis for all projects")
    count = asyncio.run(_schedule_all_project_insights())
    logger.info("Dispatched insights for %d projects", count)
    return {"projects_scheduled": count}


async def _run_contributor_insights(run_id: str, contributor_id: str) -> None:
    from app.db.models.contributor_insight import ContributorInsightRun
    from app.services.insights.contributor_engine import (
        run_contributor_analysis, persist_contributor_findings,
    )
    from app.services.sync_logger import SyncLogger
    from app.services.insights.enhancer import enhance_findings

    slog = SyncLogger(f"contributor-insights-{run_id}")

    Session = _get_session()
    async with Session() as db:
        run = await db.get(ContributorInsightRun, uuid.UUID(run_id))
        if not run:
            logger.error("ContributorInsightRun %s not found", run_id)
            slog.error("init", f"ContributorInsightRun {run_id} not found")
            slog.fail("Run not found")
            slog.close()
            return

        try:
            slog.info("init", f"Starting insights analysis for contributor {contributor_id}")

            raw_findings = await run_contributor_analysis(db, run, slog=slog)

            try:
                slog.info("enhance", "Running AI enhancement on findings...")
                raw_findings = await enhance_findings(
                    db, None, raw_findings, slog=slog,
                )
                slog.info("enhance", "AI enhancement complete")
            except Exception:
                logger.warning("AI enhancement failed for contributor insights", exc_info=True)
                slog.warning("enhance", "AI enhancement failed — using raw findings")

            slog.info("persist", f"Persisting {len(raw_findings)} findings...")
            count = await persist_contributor_findings(db, run, raw_findings)
            logger.info("ContributorInsightRun %s completed with %d findings", run_id, count)
            slog.info("persist", f"Persisted {count} findings (deduplicated)")
            slog.complete()

        except Exception as e:
            logger.exception("ContributorInsightRun %s failed: %s", run_id, e)
            slog.fail(str(e)[:500])
            await db.rollback()
            run = await db.get(ContributorInsightRun, uuid.UUID(run_id))
            if run:
                run.status = "failed"
                run.error_message = str(e)[:2000]
                run.finished_at = datetime.now(timezone.utc)
                await db.commit()
        finally:
            slog.close()


@celery.task(name="run_contributor_insights")
def run_contributor_insights(run_id: str, contributor_id: str) -> dict:
    logger.info("Celery task run_contributor_insights: run=%s contributor=%s", run_id, contributor_id)
    asyncio.run(_run_contributor_insights(run_id, contributor_id))
    return {"run_id": run_id, "contributor_id": contributor_id}
