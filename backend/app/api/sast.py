import json
import uuid
from datetime import datetime, timezone, timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.db.base import get_db
from app.db.models import User, Project, Repository
from app.db.models.sast import (
    SastScanRun, SastScanStatus, SastFinding, SastFindingStatus,
    SastSeverity, SastRuleProfile, SastIgnoredRule,
)
from app.auth.dependencies import get_current_user


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SastScanRunOut(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    project_id: uuid.UUID
    status: str
    branch: str | None = None
    commit_sha: str | None = None
    tool: str
    config_profile_id: uuid.UUID | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    findings_count: int
    error_message: str | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class SastFindingOut(BaseModel):
    id: uuid.UUID
    scan_run_id: uuid.UUID
    repository_id: uuid.UUID
    project_id: uuid.UUID
    rule_id: str
    severity: str
    confidence: str
    file_path: str
    start_line: int
    end_line: int
    start_col: int | None = None
    end_col: int | None = None
    message: str
    code_snippet: str | None = None
    fix_suggestion: str | None = None
    cwe_ids: list | None = None
    owasp_ids: list | None = None
    metadata: dict | None = Field(None, validation_alias="extra_metadata")
    status: str
    first_detected_at: datetime
    last_detected_at: datetime
    dismissed_at: datetime | None = None
    dismissed_by_id: uuid.UUID | None = None
    model_config = {"from_attributes": True}


class SastSummary(BaseModel):
    total_open: int
    critical: int
    high: int
    medium: int
    low: int
    info: int
    fixed_30d: int
    by_rule: dict[str, int]
    by_file: dict[str, int]


class SastRuleProfileOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    rulesets: list
    custom_rules_yaml: str | None = None
    scan_branches: list = []
    is_default: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class SastRuleProfileCreate(BaseModel):
    name: str
    description: str = ""
    rulesets: list[str] = ["auto"]
    custom_rules_yaml: str | None = None
    scan_branches: list[str] = []
    is_default: bool = False


class SastRuleProfileUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    rulesets: list[str] | None = None
    custom_rules_yaml: str | None = None
    scan_branches: list[str] | None = None
    is_default: bool | None = None


class SastIgnoredRuleOut(BaseModel):
    id: uuid.UUID
    rule_id: str
    repository_id: uuid.UUID | None = None
    reason: str
    created_by_id: uuid.UUID | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class SastIgnoredRuleCreate(BaseModel):
    rule_id: str
    reason: str = ""


class SastScanTrigger(BaseModel):
    branch: str | None = None
    profile_id: uuid.UUID | None = None


class SastSettingsOut(BaseModel):
    auto_sast_on_sync: bool


class SastSettingsUpdate(BaseModel):
    auto_sast_on_sync: bool


# ---------------------------------------------------------------------------
# Repository-scoped router
# ---------------------------------------------------------------------------

repo_router = APIRouter(
    prefix="/api/repositories/{repo_id}/sast",
    tags=["sast"],
)


async def _get_repo(db: AsyncSession, repo_id: uuid.UUID) -> Repository:
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo


@repo_router.post("/scan", response_model=SastScanRunOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_scan(
    repo_id: uuid.UUID,
    body: SastScanTrigger | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    repo = await _get_repo(db, repo_id)

    stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    stale_q = select(SastScanRun).where(
        SastScanRun.repository_id == repo_id,
        SastScanRun.status.in_([SastScanStatus.QUEUED, SastScanStatus.RUNNING]),
        SastScanRun.created_at < stale_cutoff,
    )
    for sr in (await db.execute(stale_q)).scalars().all():
        sr.status = SastScanStatus.FAILED
        sr.error_message = "Timed out (stale scan detected)"
        sr.finished_at = datetime.now(timezone.utc)
    await db.flush()

    scan_run = SastScanRun(
        repository_id=repo.id,
        project_id=repo.project_id,
        status=SastScanStatus.QUEUED,
        branch=body.branch if body else None,
        config_profile_id=body.profile_id if body else None,
    )
    db.add(scan_run)
    await db.commit()
    await db.refresh(scan_run)

    from app.workers.tasks import run_sast_scan
    run_sast_scan.delay(str(scan_run.id), str(repo.id))
    return scan_run


@repo_router.get("/findings", response_model=list[SastFindingOut])
async def list_repo_findings(
    repo_id: uuid.UUID,
    severity: str | None = None,
    finding_status: str | None = Query(None, alias="status"),
    file_path: str | None = None,
    rule_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_repo(db, repo_id)
    q = select(SastFinding).where(SastFinding.repository_id == repo_id)

    if severity:
        q = q.where(SastFinding.severity == SastSeverity(severity))
    if finding_status:
        q = q.where(SastFinding.status == SastFindingStatus(finding_status))
    else:
        q = q.where(SastFinding.status == SastFindingStatus.OPEN)
    if file_path:
        q = q.where(SastFinding.file_path.ilike(f"%{file_path}%"))
    if rule_id:
        q = q.where(SastFinding.rule_id.ilike(f"%{rule_id}%"))

    q = q.order_by(SastFinding.severity, SastFinding.last_detected_at.desc())
    return (await db.execute(q)).scalars().all()


@repo_router.get("/summary", response_model=SastSummary)
async def get_repo_summary(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_repo(db, repo_id)
    return await _build_summary(db, repository_id=repo_id)


@repo_router.get("/runs", response_model=list[SastScanRunOut])
async def list_repo_runs(
    repo_id: uuid.UUID,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_repo(db, repo_id)
    q = (
        select(SastScanRun)
        .where(SastScanRun.repository_id == repo_id)
        .order_by(SastScanRun.created_at.desc())
        .limit(limit)
    )
    return (await db.execute(q)).scalars().all()


@repo_router.get("/runs/{run_id}/logs")
async def stream_scan_logs(
    request: Request,
    repo_id: uuid.UUID,
    run_id: uuid.UUID,
    token: str | None = Query(default=None),
):
    from app.auth.security import decode_token as decode_jwt
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    payload = decode_jwt(token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    list_key = f"sync:logs:sast-{run_id}"
    channel_key = f"sync:logs:live:sast-{run_id}"

    async def event_generator():
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            existing = await r.lrange(list_key, 0, -1)
            for entry in existing:
                data = json.loads(entry)
                if data.get("phase") == "__done__":
                    yield {"event": "done", "data": entry}
                    return
                yield {"event": "log", "data": entry}

            pubsub = r.pubsub()
            await pubsub.subscribe(channel_key)
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if msg is None:
                        continue
                    data = json.loads(msg["data"])
                    if data.get("phase") == "__done__":
                        yield {"event": "done", "data": msg["data"]}
                        break
                    yield {"event": "log", "data": msg["data"]}
            finally:
                await pubsub.unsubscribe(channel_key)
                await pubsub.aclose()
        finally:
            await r.aclose()

    return EventSourceResponse(event_generator())


@repo_router.patch("/findings/{finding_id}/dismiss", response_model=SastFindingOut)
async def dismiss_finding(
    repo_id: uuid.UUID,
    finding_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SastFinding).where(
            SastFinding.id == finding_id,
            SastFinding.repository_id == repo_id,
        )
    )
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    finding.status = SastFindingStatus.DISMISSED
    finding.dismissed_at = datetime.now(timezone.utc)
    finding.dismissed_by_id = user.id
    await db.commit()
    await db.refresh(finding)
    return finding


@repo_router.patch("/findings/{finding_id}/false-positive", response_model=SastFindingOut)
async def mark_false_positive(
    repo_id: uuid.UUID,
    finding_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SastFinding).where(
            SastFinding.id == finding_id,
            SastFinding.repository_id == repo_id,
        )
    )
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    finding.status = SastFindingStatus.FALSE_POSITIVE
    finding.dismissed_at = datetime.now(timezone.utc)
    finding.dismissed_by_id = user.id
    await db.commit()
    await db.refresh(finding)
    return finding


# ---------------------------------------------------------------------------
# Project-scoped router
# ---------------------------------------------------------------------------

project_router = APIRouter(
    prefix="/api/projects/{project_id}/sast",
    tags=["sast"],
)


async def _get_project(db: AsyncSession, project_id: uuid.UUID) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@project_router.get("/findings", response_model=list[SastFindingOut])
async def list_project_findings(
    project_id: uuid.UUID,
    severity: str | None = None,
    finding_status: str | None = Query(None, alias="status"),
    file_path: str | None = None,
    rule_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_project(db, project_id)
    q = select(SastFinding).where(SastFinding.project_id == project_id)

    if severity:
        q = q.where(SastFinding.severity == SastSeverity(severity))
    if finding_status:
        q = q.where(SastFinding.status == SastFindingStatus(finding_status))
    else:
        q = q.where(SastFinding.status == SastFindingStatus.OPEN)
    if file_path:
        q = q.where(SastFinding.file_path.ilike(f"%{file_path}%"))
    if rule_id:
        q = q.where(SastFinding.rule_id.ilike(f"%{rule_id}%"))

    q = q.order_by(SastFinding.severity, SastFinding.last_detected_at.desc())
    return (await db.execute(q)).scalars().all()


@project_router.get("/summary", response_model=SastSummary)
async def get_project_summary(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_project(db, project_id)
    return await _build_summary(db, project_id=project_id)


@project_router.get("/runs", response_model=list[SastScanRunOut])
async def list_project_runs(
    project_id: uuid.UUID,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_project(db, project_id)
    q = (
        select(SastScanRun)
        .where(SastScanRun.project_id == project_id)
        .order_by(SastScanRun.created_at.desc())
        .limit(limit)
    )
    return (await db.execute(q)).scalars().all()


# ---------------------------------------------------------------------------
# Rule profile CRUD
# ---------------------------------------------------------------------------

profile_router = APIRouter(
    prefix="/api/sast/profiles",
    tags=["sast"],
)


@profile_router.get("", response_model=list[SastRuleProfileOut])
async def list_profiles(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = select(SastRuleProfile).order_by(SastRuleProfile.is_default.desc(), SastRuleProfile.name)
    return (await db.execute(q)).scalars().all()


@profile_router.post("", response_model=SastRuleProfileOut, status_code=status.HTTP_201_CREATED)
async def create_profile(
    body: SastRuleProfileCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    if body.is_default:
        await _clear_default(db)

    profile = SastRuleProfile(
        name=body.name,
        description=body.description,
        rulesets=body.rulesets,
        custom_rules_yaml=body.custom_rules_yaml,
        scan_branches=body.scan_branches,
        is_default=body.is_default,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@profile_router.put("/{profile_id}", response_model=SastRuleProfileOut)
async def update_profile(
    profile_id: uuid.UUID,
    body: SastRuleProfileUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    profile = await db.get(SastRuleProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    if body.is_default is True:
        await _clear_default(db)

    for field_name in ("name", "description", "rulesets", "custom_rules_yaml", "scan_branches", "is_default"):
        val = getattr(body, field_name)
        if val is not None:
            setattr(profile, field_name, val)

    profile.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)
    return profile


@profile_router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    profile = await db.get(SastRuleProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    await db.delete(profile)
    await db.commit()


# ---------------------------------------------------------------------------
# SAST settings (auto-trigger toggle)
# ---------------------------------------------------------------------------

settings_router = APIRouter(
    prefix="/api/sast/settings",
    tags=["sast"],
)


@settings_router.get("", response_model=SastSettingsOut)
async def get_sast_settings(
    _user: User = Depends(get_current_user),
):
    return SastSettingsOut(auto_sast_on_sync=settings.auto_sast_on_sync)


@settings_router.put("", response_model=SastSettingsOut)
async def update_sast_settings(
    body: SastSettingsUpdate,
    _user: User = Depends(get_current_user),
):
    settings.auto_sast_on_sync = body.auto_sast_on_sync
    return SastSettingsOut(auto_sast_on_sync=settings.auto_sast_on_sync)


# ---------------------------------------------------------------------------
# Report downloads
# ---------------------------------------------------------------------------

@repo_router.get("/report")
async def download_repo_report(
    repo_id: uuid.UUID,
    format: str = Query("json", regex="^(json|csv|pdf)$"),
    report_status: str | None = Query(None, alias="status"),
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    from app.auth.security import decode_token as decode_jwt
    if token:
        payload = decode_jwt(token)
        if payload is None or payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token")
    else:
        raise HTTPException(status_code=401, detail="Token required")
    await _get_repo(db, repo_id)
    from app.services.sast_report import generate_json_report, generate_csv_report, generate_pdf_report
    if format == "csv":
        content = await generate_csv_report(db, repository_id=str(repo_id), status_filter=report_status)
        return Response(content=content, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=sast-report.csv"})
    elif format == "pdf":
        content = await generate_pdf_report(db, repository_id=str(repo_id), status_filter=report_status)
        return Response(content=content, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=sast-report.pdf"})
    else:
        content = await generate_json_report(db, repository_id=str(repo_id), status_filter=report_status)
        return Response(content=content, media_type="application/json", headers={"Content-Disposition": "attachment; filename=sast-report.json"})


@project_router.get("/report")
async def download_project_report(
    project_id: uuid.UUID,
    format: str = Query("json", regex="^(json|csv|pdf)$"),
    report_status: str | None = Query(None, alias="status"),
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    from app.auth.security import decode_token as decode_jwt
    if token:
        payload = decode_jwt(token)
        if payload is None or payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token")
    else:
        raise HTTPException(status_code=401, detail="Token required")
    await _get_project(db, project_id)
    from app.services.sast_report import generate_json_report, generate_csv_report, generate_pdf_report
    if format == "csv":
        content = await generate_csv_report(db, project_id=str(project_id), status_filter=report_status)
        return Response(content=content, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=sast-report.csv"})
    elif format == "pdf":
        content = await generate_pdf_report(db, project_id=str(project_id), status_filter=report_status)
        return Response(content=content, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=sast-report.pdf"})
    else:
        content = await generate_json_report(db, project_id=str(project_id), status_filter=report_status)
        return Response(content=content, media_type="application/json", headers={"Content-Disposition": "attachment; filename=sast-report.json"})


# ---------------------------------------------------------------------------
# Ignored rules CRUD (global)
# ---------------------------------------------------------------------------

ignored_router = APIRouter(
    prefix="/api/sast/ignored-rules",
    tags=["sast"],
)


@ignored_router.get("", response_model=list[SastIgnoredRuleOut])
async def list_global_ignored_rules(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = select(SastIgnoredRule).where(SastIgnoredRule.repository_id.is_(None)).order_by(SastIgnoredRule.rule_id)
    return (await db.execute(q)).scalars().all()


@ignored_router.post("", response_model=SastIgnoredRuleOut, status_code=status.HTTP_201_CREATED)
async def add_global_ignored_rule(
    body: SastIgnoredRuleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = await db.execute(
        select(SastIgnoredRule).where(
            SastIgnoredRule.rule_id == body.rule_id,
            SastIgnoredRule.repository_id.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Rule already ignored globally")

    rule = SastIgnoredRule(rule_id=body.rule_id, reason=body.reason, created_by_id=user.id)
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@ignored_router.delete("/{ignored_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_global_ignored_rule(
    ignored_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    rule = await db.get(SastIgnoredRule, ignored_id)
    if not rule or rule.repository_id is not None:
        raise HTTPException(status_code=404, detail="Global ignored rule not found")
    await db.delete(rule)
    await db.commit()


# ---------------------------------------------------------------------------
# Ignored rules CRUD (per-repo)
# ---------------------------------------------------------------------------

@repo_router.get("/ignored-rules", response_model=list[SastIgnoredRuleOut])
async def list_repo_ignored_rules(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_repo(db, repo_id)
    q = select(SastIgnoredRule).where(
        or_(SastIgnoredRule.repository_id == repo_id, SastIgnoredRule.repository_id.is_(None))
    ).order_by(SastIgnoredRule.repository_id.is_(None).desc(), SastIgnoredRule.rule_id)
    return (await db.execute(q)).scalars().all()


@repo_router.post("/ignored-rules", response_model=SastIgnoredRuleOut, status_code=status.HTTP_201_CREATED)
async def add_repo_ignored_rule(
    repo_id: uuid.UUID,
    body: SastIgnoredRuleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_repo(db, repo_id)
    existing = await db.execute(
        select(SastIgnoredRule).where(
            SastIgnoredRule.rule_id == body.rule_id,
            SastIgnoredRule.repository_id == repo_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Rule already ignored for this repository")

    rule = SastIgnoredRule(rule_id=body.rule_id, repository_id=repo_id, reason=body.reason, created_by_id=user.id)
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@repo_router.delete("/ignored-rules/{ignored_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_repo_ignored_rule(
    repo_id: uuid.UUID,
    ignored_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    rule = await db.get(SastIgnoredRule, ignored_id)
    if not rule or rule.repository_id != repo_id:
        raise HTTPException(status_code=404, detail="Ignored rule not found for this repository")
    await db.delete(rule)
    await db.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _build_summary(
    db: AsyncSession,
    *,
    project_id: uuid.UUID | None = None,
    repository_id: uuid.UUID | None = None,
) -> SastSummary:
    base = select(SastFinding).where(SastFinding.status == SastFindingStatus.OPEN)
    if project_id:
        base = base.where(SastFinding.project_id == project_id)
    if repository_id:
        base = base.where(SastFinding.repository_id == repository_id)

    findings = (await db.execute(base)).scalars().all()

    severity_counts = {s: 0 for s in ("critical", "high", "medium", "low", "info")}
    by_rule: dict[str, int] = {}
    by_file: dict[str, int] = {}

    for f in findings:
        sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        by_rule[f.rule_id] = by_rule.get(f.rule_id, 0) + 1
        by_file[f.file_path] = by_file.get(f.file_path, 0) + 1

    top_rules = dict(sorted(by_rule.items(), key=lambda x: -x[1])[:10])
    top_files = dict(sorted(by_file.items(), key=lambda x: -x[1])[:10])

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    fixed_base = select(func.count()).select_from(SastFinding).where(
        SastFinding.status == SastFindingStatus.FIXED,
    )
    if project_id:
        fixed_base = fixed_base.where(SastFinding.project_id == project_id)
    if repository_id:
        fixed_base = fixed_base.where(SastFinding.repository_id == repository_id)
    fixed_30d = (await db.execute(fixed_base)).scalar() or 0

    return SastSummary(
        total_open=len(findings),
        critical=severity_counts["critical"],
        high=severity_counts["high"],
        medium=severity_counts["medium"],
        low=severity_counts["low"],
        info=severity_counts["info"],
        fixed_30d=fixed_30d,
        by_rule=top_rules,
        by_file=top_files,
    )


async def _clear_default(db: AsyncSession) -> None:
    existing = await db.execute(
        select(SastRuleProfile).where(SastRuleProfile.is_default.is_(True))
    )
    for p in existing.scalars().all():
        p.is_default = False
    await db.flush()
