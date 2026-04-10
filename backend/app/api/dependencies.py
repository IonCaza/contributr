import json
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.db.base import get_db
from app.db.models import User, Project, Repository
from app.services.sync_logger import stream_log_events
from app.db.models.dependency import (
    DepScanRun, DepScanStatus, DependencyFinding, DepFindingStatus,
    DepFindingSeverity,
)
from app.auth.dependencies import get_current_user, get_accessible_project_ids


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DepScanRunOut(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    project_id: uuid.UUID
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    findings_count: int
    vulnerable_count: int
    outdated_count: int
    error_message: str | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class DepFindingOut(BaseModel):
    id: uuid.UUID
    scan_run_id: uuid.UUID
    repository_id: uuid.UUID
    project_id: uuid.UUID
    file_path: str
    file_type: str
    ecosystem: str
    package_name: str
    current_version: str | None = None
    latest_version: str | None = None
    is_outdated: bool
    is_vulnerable: bool
    is_direct: bool
    severity: str
    vulnerabilities: list | None = None
    license: str | None = Field(None, validation_alias="dep_license")
    status: str
    first_detected_at: datetime
    last_detected_at: datetime
    dismissed_at: datetime | None = None
    dismissed_by_id: uuid.UUID | None = None
    model_config = {"from_attributes": True}


class DepSummary(BaseModel):
    total_packages: int
    vulnerable: int
    outdated: int
    up_to_date: int
    severity_critical: int
    severity_high: int
    severity_medium: int
    severity_low: int
    by_ecosystem: dict[str, int]
    by_file: dict[str, int]


class PaginatedFindings(BaseModel):
    items: list[DepFindingOut]
    total: int
    page: int
    page_size: int


class DepScanTrigger(BaseModel):
    pass


class DepSettingsOut(BaseModel):
    auto_dep_scan_on_sync: bool


class DepSettingsUpdate(BaseModel):
    auto_dep_scan_on_sync: bool


# ---------------------------------------------------------------------------
# Repository-scoped router
# ---------------------------------------------------------------------------

repo_router = APIRouter(
    prefix="/api/repositories/{repo_id}/dependencies",
    tags=["dependencies"],
)


async def _get_repo(db: AsyncSession, repo_id: uuid.UUID, accessible: set[uuid.UUID] | None = None) -> Repository:
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if accessible is not None and repo.project_id not in accessible:
        raise HTTPException(status_code=403, detail="No access to this project")
    return repo


@repo_router.post("/scan", response_model=DepScanRunOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_scan(
    repo_id: uuid.UUID,
    body: DepScanTrigger | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    accessible: set[uuid.UUID] | None = Depends(get_accessible_project_ids),
):
    repo = await _get_repo(db, repo_id, accessible)

    stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    stale_q = select(DepScanRun).where(
        DepScanRun.repository_id == repo_id,
        DepScanRun.status.in_([DepScanStatus.QUEUED, DepScanStatus.RUNNING]),
        DepScanRun.created_at < stale_cutoff,
    )
    for sr in (await db.execute(stale_q)).scalars().all():
        sr.status = DepScanStatus.FAILED
        sr.error_message = "Timed out (stale scan detected)"
        sr.finished_at = datetime.now(timezone.utc)
    await db.flush()

    scan_run = DepScanRun(
        repository_id=repo.id,
        project_id=repo.project_id,
        status=DepScanStatus.QUEUED,
    )
    db.add(scan_run)
    await db.commit()
    await db.refresh(scan_run)

    from app.workers.tasks import run_dependency_scan
    run_dependency_scan.delay(str(scan_run.id), str(repo.id))
    return scan_run


@repo_router.get("/findings", response_model=PaginatedFindings)
async def list_repo_findings(
    repo_id: uuid.UUID,
    severity: str | None = None,
    ecosystem: str | None = None,
    outdated: bool | None = None,
    vulnerable: bool | None = None,
    file_path: str | None = None,
    finding_status: str | None = Query(None, alias="status"),
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    accessible: set[uuid.UUID] | None = Depends(get_accessible_project_ids),
):
    await _get_repo(db, repo_id, accessible)
    q = select(DependencyFinding).where(DependencyFinding.repository_id == repo_id)

    if search:
        q = q.where(DependencyFinding.package_name.ilike(f"%{search}%"))
    if severity:
        q = q.where(DependencyFinding.severity == DepFindingSeverity(severity))
    if ecosystem:
        q = q.where(DependencyFinding.ecosystem == ecosystem)
    if outdated is not None:
        q = q.where(DependencyFinding.is_outdated == outdated)
    if vulnerable is not None:
        q = q.where(DependencyFinding.is_vulnerable == vulnerable)
    if file_path:
        q = q.where(DependencyFinding.file_path.ilike(f"%{file_path}%"))
    if finding_status:
        q = q.where(DependencyFinding.status == DepFindingStatus(finding_status))
    else:
        q = q.where(DependencyFinding.status == DepFindingStatus.ACTIVE)

    q = q.order_by(DependencyFinding.severity, DependencyFinding.is_vulnerable.desc(), DependencyFinding.package_name)

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.offset((page - 1) * page_size).limit(page_size)
    return PaginatedFindings(
        items=list((await db.execute(q)).scalars().all()),
        total=total,
        page=page,
        page_size=page_size,
    )


@repo_router.get("/summary", response_model=DepSummary)
async def get_repo_summary(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    accessible: set[uuid.UUID] | None = Depends(get_accessible_project_ids),
):
    await _get_repo(db, repo_id, accessible)
    return await _build_summary(db, repository_id=repo_id)


@repo_router.get("/runs", response_model=list[DepScanRunOut])
async def list_repo_runs(
    repo_id: uuid.UUID,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    accessible: set[uuid.UUID] | None = Depends(get_accessible_project_ids),
):
    await _get_repo(db, repo_id, accessible)
    q = (
        select(DepScanRun)
        .where(DepScanRun.repository_id == repo_id)
        .order_by(DepScanRun.created_at.desc())
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

    list_key = f"sync:logs:dep-{run_id}"
    channel_key = f"sync:logs:live:dep-{run_id}"

    return EventSourceResponse(stream_log_events(list_key, channel_key, request))


@repo_router.patch("/findings/{finding_id}/dismiss", response_model=DepFindingOut)
async def dismiss_finding(
    repo_id: uuid.UUID,
    finding_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DependencyFinding).where(
            DependencyFinding.id == finding_id,
            DependencyFinding.repository_id == repo_id,
        )
    )
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    finding.status = DepFindingStatus.DISMISSED
    finding.dismissed_at = datetime.now(timezone.utc)
    finding.dismissed_by_id = user.id
    await db.commit()
    await db.refresh(finding)
    return finding


@repo_router.get("/report")
async def download_repo_report(
    repo_id: uuid.UUID,
    format: str = Query("json", pattern="^(json|csv)$"),
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    from app.auth.security import decode_token as decode_jwt
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    payload = decode_jwt(token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token")

    await _get_repo(db, repo_id)
    content = await _generate_report(db, format, repository_id=repo_id)
    media = "text/csv" if format == "csv" else "application/json"
    ext = format
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename=dependency-report.{ext}"},
    )


# ---------------------------------------------------------------------------
# Project-scoped router
# ---------------------------------------------------------------------------

project_router = APIRouter(
    prefix="/api/projects/{project_id}/dependencies",
    tags=["dependencies"],
)


async def _get_project(db: AsyncSession, project_id: uuid.UUID, accessible: set[uuid.UUID] | None = None) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if accessible is not None and project.id not in accessible:
        raise HTTPException(status_code=403, detail="No access to this project")
    return project


@project_router.get("/findings", response_model=PaginatedFindings)
async def list_project_findings(
    project_id: uuid.UUID,
    severity: str | None = None,
    ecosystem: str | None = None,
    outdated: bool | None = None,
    vulnerable: bool | None = None,
    file_path: str | None = None,
    finding_status: str | None = Query(None, alias="status"),
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    accessible: set[uuid.UUID] | None = Depends(get_accessible_project_ids),
):
    await _get_project(db, project_id, accessible)
    q = select(DependencyFinding).where(DependencyFinding.project_id == project_id)

    if search:
        q = q.where(DependencyFinding.package_name.ilike(f"%{search}%"))
    if severity:
        q = q.where(DependencyFinding.severity == DepFindingSeverity(severity))
    if ecosystem:
        q = q.where(DependencyFinding.ecosystem == ecosystem)
    if outdated is not None:
        q = q.where(DependencyFinding.is_outdated == outdated)
    if vulnerable is not None:
        q = q.where(DependencyFinding.is_vulnerable == vulnerable)
    if file_path:
        q = q.where(DependencyFinding.file_path.ilike(f"%{file_path}%"))
    if finding_status:
        q = q.where(DependencyFinding.status == DepFindingStatus(finding_status))
    else:
        q = q.where(DependencyFinding.status == DepFindingStatus.ACTIVE)

    q = q.order_by(DependencyFinding.severity, DependencyFinding.is_vulnerable.desc(), DependencyFinding.package_name)

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.offset((page - 1) * page_size).limit(page_size)
    return PaginatedFindings(
        items=list((await db.execute(q)).scalars().all()),
        total=total,
        page=page,
        page_size=page_size,
    )


@project_router.get("/summary", response_model=DepSummary)
async def get_project_summary(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    accessible: set[uuid.UUID] | None = Depends(get_accessible_project_ids),
):
    await _get_project(db, project_id, accessible)
    return await _build_summary(db, project_id=project_id)


@project_router.get("/runs", response_model=list[DepScanRunOut])
async def list_project_runs(
    project_id: uuid.UUID,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    accessible: set[uuid.UUID] | None = Depends(get_accessible_project_ids),
):
    await _get_project(db, project_id, accessible)
    q = (
        select(DepScanRun)
        .where(DepScanRun.project_id == project_id)
        .order_by(DepScanRun.created_at.desc())
        .limit(limit)
    )
    return (await db.execute(q)).scalars().all()


@project_router.get("/report")
async def download_project_report(
    project_id: uuid.UUID,
    format: str = Query("json", pattern="^(json|csv)$"),
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    from app.auth.security import decode_token as decode_jwt
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    payload = decode_jwt(token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token")

    await _get_project(db, project_id)
    content = await _generate_report(db, format, project_id=project_id)
    media = "text/csv" if format == "csv" else "application/json"
    ext = format
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename=dependency-report.{ext}"},
    )


# ---------------------------------------------------------------------------
# Settings router
# ---------------------------------------------------------------------------

settings_router = APIRouter(
    prefix="/api/dependencies/settings",
    tags=["dependencies"],
)


@settings_router.get("", response_model=DepSettingsOut)
async def get_dep_settings(
    _user: User = Depends(get_current_user),
):
    return DepSettingsOut(auto_dep_scan_on_sync=settings.auto_dep_scan_on_sync)


@settings_router.put("", response_model=DepSettingsOut)
async def update_dep_settings(
    body: DepSettingsUpdate,
    _user: User = Depends(get_current_user),
):
    settings.auto_dep_scan_on_sync = body.auto_dep_scan_on_sync
    return DepSettingsOut(auto_dep_scan_on_sync=settings.auto_dep_scan_on_sync)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _build_summary(
    db: AsyncSession,
    *,
    project_id: uuid.UUID | None = None,
    repository_id: uuid.UUID | None = None,
) -> DepSummary:
    base = select(DependencyFinding).where(DependencyFinding.status == DepFindingStatus.ACTIVE)
    if project_id:
        base = base.where(DependencyFinding.project_id == project_id)
    if repository_id:
        base = base.where(DependencyFinding.repository_id == repository_id)

    findings = (await db.execute(base)).scalars().all()

    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    by_ecosystem: dict[str, int] = {}
    by_file: dict[str, int] = {}
    vulnerable = 0
    outdated = 0
    up_to_date = 0

    for f in findings:
        if f.is_vulnerable:
            vulnerable += 1
            sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
            if sev in severity_counts:
                severity_counts[sev] += 1
        if f.is_outdated:
            outdated += 1
        if not f.is_outdated and not f.is_vulnerable:
            up_to_date += 1
        by_ecosystem[f.ecosystem] = by_ecosystem.get(f.ecosystem, 0) + 1
        by_file[f.file_path] = by_file.get(f.file_path, 0) + 1

    top_files = dict(sorted(by_file.items(), key=lambda x: -x[1])[:10])

    return DepSummary(
        total_packages=len(findings),
        vulnerable=vulnerable,
        outdated=outdated,
        up_to_date=up_to_date,
        severity_critical=severity_counts["critical"],
        severity_high=severity_counts["high"],
        severity_medium=severity_counts["medium"],
        severity_low=severity_counts["low"],
        by_ecosystem=by_ecosystem,
        by_file=top_files,
    )


async def _generate_report(
    db: AsyncSession,
    format: str,
    *,
    project_id: uuid.UUID | None = None,
    repository_id: uuid.UUID | None = None,
) -> str | bytes:
    base = select(DependencyFinding).where(DependencyFinding.status == DepFindingStatus.ACTIVE)
    if project_id:
        base = base.where(DependencyFinding.project_id == project_id)
    if repository_id:
        base = base.where(DependencyFinding.repository_id == repository_id)

    base = base.order_by(DependencyFinding.severity, DependencyFinding.package_name)
    findings = (await db.execute(base)).scalars().all()

    if format == "csv":
        import csv
        import io
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "package_name", "ecosystem", "file_path", "current_version",
            "latest_version", "is_outdated", "is_vulnerable", "severity",
            "vulnerabilities",
        ])
        for f in findings:
            vuln_ids = ", ".join(v.get("id", "") for v in (f.vulnerabilities or []))
            writer.writerow([
                f.package_name, f.ecosystem, f.file_path, f.current_version or "",
                f.latest_version or "", f.is_outdated, f.is_vulnerable,
                f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                vuln_ids,
            ])
        return buf.getvalue()
    else:
        rows = []
        for f in findings:
            rows.append({
                "package_name": f.package_name,
                "ecosystem": f.ecosystem,
                "file_path": f.file_path,
                "current_version": f.current_version,
                "latest_version": f.latest_version,
                "is_outdated": f.is_outdated,
                "is_vulnerable": f.is_vulnerable,
                "severity": f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                "vulnerabilities": f.vulnerabilities or [],
            })
        return json.dumps(rows, indent=2, default=str)
