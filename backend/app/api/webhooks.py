"""Webhook receiver endpoints for automated code review.

Accepts PR event payloads from GitHub, Azure DevOps, and GitLab, validates
their authenticity, and dispatches a Celery task to run the code-reviewer
agent headlessly.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.base import async_session
from app.db.models import Repository
from app.db.models.code_review_run import (
    CodeReviewRun,
    CodeReviewStatus,
    CodeReviewTrigger,
)
from app.db.models.repository import Platform

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


# ── Shared helpers ─────────────────────────────────────────────────────


async def _find_repo_by_platform(
    db: AsyncSession,
    platform: Platform,
    owner: str,
    repo_name: str,
) -> Repository | None:
    result = await db.execute(
        select(Repository).where(
            Repository.platform == platform,
            Repository.platform_owner == owner,
            Repository.platform_repo == repo_name,
        ).limit(1)
    )
    return result.scalar_one_or_none()


async def _create_review_run(
    db: AsyncSession,
    repo: Repository,
    pr_number: int,
    trigger: CodeReviewTrigger,
) -> CodeReviewRun:
    run = CodeReviewRun(
        project_id=repo.project_id,
        repository_id=repo.id,
        platform_pr_number=pr_number,
        trigger=trigger,
        status=CodeReviewStatus.QUEUED,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


def _dispatch_review(run: CodeReviewRun) -> str:
    from app.workers.tasks import run_code_review

    task = run_code_review.delay(str(run.id))
    return task.id


# ── GitHub ─────────────────────────────────────────────────────────────


def _verify_github_signature(payload: bytes, signature: str | None, secret: str) -> bool:
    if not signature:
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
):
    body = await request.body()

    if not _verify_github_signature(body, x_hub_signature_256, settings.secret_key):
        raise HTTPException(status_code=401, detail="Invalid signature")

    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": f"event={x_github_event}"}

    payload = await request.json()
    action = payload.get("action", "")
    if action not in ("opened", "synchronize", "reopened"):
        return {"status": "ignored", "reason": f"action={action}"}

    pr = payload.get("pull_request", {})
    pr_number = pr.get("number")
    repo_data = payload.get("repository", {})
    full_name = repo_data.get("full_name", "")
    parts = full_name.split("/", 1)
    if len(parts) != 2 or not pr_number:
        raise HTTPException(status_code=400, detail="Missing repo or PR data")

    owner, repo_name = parts

    async with async_session() as db:
        repo = await _find_repo_by_platform(db, Platform.GITHUB, owner, repo_name)
        if not repo:
            return {"status": "ignored", "reason": "repository not tracked"}

        run = await _create_review_run(db, repo, pr_number, CodeReviewTrigger.WEBHOOK)
        task_id = _dispatch_review(run)

    logger.info("GitHub webhook: dispatched code review %s for %s PR #%s", run.id, full_name, pr_number)
    return {"status": "queued", "review_run_id": str(run.id), "celery_task_id": task_id}


# ── Azure DevOps ───────────────────────────────────────────────────────


def _verify_azure_auth(request: Request, secret: str) -> bool:
    """Validate Azure DevOps service hook basic auth or shared secret header."""
    auth = request.headers.get("Authorization", "")
    if auth:
        import base64
        try:
            decoded = base64.b64decode(auth.replace("Basic ", "")).decode()
            _, password = decoded.split(":", 1)
            return hmac.compare_digest(password, secret)
        except Exception:
            return False
    token = request.headers.get("X-Azure-Token", "")
    return hmac.compare_digest(token, secret) if token else False


@router.post("/azure-devops")
async def azure_devops_webhook(request: Request):
    if not _verify_azure_auth(request, settings.secret_key):
        raise HTTPException(status_code=401, detail="Invalid authentication")

    payload = await request.json()
    event_type = payload.get("eventType", "")
    if "pullrequest" not in event_type.lower().replace(".", ""):
        return {"status": "ignored", "reason": f"eventType={event_type}"}

    resource = payload.get("resource", {})
    pr_number = resource.get("pullRequestId")
    repo_data = resource.get("repository", {})
    repo_name = repo_data.get("name", "")

    project_data = repo_data.get("project", {})
    project_name = project_data.get("name", "")

    if not pr_number or not repo_name:
        raise HTTPException(status_code=400, detail="Missing PR or repo data")

    org_url = payload.get("resourceContainers", {}).get("account", {}).get("baseUrl", "")
    org_name = ""
    if org_url:
        org_name = org_url.rstrip("/").split("/")[-1]

    owner = f"{org_name}/{project_name}" if org_name and project_name else project_name

    async with async_session() as db:
        repo = await _find_repo_by_platform(db, Platform.AZURE, owner, repo_name)
        if not repo:
            result = await db.execute(
                select(Repository).where(
                    Repository.platform == Platform.AZURE,
                    Repository.platform_repo == repo_name,
                ).limit(1)
            )
            repo = result.scalar_one_or_none()

        if not repo:
            return {"status": "ignored", "reason": "repository not tracked"}

        run = await _create_review_run(db, repo, pr_number, CodeReviewTrigger.WEBHOOK)
        task_id = _dispatch_review(run)

    logger.info("Azure webhook: dispatched code review %s for %s PR #%s", run.id, repo_name, pr_number)
    return {"status": "queued", "review_run_id": str(run.id), "celery_task_id": task_id}


# ── GitLab ─────────────────────────────────────────────────────────────


@router.post("/gitlab")
async def gitlab_webhook(
    request: Request,
    x_gitlab_token: str | None = Header(None),
):
    if not x_gitlab_token or not hmac.compare_digest(x_gitlab_token, settings.secret_key):
        raise HTTPException(status_code=401, detail="Invalid token")

    payload = await request.json()
    event_type = payload.get("event_type", "") or payload.get("object_kind", "")
    if event_type != "merge_request":
        return {"status": "ignored", "reason": f"event_type={event_type}"}

    attrs = payload.get("object_attributes", {})
    action = attrs.get("action", "")
    if action not in ("open", "reopen", "update"):
        return {"status": "ignored", "reason": f"action={action}"}

    mr_iid = attrs.get("iid")
    project_data = payload.get("project", {})
    path_with_namespace = project_data.get("path_with_namespace", "")
    parts = path_with_namespace.rsplit("/", 1)
    if len(parts) != 2 or not mr_iid:
        raise HTTPException(status_code=400, detail="Missing MR or project data")

    owner, repo_name = parts

    async with async_session() as db:
        repo = await _find_repo_by_platform(db, Platform.GITLAB, owner, repo_name)
        if not repo:
            return {"status": "ignored", "reason": "repository not tracked"}

        run = await _create_review_run(db, repo, mr_iid, CodeReviewTrigger.WEBHOOK)
        task_id = _dispatch_review(run)

    logger.info("GitLab webhook: dispatched code review %s for %s MR !%s", run.id, path_with_namespace, mr_iid)
    return {"status": "queued", "review_run_id": str(run.id), "celery_task_id": task_id}


# ── Manual trigger ─────────────────────────────────────────────────────


class ManualReviewRequest(BaseModel):
    repository_id: uuid.UUID
    pr_number: int


@router.post("/projects/{project_id}/code-reviews")
async def trigger_code_review(
    project_id: uuid.UUID,
    body: ManualReviewRequest,
):
    """Manually trigger a code review for a specific PR. No authentication
    required beyond the standard API auth (handled at gateway/middleware level)."""
    async with async_session() as db:
        repo = await db.get(Repository, body.repository_id)
        if not repo or repo.project_id != project_id:
            raise HTTPException(status_code=404, detail="Repository not found in project")

        run = await _create_review_run(db, repo, body.pr_number, CodeReviewTrigger.MANUAL)
        task_id = _dispatch_review(run)

    logger.info("Manual trigger: dispatched code review %s for repo %s PR #%s", run.id, body.repository_id, body.pr_number)
    return {"status": "queued", "review_run_id": str(run.id), "celery_task_id": task_id}
