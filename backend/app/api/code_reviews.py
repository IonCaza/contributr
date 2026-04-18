"""Code review run listing, detail, and summary endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.base import get_db
from app.db.models import Project, Repository, User
from app.db.models.code_review_run import (
    CodeReviewRun,
    CodeReviewStatus,
)
from app.db.models.pull_request import PullRequest

router = APIRouter(
    prefix="/api/projects/{project_id}/code-reviews",
    tags=["code-reviews"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CodeReviewRunOut(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    repository_name: str
    platform_pr_number: int
    pr_title: str | None = None
    pr_state: str | None = None
    trigger: str
    status: str
    findings_count: int | None = None
    verdict: str | None = None
    review_url: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime


class CodeReviewSummary(BaseModel):
    total_runs: int
    completed: int
    failed: int
    avg_findings: float | None
    by_verdict: dict[str, int]
    by_trigger: dict[str, int]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_project(db: AsyncSession, project_id: uuid.UUID) -> Project:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _row_to_out(run: CodeReviewRun, repo_name: str, pr: PullRequest | None) -> CodeReviewRunOut:
    return CodeReviewRunOut(
        id=run.id,
        repository_id=run.repository_id,
        repository_name=repo_name,
        platform_pr_number=run.platform_pr_number,
        pr_title=pr.title if pr else None,
        pr_state=pr.state.value if pr and pr.state else None,
        trigger=run.trigger.value if run.trigger else "",
        status=run.status.value if run.status else "",
        findings_count=run.findings_count,
        verdict=run.verdict.value if run.verdict else None,
        review_url=run.review_url,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
        created_at=run.created_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[CodeReviewRunOut])
async def list_code_reviews(
    project_id: uuid.UUID,
    status: str | None = Query(None, description="Filter by status"),
    trigger: str | None = Query(None, description="Filter by trigger"),
    verdict: str | None = Query(None, description="Filter by verdict"),
    repository_id: uuid.UUID | None = Query(None, description="Filter by repository"),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_project(db, project_id)

    q = (
        select(CodeReviewRun, Repository.name.label("repo_name"))
        .join(Repository, CodeReviewRun.repository_id == Repository.id)
        .where(CodeReviewRun.project_id == project_id)
    )

    if status:
        q = q.where(CodeReviewRun.status == status)
    if trigger:
        q = q.where(CodeReviewRun.trigger == trigger)
    if verdict:
        q = q.where(CodeReviewRun.verdict == verdict)
    if repository_id:
        q = q.where(CodeReviewRun.repository_id == repository_id)

    q = q.order_by(CodeReviewRun.created_at.desc()).offset(offset).limit(limit)
    rows = (await db.execute(q)).all()

    results: list[CodeReviewRunOut] = []
    for run, repo_name in rows:
        pr = None
        if run.pull_request_id:
            pr = await db.get(PullRequest, run.pull_request_id)
        if pr is None:
            pr_q = select(PullRequest).where(
                PullRequest.repository_id == run.repository_id,
                PullRequest.platform_pr_id == run.platform_pr_number,
            ).limit(1)
            pr = (await db.execute(pr_q)).scalar_one_or_none()
        results.append(_row_to_out(run, repo_name, pr))

    return results


@router.get("/summary", response_model=CodeReviewSummary)
async def code_review_summary(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_project(db, project_id)

    base = select(CodeReviewRun).where(CodeReviewRun.project_id == project_id)

    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar_one()

    completed = (await db.execute(
        select(func.count()).select_from(
            base.where(CodeReviewRun.status == CodeReviewStatus.COMPLETED).subquery()
        )
    )).scalar_one()

    failed = (await db.execute(
        select(func.count()).select_from(
            base.where(CodeReviewRun.status == CodeReviewStatus.FAILED).subquery()
        )
    )).scalar_one()

    avg_findings = (await db.execute(
        select(func.avg(CodeReviewRun.findings_count)).where(
            CodeReviewRun.project_id == project_id,
            CodeReviewRun.status == CodeReviewStatus.COMPLETED,
        )
    )).scalar_one()

    verdict_rows = (await db.execute(
        select(CodeReviewRun.verdict, func.count())
        .where(
            CodeReviewRun.project_id == project_id,
            CodeReviewRun.verdict.isnot(None),
        )
        .group_by(CodeReviewRun.verdict)
    )).all()
    by_verdict = {str(v.value) if hasattr(v, "value") else str(v): c for v, c in verdict_rows}

    trigger_rows = (await db.execute(
        select(CodeReviewRun.trigger, func.count())
        .where(CodeReviewRun.project_id == project_id)
        .group_by(CodeReviewRun.trigger)
    )).all()
    by_trigger = {str(t.value) if hasattr(t, "value") else str(t): c for t, c in trigger_rows}

    return CodeReviewSummary(
        total_runs=total,
        completed=completed,
        failed=failed,
        avg_findings=round(avg_findings, 1) if avg_findings is not None else None,
        by_verdict=by_verdict,
        by_trigger=by_trigger,
    )


@router.get("/{run_id}", response_model=CodeReviewRunOut)
async def get_code_review(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_project(db, project_id)

    run = await db.get(CodeReviewRun, run_id)
    if not run or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Code review run not found")

    repo = await db.get(Repository, run.repository_id)
    repo_name = repo.name if repo else "Unknown"

    pr = None
    if run.pull_request_id:
        pr = await db.get(PullRequest, run.pull_request_id)
    if pr is None:
        pr_q = select(PullRequest).where(
            PullRequest.repository_id == run.repository_id,
            PullRequest.platform_pr_id == run.platform_pr_number,
        ).limit(1)
        pr = (await db.execute(pr_q)).scalar_one_or_none()

    return _row_to_out(run, repo_name, pr)
