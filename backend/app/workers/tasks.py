import asyncio
import re
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
    fetch_ado_work_item_activities, rebuild_daily_delivery_stats,
    _parse_ado_project,
)
from app.services.metrics import rebuild_daily_stats
from app.services.sync_logger import SyncLogger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _get_session() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _cleanup_orphaned_running_jobs() -> None:
    from app.db.models.delivery_sync_job import DeliverySyncJob

    Session = _get_session()
    async with Session() as db:
        now = datetime.now(timezone.utc)
        cleaned = 0

        for model in (SyncJob, DeliverySyncJob):
            result = await db.execute(
                select(model).where(
                    model.status.in_([SyncStatus.QUEUED, SyncStatus.RUNNING])
                )
            )
            for job in result.scalars().all():
                job.status = SyncStatus.FAILED
                job.error_message = "Worker restarted; task was interrupted"
                job.finished_at = now
                cleaned += 1
                logger.info("Cleaned up orphaned %s job %s on worker startup", model.__tablename__, job.id)

        if cleaned:
            await db.commit()


@worker_ready.connect
def _on_worker_ready(sender, **kwargs):
    try:
        asyncio.run(_cleanup_orphaned_running_jobs())
    except Exception:
        logger.exception("Failed to clean up orphaned jobs on startup")


class SyncCancelled(Exception):
    pass


_WI_REF_RE = re.compile(r'(?:AB)?#(\d{2,})')


async def _link_commits_to_work_items(
    db: AsyncSession,
    project_id: uuid.UUID,
    repo_ids: list[uuid.UUID] | None = None,
    sync_log: "SyncLogger | None" = None,
) -> int:
    """Scan commit messages for work-item references and create WorkItemCommit rows.

    If *repo_ids* is given, only commits from those repos are scanned;
    otherwise all repos belonging to *project_id* are included.
    """
    from app.db.models.work_item import WorkItem
    from app.db.models.work_item_commit import WorkItemCommit

    if repo_ids is None:
        repo_ids = list(
            (await db.execute(
                select(Repository.id).where(Repository.project_id == project_id)
            )).scalars().all()
        )
    if not repo_ids:
        return 0

    commits = (
        await db.execute(
            select(Commit).where(Commit.repository_id.in_(repo_ids))
        )
    ).scalars().all()

    wi_rows = await db.execute(
        select(WorkItem.platform_work_item_id, WorkItem.id)
        .where(WorkItem.project_id == project_id)
    )
    wi_map = {row[0]: row[1] for row in wi_rows.all()}
    if not wi_map:
        if sync_log:
            sync_log.info("wi_links", "No work items in DB — skipping commit-message link scan")
        return 0

    link_count = 0
    for c in commits:
        if not c.message:
            continue
        refs = _WI_REF_RE.findall(c.message)
        for ref_str in refs:
            ref_id = int(ref_str)
            wi_uuid = wi_map.get(ref_id)
            if not wi_uuid:
                continue
            existing = await db.execute(
                select(WorkItemCommit).where(
                    WorkItemCommit.work_item_id == wi_uuid,
                    WorkItemCommit.commit_id == c.id,
                )
            )
            if not existing.scalar_one_or_none():
                db.add(WorkItemCommit(
                    work_item_id=wi_uuid,
                    commit_id=c.id,
                    link_type="message_ref",
                ))
                link_count += 1

    if link_count:
        await db.flush()
    if sync_log:
        sync_log.info("wi_links", f"Found {link_count} commit-to-work-item links from messages")
    return link_count


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
            await _link_commits_to_work_items(
                db, repo.project_id, repo_ids=[repo.id], sync_log=slog,
            )

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

            if settings.auto_sast_on_sync:
                try:
                    from app.db.models.sast import SastScanRun, SastScanStatus
                    sast_run = SastScanRun(
                        repository_id=repo.id,
                        project_id=repo.project_id,
                        status=SastScanStatus.QUEUED,
                    )
                    db.add(sast_run)
                    await db.commit()
                    await db.refresh(sast_run)
                    run_sast_scan.delay(str(sast_run.id), str(repo.id))
                    slog.info("sast", "SAST scan queued automatically")
                except Exception:
                    logger.warning("Auto SAST scan trigger failed", exc_info=True)

            if settings.auto_dep_scan_on_sync:
                try:
                    from app.db.models.dependency import DepScanRun, DepScanStatus
                    dep_run = DepScanRun(
                        repository_id=repo.id,
                        project_id=repo.project_id,
                        status=DepScanStatus.QUEUED,
                    )
                    db.add(dep_run)
                    await db.commit()
                    await db.refresh(dep_run)
                    run_dependency_scan.delay(str(dep_run.id), str(repo.id))
                    slog.info("dep_scan", "Dependency scan queued automatically")
                except Exception:
                    logger.warning("Auto dependency scan trigger failed", exc_info=True)

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
    # Key logs on job_id so each sync row in the UI shows only its own stream.
    # Fall back to a project-scoped key for legacy direct invocations that
    # don't thread a job_id through (admin tools, backfills, etc.).
    slog_id = job_id if job_id else f"delivery-{project_id}"
    slog = SyncLogger(slog_id)
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

        async def _persist_logs():
            """Snapshot the Redis log list onto the DB row so history survives
            the Redis TTL and container restarts. Best-effort: a failure here
            should never mask the real sync result."""
            if not job:
                return
            try:
                entries = slog.snapshot()
                if entries:
                    job.logs = entries
                    await db.commit()
            except Exception:
                logger.exception("Failed to persist sync logs for job %s", job_id)
                await db.rollback()

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
            await _fail_job("Project not found")
            slog.fail("Project not found")
            await _persist_logs()
            slog.close()
            return {"error": "Project not found"}

        ado_project_name = _parse_ado_project(project)
        if not ado_project_name:
            slog.error("init", "No Azure DevOps repository found in project — cannot sync delivery data")
            await _fail_job("No Azure repo in project")
            slog.fail("No Azure repo in project")
            await _persist_logs()
            slog.close()
            return {"error": "No Azure repo in project"}

        token, base_url = await _resolve_platform_token(db, Platform.AZURE)
        if not token:
            slog.error("init", "No Azure DevOps credential found")
            await _fail_job("No Azure credential")
            slog.fail("No Azure credential")
            await _persist_logs()
            slog.close()
            return {"error": "No Azure credential"}

        azure_repo = next(
            (r for r in project.repositories if r.platform and r.platform.value == "azure"),
            None,
        )
        org_url = base_url or (_derive_azure_org_url(azure_repo) if azure_repo else None)
        if not org_url:
            slog.error("init", "Cannot determine Azure DevOps org URL")
            await _fail_job("No org URL")
            slog.fail("No org URL")
            await _persist_logs()
            slog.close()
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

            slog.info("activities", "Fetching work item activity history...")
            act_count = await fetch_ado_work_item_activities(db, project, org_url, token, ado_project_name, slog)
            slog.info("activities", f"Synced {act_count} activity records")

            slog.info("wi_links", "Scanning commit messages for work item references...")
            await _link_commits_to_work_items(
                db, project.id, sync_log=slog,
            )

            slog.info("stats", "Rebuilding daily delivery stats...")
            await rebuild_daily_delivery_stats(db, project.id)
            slog.info("stats", "Daily delivery stats rebuilt")

            if job:
                job.status = SyncStatus.COMPLETED
                job.finished_at = datetime.now(timezone.utc)

            await db.commit()
            slog.complete()
            await _persist_logs()
            return {"teams": teams_count, "iterations": iter_count, "work_items": wi_count}

        except Exception as e:
            logger.exception("Delivery sync FAILED for project %s: %s", project_id, e)
            slog.fail(str(e)[:500])
            await db.rollback()
            await _fail_job(str(e)[:500])
            await _persist_logs()
            return {"error": str(e)}
        finally:
            slog.close()


async def _mark_delivery_job_failed(job_id: str, error: str) -> None:
    from app.db.models.delivery_sync_job import DeliverySyncJob
    Session = _get_session()
    async with Session() as db:
        job = await db.get(DeliverySyncJob, uuid.UUID(job_id))
        if job and job.status in (SyncStatus.QUEUED, SyncStatus.RUNNING):
            job.status = SyncStatus.FAILED
            job.error_message = f"Task failed unexpectedly: {error[:2000]}"
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info("Marked stale delivery job %s as FAILED via on_failure hook", job_id)


class _DeliverySyncTask(celery.Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        if args and len(args) >= 2 and args[1]:
            try:
                asyncio.run(_mark_delivery_job_failed(args[1], str(exc)))
            except Exception:
                logger.exception("on_failure hook could not mark delivery job as failed")


@celery.task(name="sync_delivery", base=_DeliverySyncTask)
def sync_delivery(project_id: str, job_id: str | None = None) -> dict:
    logger.info("Celery task sync_delivery called: project=%s job=%s", project_id, job_id)
    return asyncio.run(_run_delivery_sync(project_id, job_id))


async def _run_backfill_iteration_transitions(project_id: str | None = None) -> dict:
    """Re-pull work item update history for projects missing iteration-path activities.

    Old syncs stored at most one activity per revision, so iteration-path
    changes that coincided with state/assignment changes were dropped.
    This task re-hydrates ``work_item_activities`` for those projects.

    If ``project_id`` is provided, only that project is backfilled.
    Otherwise every Azure-linked project that has work items but *zero*
    ``System.IterationPath`` activity rows is processed.
    """
    from sqlalchemy.orm import selectinload
    from app.services.iteration_transitions import (
        project_has_iteration_transitions,
    )

    slog = SyncLogger(f"backfill-iterations-{project_id or 'all'}")
    slog.info("init", f"Starting iteration-path backfill project={project_id or '<all>'}")

    Session = _get_session()
    results: dict[str, int] = {}

    async with Session() as db:
        q = select(Project).options(selectinload(Project.repositories))
        if project_id:
            q = q.where(Project.id == uuid.UUID(project_id))
        projects = (await db.execute(q)).scalars().all()

        if not projects:
            slog.info("init", "No projects matched")
            slog.close()
            return results

        token, base_url = await _resolve_platform_token(db, Platform.AZURE)
        if not token:
            slog.error("init", "No Azure DevOps credential; cannot backfill")
            slog.close()
            return results

        for project in projects:
            ado_project_name = _parse_ado_project(project)
            if not ado_project_name:
                continue

            if not project_id and await project_has_iteration_transitions(db, project.id):
                continue

            azure_repo = next(
                (r for r in project.repositories if r.platform and r.platform.value == "azure"),
                None,
            )
            org_url = base_url or (_derive_azure_org_url(azure_repo) if azure_repo else None)
            if not org_url:
                slog.warning(str(project.id), "Cannot determine org URL; skipping")
                continue

            try:
                slog.info(str(project.id), f"Backfilling activities for {project.name}")
                created = await fetch_ado_work_item_activities(
                    db, project, org_url, token, ado_project_name, slog,
                )
                await db.commit()
                results[str(project.id)] = created
                slog.info(str(project.id), f"Backfilled {created} activity rows")
            except Exception as e:
                logger.exception(
                    "Backfill failed for project %s: %s", project.id, e,
                )
                slog.warning(str(project.id), f"Backfill failed: {e}")
                await db.rollback()

    slog.complete()
    return results


@celery.task(name="backfill_iteration_transitions")
def backfill_iteration_transitions(project_id: str | None = None) -> dict:
    """Celery entry point for the iteration-path backfill."""
    logger.info(
        "Celery task backfill_iteration_transitions called: project=%s",
        project_id or "<all>",
    )
    return asyncio.run(_run_backfill_iteration_transitions(project_id))


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
    from app.services.insights.contributor_enhancer import enhance_contributor_findings

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
                slog.info("enhance", "Running agentic root-cause investigation...")
                raw_findings = await enhance_contributor_findings(
                    db, uuid.UUID(contributor_id), raw_findings, slog=slog,
                )
                slog.info("enhance", "Agentic enhancement complete")
            except Exception:
                logger.warning("Agentic enhancement failed for contributor insights", exc_info=True)
                slog.warning("enhance", "Agentic enhancement failed — using raw findings")

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


async def _run_team_insights(run_id: str, team_id: str, project_id: str) -> None:
    from app.db.models.team_insight import TeamInsightRun
    from app.services.insights.team_engine import run_team_analysis, persist_team_findings
    from app.services.sync_logger import SyncLogger

    slog = SyncLogger(f"team-insights-{run_id}")

    Session = _get_session()
    async with Session() as db:
        run = await db.get(TeamInsightRun, uuid.UUID(run_id))
        if not run:
            logger.error("TeamInsightRun %s not found", run_id)
            slog.error("init", f"TeamInsightRun {run_id} not found")
            slog.fail("Run not found")
            slog.close()
            return

        try:
            slog.info("init", f"Starting insights analysis for team {team_id}")

            raw_findings = await run_team_analysis(db, run, slog=slog)

            try:
                from app.services.insights.enhancer import enhance_findings
                slog.info("enhance", "Running AI enhancement on findings...")
                raw_findings = await enhance_findings(db, uuid.UUID(project_id), raw_findings, slog=slog)
                slog.info("enhance", "AI enhancement complete")
            except Exception:
                logger.warning("AI enhancement failed for team insights", exc_info=True)
                slog.warning("enhance", "AI enhancement failed — using raw findings")

            slog.info("persist", f"Persisting {len(raw_findings)} findings...")
            count = await persist_team_findings(db, run, raw_findings)
            logger.info("TeamInsightRun %s completed with %d findings", run_id, count)
            slog.info("persist", f"Persisted {count} findings (deduplicated)")
            slog.complete()

        except Exception as e:
            logger.exception("TeamInsightRun %s failed: %s", run_id, e)
            slog.fail(str(e)[:500])
            await db.rollback()
            run = await db.get(TeamInsightRun, uuid.UUID(run_id))
            if run:
                run.status = "failed"
                run.error_message = str(e)[:2000]
                run.finished_at = datetime.now(timezone.utc)
                await db.commit()
        finally:
            slog.close()


@celery.task(name="run_team_insights")
def run_team_insights(run_id: str, team_id: str, project_id: str) -> dict:
    logger.info("Celery task run_team_insights: run=%s team=%s", run_id, team_id)
    asyncio.run(_run_team_insights(run_id, team_id, project_id))
    return {"run_id": run_id, "team_id": team_id, "project_id": project_id}


async def _run_sast_scan(scan_id: str, repository_id: str) -> None:
    from app.db.models.sast import SastScanRun, SastScanStatus, SastRuleProfile
    from app.services.sast_scanner import run_sast_scan as execute_scan
    from app.services.sync_logger import SyncLogger

    slog = SyncLogger(f"sast-{scan_id}")

    Session = _get_session()
    async with Session() as db:
        scan_run = await db.get(SastScanRun, uuid.UUID(scan_id))
        if not scan_run:
            logger.error("SastScanRun %s not found", scan_id)
            slog.error("init", f"SastScanRun {scan_id} not found")
            slog.fail("Scan run not found")
            slog.close()
            return

        try:
            scan_run.status = SastScanStatus.RUNNING
            scan_run.started_at = datetime.now(timezone.utc)
            await db.commit()

            slog.info("init", f"Starting SAST scan for repository {repository_id}")

            profile = None
            if scan_run.config_profile_id:
                profile = await db.get(SastRuleProfile, scan_run.config_profile_id)
            if not profile:
                result = await db.execute(
                    select(SastRuleProfile).where(SastRuleProfile.is_default.is_(True)).limit(1)
                )
                profile = result.scalar_one_or_none()

            if profile:
                slog.info("config", f"Using rule profile: {profile.name} ({', '.join(profile.rulesets)})")
            else:
                slog.info("config", "No rule profile configured, using Semgrep auto-detect")

            count = await execute_scan(
                db, scan_run,
                branch=scan_run.branch,
                profile=profile,
                slog=slog,
            )

            scan_run.status = SastScanStatus.COMPLETED
            scan_run.finished_at = datetime.now(timezone.utc)
            scan_run.findings_count = count
            await db.commit()

            slog.info("done", f"SAST scan complete: {count} findings")
            slog.complete()

        except Exception as e:
            logger.exception("SastScanRun %s failed: %s", scan_id, e)
            slog.fail(str(e)[:500])
            await db.rollback()
            scan_run = await db.get(SastScanRun, uuid.UUID(scan_id))
            if scan_run:
                scan_run.status = SastScanStatus.FAILED
                scan_run.error_message = str(e)[:2000]
                scan_run.finished_at = datetime.now(timezone.utc)
                await db.commit()
        finally:
            slog.close()


@celery.task(name="run_sast_scan")
def run_sast_scan(scan_id: str, repository_id: str) -> dict:
    logger.info("Celery task run_sast_scan: scan=%s repo=%s", scan_id, repository_id)
    asyncio.run(_run_sast_scan(scan_id, repository_id))
    return {"scan_id": scan_id, "repository_id": repository_id}


# ---------------------------------------------------------------------------
# Dependency scan
# ---------------------------------------------------------------------------

async def _run_dependency_scan(scan_id: str, repository_id: str) -> None:
    from app.db.models.dependency import DepScanRun, DepScanStatus
    from app.services.dependency_scanner import scan_repository_dependencies
    from app.services.sync_logger import SyncLogger

    slog = SyncLogger(f"dep-{scan_id}")

    Session = _get_session()
    async with Session() as db:
        scan_run = await db.get(DepScanRun, uuid.UUID(scan_id))
        if not scan_run:
            logger.error("DepScanRun %s not found", scan_id)
            slog.error("init", f"DepScanRun {scan_id} not found")
            slog.fail("Scan run not found")
            slog.close()
            return

        try:
            scan_run.status = DepScanStatus.RUNNING
            scan_run.started_at = datetime.now(timezone.utc)
            await db.commit()

            repo = await db.get(Repository, uuid.UUID(repository_id))
            if not repo:
                raise FileNotFoundError(f"Repository {repository_id} not found")

            slog.info("init", f"Starting dependency scan for repository {repo.name}")

            count = await scan_repository_dependencies(db, repo, scan_run, slog=slog)

            scan_run.status = DepScanStatus.COMPLETED
            scan_run.finished_at = datetime.now(timezone.utc)
            await db.commit()

            slog.info("done", f"Dependency scan complete: {count} findings")
            slog.complete()

        except Exception as e:
            logger.exception("DepScanRun %s failed: %s", scan_id, e)
            slog.fail(str(e)[:500])
            await db.rollback()
            scan_run = await db.get(DepScanRun, uuid.UUID(scan_id))
            if scan_run:
                scan_run.status = DepScanStatus.FAILED
                scan_run.error_message = str(e)[:2000]
                scan_run.finished_at = datetime.now(timezone.utc)
                await db.commit()
        finally:
            slog.close()


async def _mark_dep_scan_failed(scan_id: str, error: str) -> None:
    from app.db.models.dependency import DepScanRun, DepScanStatus
    Session = _get_session()
    async with Session() as db:
        scan_run = await db.get(DepScanRun, uuid.UUID(scan_id))
        if scan_run and scan_run.status in (DepScanStatus.QUEUED, DepScanStatus.RUNNING):
            scan_run.status = DepScanStatus.FAILED
            scan_run.error_message = f"Task failed unexpectedly: {error[:2000]}"
            scan_run.finished_at = datetime.now(timezone.utc)
            await db.commit()


class _DepScanTask(celery.Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        if args:
            try:
                asyncio.run(_mark_dep_scan_failed(args[0], str(exc)))
            except Exception:
                logger.exception("on_failure hook could not mark dep scan as failed")


@celery.task(name="run_dependency_scan", base=_DepScanTask)
def run_dependency_scan(scan_id: str, repository_id: str) -> dict:
    logger.info("Celery task run_dependency_scan: scan=%s repo=%s", scan_id, repository_id)
    asyncio.run(_run_dependency_scan(scan_id, repository_id))
    return {"scan_id": scan_id, "repository_id": repository_id}


# ---------------------------------------------------------------------------
# Project scheduling engine
# ---------------------------------------------------------------------------

from datetime import timedelta
from app.db.models.project_schedule import ProjectSchedule, ScheduleInterval

_INTERVAL_MAP: dict[str, timedelta] = {
    ScheduleInterval.EVERY_HOUR.value: timedelta(hours=1),
    ScheduleInterval.EVERY_6_HOURS.value: timedelta(hours=6),
    ScheduleInterval.EVERY_12_HOURS.value: timedelta(hours=12),
    ScheduleInterval.DAILY.value: timedelta(days=1),
    ScheduleInterval.EVERY_2_DAYS.value: timedelta(days=2),
    ScheduleInterval.WEEKLY.value: timedelta(weeks=1),
    ScheduleInterval.MONTHLY.value: timedelta(days=30),
}


def _is_due(interval: str, last_run_at: datetime | None) -> bool:
    if interval == ScheduleInterval.DISABLED.value:
        return False
    td = _INTERVAL_MAP.get(interval)
    if td is None:
        return False
    if last_run_at is None:
        return True
    return datetime.now(timezone.utc) >= last_run_at + td


async def _dispatch_scheduled_tasks() -> dict:
    from sqlalchemy.orm import selectinload
    from app.db.models.insight import InsightRun, InsightRunStatus
    from app.db.models.sast import SastScanRun, SastScanStatus
    from app.db.models.dependency import DepScanRun, DepScanStatus
    from app.db.models.delivery_sync_job import DeliverySyncJob

    Session = _get_session()
    dispatched: dict[str, int] = {
        "repo_sync": 0, "delivery_sync": 0,
        "security_scan": 0, "dependency_scan": 0, "insights": 0,
    }

    async with Session() as db:
        result = await db.execute(
            select(ProjectSchedule)
            .options(selectinload(ProjectSchedule.project).selectinload(Project.repositories))
        )
        schedules = result.scalars().all()
        now = datetime.now(timezone.utc)

        for sched in schedules:
            project = sched.project
            if not project:
                continue

            if _is_due(sched.repo_sync_interval, sched.repo_sync_last_run_at):
                for repo in project.repositories:
                    job = SyncJob(repository_id=repo.id, status=SyncStatus.QUEUED)
                    db.add(job)
                    await db.flush()
                    sync_repository.delay(str(repo.id), str(job.id))
                    dispatched["repo_sync"] += 1
                sched.repo_sync_last_run_at = now

            if _is_due(sched.delivery_sync_interval, sched.delivery_sync_last_run_at):
                job = DeliverySyncJob(project_id=project.id, status=SyncStatus.QUEUED)
                db.add(job)
                await db.flush()
                sync_delivery.delay(str(project.id), str(job.id))
                sched.delivery_sync_last_run_at = now
                dispatched["delivery_sync"] += 1

            if _is_due(sched.security_scan_interval, sched.security_scan_last_run_at):
                for repo in project.repositories:
                    scan_run = SastScanRun(
                        repository_id=repo.id,
                        project_id=project.id,
                        status=SastScanStatus.QUEUED,
                    )
                    db.add(scan_run)
                    await db.flush()
                    run_sast_scan.delay(str(scan_run.id), str(repo.id))
                    dispatched["security_scan"] += 1
                sched.security_scan_last_run_at = now

            if _is_due(sched.dependency_scan_interval, sched.dependency_scan_last_run_at):
                for repo in project.repositories:
                    dep_run = DepScanRun(
                        repository_id=repo.id,
                        project_id=project.id,
                        status=DepScanStatus.QUEUED,
                    )
                    db.add(dep_run)
                    await db.flush()
                    run_dependency_scan.delay(str(dep_run.id), str(repo.id))
                    dispatched["dependency_scan"] += 1
                sched.dependency_scan_last_run_at = now

            if _is_due(sched.insights_interval, sched.insights_last_run_at):
                run = InsightRun(project_id=project.id, status=InsightRunStatus.RUNNING)
                db.add(run)
                await db.flush()
                run_project_insights.delay(str(run.id), str(project.id))
                sched.insights_last_run_at = now
                dispatched["insights"] += 1

        await db.commit()

    return dispatched


@celery.task(name="scheduler_tick")
def scheduler_tick() -> dict:
    dispatched = asyncio.run(_dispatch_scheduled_tasks())
    total = sum(dispatched.values())
    if total:
        logger.info("Scheduler tick dispatched %d tasks: %s", total, dispatched)
    return dispatched


# ---------------------------------------------------------------------------
# Automated code review
# ---------------------------------------------------------------------------

async def _run_code_review(run_id: str) -> None:
    from app.db.models.code_review_run import (
        CodeReviewRun, CodeReviewStatus, CodeReviewVerdict,
    )
    from app.agents.runner import run_agent_stream

    Session = _get_session()
    async with Session() as db:
        run = await db.get(CodeReviewRun, uuid.UUID(run_id))
        if not run:
            logger.error("CodeReviewRun %s not found", run_id)
            return

        repo = await db.get(Repository, run.repository_id)
        if not repo:
            run.status = CodeReviewStatus.FAILED
            run.error_message = "Repository not found"
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return

        try:
            run.status = CodeReviewStatus.RUNNING
            run.started_at = datetime.now(timezone.utc)
            await db.commit()

            prompt = (
                f"You are running in **automated headless mode**. Review PR "
                f"#{run.platform_pr_number} in repository '{repo.name}'.\n\n"
                f"Follow the full PR Review Workflow from your system prompt:\n"
                f"1. Get changed files\n"
                f"2. Gather ADRs and project standards\n"
                f"3. Review each file's diff\n"
                f"4. Check existing review comments\n"
                f"5. Post inline comments for each finding using post_review_comment\n"
                f"6. Submit the overall review using submit_review\n\n"
                f"Be thorough but concise. Tag findings with severity. "
                f"Set your verdict based on the severity of findings."
            )

            collected_text = ""
            findings_count = 0
            verdict = None
            review_url = None

            async for event in run_agent_stream(
                db,
                prompt,
                agent_slug="code-reviewer",
                session_id=None,
                user_id=None,
            ):
                etype = event.get("type", "")
                if etype == "token":
                    collected_text += event.get("content", "")
                elif etype == "tool_call_end":
                    tool_name = event.get("tool_name", "")
                    result = event.get("result", "")
                    if tool_name == "post_review_comment" and "Posted" in result:
                        findings_count += 1
                    elif tool_name == "submit_review":
                        if "APPROVE" in result:
                            verdict = CodeReviewVerdict.APPROVE
                        elif "REQUEST_CHANGES" in result:
                            verdict = CodeReviewVerdict.REQUEST_CHANGES
                        else:
                            verdict = CodeReviewVerdict.COMMENT
                        import re
                        url_match = re.search(r"https?://\S+", result)
                        if url_match:
                            review_url = url_match.group(0)[:1000]

            # Link to the PullRequest row if one exists
            from app.db.models.pull_request import PullRequest
            pr_q = select(PullRequest).where(
                PullRequest.repository_id == run.repository_id,
                PullRequest.platform_pr_id == run.platform_pr_number,
            ).limit(1)
            pr_row = (await db.execute(pr_q)).scalar_one_or_none()

            run.status = CodeReviewStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            run.findings_count = findings_count
            run.verdict = verdict or CodeReviewVerdict.COMMENT
            if review_url:
                run.review_url = review_url
            if pr_row:
                run.pull_request_id = pr_row.id
            await db.commit()

            logger.info(
                "CodeReviewRun %s completed: %d findings, verdict=%s",
                run_id, findings_count, run.verdict.value if run.verdict else "none",
            )

        except Exception as e:
            logger.exception("CodeReviewRun %s failed: %s", run_id, e)
            await db.rollback()
            run = await db.get(CodeReviewRun, uuid.UUID(run_id))
            if run:
                run.status = CodeReviewStatus.FAILED
                run.error_message = str(e)[:2000]
                run.completed_at = datetime.now(timezone.utc)
                await db.commit()


async def _mark_review_failed(run_id: str, error: str) -> None:
    from app.db.models.code_review_run import CodeReviewRun, CodeReviewStatus
    Session = _get_session()
    async with Session() as db:
        run = await db.get(CodeReviewRun, uuid.UUID(run_id))
        if run and run.status in (CodeReviewStatus.QUEUED, CodeReviewStatus.RUNNING):
            run.status = CodeReviewStatus.FAILED
            run.error_message = f"Task failed unexpectedly: {error[:2000]}"
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()


class _CodeReviewTask(celery.Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        if args:
            try:
                asyncio.run(_mark_review_failed(args[0], str(exc)))
            except Exception:
                logger.exception("on_failure hook could not mark code review as failed")


@celery.task(name="run_code_review", base=_CodeReviewTask)
def run_code_review(run_id: str) -> dict:
    logger.info("Celery task run_code_review: run=%s", run_id)
    asyncio.run(_run_code_review(run_id))
    return {"run_id": run_id}
