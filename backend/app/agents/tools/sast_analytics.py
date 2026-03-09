from __future__ import annotations

import logging
from typing import Optional

from langchain_core.tools import tool
from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project, Repository, Contributor, Commit, CommitFile
from app.db.models.sast import (
    SastScanRun, SastFinding, SastScanStatus,
    SastSeverity, SastFindingStatus,
)
from app.agents.tools.base import ToolDefinition
from app.agents.tools.registry import register_tool_category

logger = logging.getLogger(__name__)

CATEGORY = "sast_analytics"

DEFINITIONS = [
    ToolDefinition("get_sast_summary", "SAST Summary", "Security finding counts by severity and status for a project or repo", CATEGORY),
    ToolDefinition("get_sast_findings", "SAST Findings", "List SAST findings with optional severity/status/file/rule filters", CATEGORY),
    ToolDefinition("get_sast_finding_detail", "SAST Finding Detail", "Full detail of a single SAST finding including code snippet and fix", CATEGORY),
    ToolDefinition("get_sast_hotspot_files", "SAST Hotspot Files", "Files with the most security findings ranked by risk", CATEGORY),
    ToolDefinition("get_sast_top_rules", "SAST Top Rules", "Most frequently triggered SAST rules", CATEGORY),
    ToolDefinition("get_sast_cwe_breakdown", "SAST CWE Breakdown", "Findings grouped by CWE weakness category", CATEGORY),
    ToolDefinition("get_sast_scan_history", "SAST Scan History", "Recent scan runs with status, timing, and finding counts", CATEGORY),
    ToolDefinition("get_sast_trend", "SAST Trend", "New vs fixed findings across recent scans", CATEGORY),
    ToolDefinition("get_sast_open_critical", "SAST Open Critical", "All open critical and high severity findings needing attention", CATEGORY),
    ToolDefinition("get_sast_contributor_exposure", "SAST Contributor Exposure", "Contributors whose recent commits touch files with open findings", CATEGORY),
    ToolDefinition("get_sast_fix_rate", "SAST Fix Rate", "Percentage of findings resolved vs total detected over time", CATEGORY),
    ToolDefinition("get_sast_file_risk", "SAST File Risk Score", "Per-file risk score based on finding density and severity", CATEGORY),
]


# ── Helpers ────────────────────────────────────────────────────────────


def _fmt(val) -> str:
    if val is None:
        return "—"
    if isinstance(val, float):
        return f"{val:,.1f}"
    if isinstance(val, int):
        return f"{val:,}"
    return str(val)


def _kv_block(data: dict, title: str = "") -> str:
    lines = []
    if title:
        lines.append(f"**{title}**")
    for k, v in data.items():
        label = k.replace("_", " ").title()
        lines.append(f"- {label}: {_fmt(v)}")
    return "\n".join(lines)


def _table(columns: list[str], rows: list[tuple | list]) -> str:
    if not rows:
        return "No results found."
    header = " | ".join(columns)
    sep = " | ".join("---" for _ in columns)
    lines = [header, sep]
    for row in rows:
        lines.append(" | ".join(_fmt(v) for v in row))
    return "\n".join(lines)


async def _resolve_project(db: AsyncSession, name: str) -> Project | None:
    result = await db.execute(
        select(Project).where(Project.name.ilike(f"%{name}%")).order_by(Project.name).limit(1)
    )
    return result.scalar_one_or_none()


async def _resolve_repository(
    db: AsyncSession, name: str, project_name: str | None = None,
) -> Repository | None:
    stmt = select(Repository).where(Repository.name.ilike(f"%{name}%"))
    if project_name:
        project = await _resolve_project(db, project_name)
        if project:
            stmt = stmt.where(Repository.project_id == project.id)
    result = await db.execute(stmt.order_by(Repository.name).limit(1))
    return result.scalar_one_or_none()


async def _safe(db: AsyncSession, coro):
    try:
        async with db.begin_nested():
            return await coro
    except Exception as e:
        logger.warning("SAST tool query failed: %s", e)
        return f"Error: {e}"


def _scope_filters(project_id=None, repository_id=None, model=SastFinding):
    filters = []
    if repository_id:
        filters.append(model.repository_id == repository_id)
    elif project_id:
        filters.append(model.project_id == project_id)
    return filters


_SEV_WEIGHT = {
    SastSeverity.CRITICAL: 10,
    SastSeverity.HIGH: 5,
    SastSeverity.MEDIUM: 2,
    SastSeverity.LOW: 1,
    SastSeverity.INFO: 0,
}


# ── Tool factory ──────────────────────────────────────────────────────


def _build_sast_tools(db: AsyncSession) -> list:

    @tool
    async def get_sast_summary(
        project_name: Optional[str] = None,
        repo_name: Optional[str] = None,
    ) -> str:
        """Get an overview of SAST security findings for a project or repository.
        Returns counts by severity and status, plus the latest scan info.

        Args:
            project_name: Project name (partial match). Required if repo_name is omitted.
            repo_name: Repository name (partial match). Optional — narrows scope.
        """
        async def _impl():
            project_id = repository_id = None
            label = "All"
            if repo_name:
                repo = await _resolve_repository(db, repo_name, project_name)
                if not repo:
                    return f"No repository found matching '{repo_name}'."
                repository_id = repo.id
                label = repo.name
            elif project_name:
                project = await _resolve_project(db, project_name)
                if not project:
                    return f"No project found matching '{project_name}'."
                project_id = project.id
                label = project.name

            filters = _scope_filters(project_id, repository_id)

            stmt = (
                select(SastFinding.severity, SastFinding.status, func.count().label("cnt"))
                .group_by(SastFinding.severity, SastFinding.status)
            )
            if filters:
                stmt = stmt.where(*filters)
            sev_rows = (await db.execute(stmt)).all()

            if not sev_rows:
                return f"No SAST findings found for '{label}'. Has a scan been run?"

            by_sev: dict[str, int] = {}
            by_status: dict[str, int] = {}
            total = 0
            for r in sev_rows:
                by_sev[r.severity] = by_sev.get(r.severity, 0) + r.cnt
                by_status[r.status] = by_status.get(r.status, 0) + r.cnt
                total += r.cnt

            scan_q = select(SastScanRun).order_by(SastScanRun.created_at.desc()).limit(1)
            if repository_id:
                scan_q = scan_q.where(SastScanRun.repository_id == repository_id)
            elif project_id:
                scan_q = scan_q.where(SastScanRun.project_id == project_id)
            last_scan = (await db.execute(scan_q)).scalar_one_or_none()

            data = {
                "scope": label,
                "total_findings": total,
                "critical": by_sev.get("critical", 0),
                "high": by_sev.get("high", 0),
                "medium": by_sev.get("medium", 0),
                "low": by_sev.get("low", 0),
                "info": by_sev.get("info", 0),
                "open": by_status.get("open", 0),
                "fixed": by_status.get("fixed", 0),
                "dismissed": by_status.get("dismissed", 0),
                "false_positive": by_status.get("false_positive", 0),
            }
            if last_scan:
                data["last_scan_status"] = last_scan.status
                data["last_scan_date"] = str(last_scan.created_at)[:16]
                data["last_scan_findings"] = last_scan.findings_count

            return _kv_block(data, f"SAST Summary: {label}")
        return await _safe(db, _impl())

    @tool
    async def get_sast_findings(
        project_name: Optional[str] = None,
        repo_name: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        file_path: Optional[str] = None,
        rule_id: Optional[str] = None,
        limit: int = 25,
    ) -> str:
        """List SAST findings with optional filters.

        Args:
            project_name: Project name to scope (partial match).
            repo_name: Repository name to scope (partial match).
            severity: Filter by severity: critical, high, medium, low, info.
            status: Filter by status: open, fixed, dismissed, false_positive.
            file_path: Filter by file path (partial match).
            rule_id: Filter by Semgrep rule ID (partial match).
            limit: Max results (default 25, max 50).
        """
        async def _impl():
            project_id = repository_id = None
            if repo_name:
                repo = await _resolve_repository(db, repo_name, project_name)
                if not repo:
                    return f"No repository found matching '{repo_name}'."
                repository_id = repo.id
            elif project_name:
                project = await _resolve_project(db, project_name)
                if not project:
                    return f"No project found matching '{project_name}'."
                project_id = project.id

            filters = _scope_filters(project_id, repository_id)
            if severity:
                filters.append(SastFinding.severity == severity.lower())
            if status:
                filters.append(SastFinding.status == status.lower())
            if file_path:
                filters.append(SastFinding.file_path.ilike(f"%{file_path}%"))
            if rule_id:
                filters.append(SastFinding.rule_id.ilike(f"%{rule_id}%"))

            stmt = (
                select(
                    SastFinding.severity, SastFinding.file_path,
                    SastFinding.start_line, SastFinding.rule_id,
                    SastFinding.message, SastFinding.status,
                    SastFinding.confidence, SastFinding.id,
                    Repository.name.label("repo"),
                )
                .join(Repository, Repository.id == SastFinding.repository_id)
            )
            if filters:
                stmt = stmt.where(*filters)
            stmt = stmt.order_by(
                case(
                    (SastFinding.severity == "critical", 0),
                    (SastFinding.severity == "high", 1),
                    (SastFinding.severity == "medium", 2),
                    (SastFinding.severity == "low", 3),
                    else_=4,
                ),
                SastFinding.last_detected_at.desc(),
            ).limit(min(limit, 50))

            rows = (await db.execute(stmt)).all()
            if not rows:
                return "No SAST findings match the given filters."

            return _table(
                ["Severity", "File", "Line", "Rule", "Message", "Status", "Repo"],
                [
                    (
                        r.severity.upper() if hasattr(r.severity, 'upper') else str(r.severity),
                        r.file_path,
                        r.start_line,
                        (r.rule_id or "")[:40],
                        (r.message or "")[:60],
                        r.status,
                        r.repo,
                    )
                    for r in rows
                ],
            )
        return await _safe(db, _impl())

    @tool
    async def get_sast_finding_detail(finding_id: str) -> str:
        """Get full details of a SAST finding including code snippet and fix suggestion.

        Args:
            finding_id: UUID of the SAST finding.
        """
        async def _impl():
            import uuid as _uuid
            try:
                fid = _uuid.UUID(finding_id)
            except ValueError:
                return f"Invalid finding ID: '{finding_id}'. Must be a valid UUID."

            finding = (await db.execute(
                select(SastFinding)
                .where(SastFinding.id == fid)
            )).scalar_one_or_none()
            if not finding:
                return f"No SAST finding found with ID '{finding_id}'."

            repo = (await db.execute(
                select(Repository.name).where(Repository.id == finding.repository_id)
            )).scalar_one_or_none()

            data = {
                "rule_id": finding.rule_id,
                "severity": finding.severity,
                "confidence": finding.confidence,
                "status": finding.status,
                "repository": repo or "—",
                "file": finding.file_path,
                "lines": f"{finding.start_line}–{finding.end_line}",
                "message": finding.message,
                "first_detected": str(finding.first_detected_at)[:16],
                "last_detected": str(finding.last_detected_at)[:16],
            }
            if finding.cwe_ids:
                data["cwe_ids"] = ", ".join(str(c) for c in finding.cwe_ids)
            if finding.owasp_ids:
                data["owasp_ids"] = ", ".join(str(o) for o in finding.owasp_ids)

            parts = [_kv_block(data, "SAST Finding Detail")]

            if finding.code_snippet:
                parts.append(f"\n**Vulnerable Code:**\n```\n{finding.code_snippet}\n```")
            if finding.fix_suggestion:
                parts.append(f"\n**Suggested Fix:**\n{finding.fix_suggestion}")

            return "\n".join(parts)
        return await _safe(db, _impl())

    @tool
    async def get_sast_hotspot_files(
        project_name: Optional[str] = None,
        repo_name: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        """Get files with the most security findings, ranked by weighted risk score.
        Risk = critical×10 + high×5 + medium×2 + low×1.

        Args:
            project_name: Project name (partial match).
            repo_name: Repository name (partial match).
            limit: Number of files to return (default 20, max 50).
        """
        async def _impl():
            project_id = repository_id = None
            if repo_name:
                repo = await _resolve_repository(db, repo_name, project_name)
                if not repo:
                    return f"No repository found matching '{repo_name}'."
                repository_id = repo.id
            elif project_name:
                project = await _resolve_project(db, project_name)
                if not project:
                    return f"No project found matching '{project_name}'."
                project_id = project.id

            filters = _scope_filters(project_id, repository_id)
            filters.append(SastFinding.status == SastFindingStatus.OPEN)

            risk_score = func.sum(case(
                (SastFinding.severity == "critical", 10),
                (SastFinding.severity == "high", 5),
                (SastFinding.severity == "medium", 2),
                (SastFinding.severity == "low", 1),
                else_=0,
            )).label("risk")

            rows = (await db.execute(
                select(
                    SastFinding.file_path,
                    func.count().label("findings"),
                    risk_score,
                    func.sum(case((SastFinding.severity == "critical", 1), else_=0)).label("crit"),
                    func.sum(case((SastFinding.severity == "high", 1), else_=0)).label("high"),
                    func.sum(case((SastFinding.severity == "medium", 1), else_=0)).label("med"),
                    Repository.name.label("repo"),
                )
                .join(Repository, Repository.id == SastFinding.repository_id)
                .where(*filters)
                .group_by(SastFinding.file_path, Repository.name)
                .order_by(risk_score.desc())
                .limit(min(limit, 50))
            )).all()
            if not rows:
                return "No open SAST findings found."

            return _table(
                ["File", "Repo", "Findings", "Risk Score", "Critical", "High", "Medium"],
                [(r.file_path, r.repo, r.findings, r.risk, r.crit, r.high, r.med) for r in rows],
            )
        return await _safe(db, _impl())

    @tool
    async def get_sast_top_rules(
        project_name: Optional[str] = None,
        repo_name: Optional[str] = None,
        status: str = "open",
        limit: int = 15,
    ) -> str:
        """Get the most frequently triggered SAST rules.

        Args:
            project_name: Project name (partial match).
            repo_name: Repository name (partial match).
            status: Finding status filter: open, fixed, all. Default: open.
            limit: Max rules to return (default 15, max 30).
        """
        async def _impl():
            project_id = repository_id = None
            if repo_name:
                repo = await _resolve_repository(db, repo_name, project_name)
                if not repo:
                    return f"No repository found matching '{repo_name}'."
                repository_id = repo.id
            elif project_name:
                project = await _resolve_project(db, project_name)
                if not project:
                    return f"No project found matching '{project_name}'."
                project_id = project.id

            filters = _scope_filters(project_id, repository_id)
            if status != "all":
                filters.append(SastFinding.status == status.lower())

            rows = (await db.execute(
                select(
                    SastFinding.rule_id,
                    SastFinding.severity,
                    func.count().label("cnt"),
                    func.count(SastFinding.file_path.distinct()).label("files"),
                )
                .where(*filters)
                .group_by(SastFinding.rule_id, SastFinding.severity)
                .order_by(func.count().desc())
                .limit(min(limit, 30))
            )).all()
            if not rows:
                return "No SAST findings match the criteria."

            return _table(
                ["Rule ID", "Severity", "Occurrences", "Files Affected"],
                [(r.rule_id, r.severity, r.cnt, r.files) for r in rows],
            )
        return await _safe(db, _impl())

    @tool
    async def get_sast_cwe_breakdown(
        project_name: Optional[str] = None,
        repo_name: Optional[str] = None,
    ) -> str:
        """Get SAST findings grouped by CWE weakness category.
        Shows which vulnerability classes are most prevalent.

        Args:
            project_name: Project name (partial match).
            repo_name: Repository name (partial match).
        """
        async def _impl():
            project_id = repository_id = None
            if repo_name:
                repo = await _resolve_repository(db, repo_name, project_name)
                if not repo:
                    return f"No repository found matching '{repo_name}'."
                repository_id = repo.id
            elif project_name:
                project = await _resolve_project(db, project_name)
                if not project:
                    return f"No project found matching '{project_name}'."
                project_id = project.id

            filters = _scope_filters(project_id, repository_id)
            filters.append(SastFinding.status == SastFindingStatus.OPEN)
            filters.append(SastFinding.cwe_ids.isnot(None))

            findings = (await db.execute(
                select(SastFinding.cwe_ids, SastFinding.severity)
                .where(*filters)
            )).all()
            if not findings:
                return "No open SAST findings with CWE classifications found."

            cwe_counts: dict[str, dict] = {}
            for row in findings:
                for cwe in (row.cwe_ids or []):
                    cwe_str = str(cwe)
                    entry = cwe_counts.setdefault(cwe_str, {"total": 0, "crit": 0, "high": 0})
                    entry["total"] += 1
                    sev = row.severity if isinstance(row.severity, str) else row.severity.value
                    if sev == "critical":
                        entry["crit"] += 1
                    elif sev == "high":
                        entry["high"] += 1

            sorted_cwes = sorted(cwe_counts.items(), key=lambda x: x[1]["total"], reverse=True)[:20]
            return _table(
                ["CWE", "Total Open", "Critical", "High"],
                [(cwe, d["total"], d["crit"], d["high"]) for cwe, d in sorted_cwes],
            )
        return await _safe(db, _impl())

    @tool
    async def get_sast_scan_history(
        project_name: Optional[str] = None,
        repo_name: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        """Get recent SAST scan runs with status, timing, and finding counts.

        Args:
            project_name: Project name (partial match).
            repo_name: Repository name (partial match).
            limit: Max runs to return (default 10, max 25).
        """
        async def _impl():
            filters: list = []
            if repo_name:
                repo = await _resolve_repository(db, repo_name, project_name)
                if not repo:
                    return f"No repository found matching '{repo_name}'."
                filters.append(SastScanRun.repository_id == repo.id)
            elif project_name:
                project = await _resolve_project(db, project_name)
                if not project:
                    return f"No project found matching '{project_name}'."
                filters.append(SastScanRun.project_id == project.id)

            stmt = (
                select(
                    SastScanRun.status, SastScanRun.branch,
                    SastScanRun.findings_count,
                    SastScanRun.started_at, SastScanRun.finished_at,
                    SastScanRun.tool, SastScanRun.error_message,
                    Repository.name.label("repo"),
                )
                .join(Repository, Repository.id == SastScanRun.repository_id)
                .order_by(SastScanRun.created_at.desc())
                .limit(min(limit, 25))
            )
            if filters:
                stmt = stmt.where(*filters)

            rows = (await db.execute(stmt)).all()
            if not rows:
                return "No SAST scan runs found."

            def _duration(r):
                if r.started_at and r.finished_at:
                    secs = (r.finished_at - r.started_at).total_seconds()
                    return f"{secs:.0f}s"
                return "—"

            return _table(
                ["Repo", "Status", "Branch", "Findings", "Duration", "Tool", "Date"],
                [
                    (
                        r.repo, r.status, r.branch or "—",
                        r.findings_count, _duration(r), r.tool,
                        str(r.started_at)[:16] if r.started_at else "—",
                    )
                    for r in rows
                ],
            )
        return await _safe(db, _impl())

    @tool
    async def get_sast_trend(
        project_name: Optional[str] = None,
        repo_name: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        """Show new vs fixed findings across recent completed scans.
        Helps assess whether security posture is improving or degrading.

        Args:
            project_name: Project name (partial match).
            repo_name: Repository name (partial match).
            limit: Number of recent scans to analyze (default 10, max 20).
        """
        async def _impl():
            filters: list = [SastScanRun.status == SastScanStatus.COMPLETED]
            if repo_name:
                repo = await _resolve_repository(db, repo_name, project_name)
                if not repo:
                    return f"No repository found matching '{repo_name}'."
                filters.append(SastScanRun.repository_id == repo.id)
            elif project_name:
                project = await _resolve_project(db, project_name)
                if not project:
                    return f"No project found matching '{project_name}'."
                filters.append(SastScanRun.project_id == project.id)

            runs = (await db.execute(
                select(SastScanRun.id, SastScanRun.finished_at, SastScanRun.findings_count)
                .where(*filters)
                .order_by(SastScanRun.finished_at.desc())
                .limit(min(limit, 20))
            )).all()
            if not runs:
                return "No completed SAST scans found."

            rows = []
            for run in reversed(runs):
                new_count = await db.scalar(
                    select(func.count()).select_from(SastFinding)
                    .where(
                        SastFinding.scan_run_id == run.id,
                        SastFinding.first_detected_at == SastFinding.last_detected_at,
                    )
                ) or 0
                fixed_count = await db.scalar(
                    select(func.count()).select_from(SastFinding)
                    .where(
                        SastFinding.scan_run_id == run.id,
                        SastFinding.status == SastFindingStatus.FIXED,
                    )
                ) or 0
                rows.append((
                    str(run.finished_at)[:10] if run.finished_at else "—",
                    run.findings_count,
                    new_count,
                    fixed_count,
                ))

            return _table(
                ["Scan Date", "Total Findings", "New", "Fixed"],
                rows,
            )
        return await _safe(db, _impl())

    @tool
    async def get_sast_open_critical(
        project_name: Optional[str] = None,
        repo_name: Optional[str] = None,
    ) -> str:
        """List all open critical and high severity findings that need immediate attention.
        Results are ordered by severity then recency.

        Args:
            project_name: Project name (partial match).
            repo_name: Repository name (partial match).
        """
        async def _impl():
            project_id = repository_id = None
            if repo_name:
                repo = await _resolve_repository(db, repo_name, project_name)
                if not repo:
                    return f"No repository found matching '{repo_name}'."
                repository_id = repo.id
            elif project_name:
                project = await _resolve_project(db, project_name)
                if not project:
                    return f"No project found matching '{project_name}'."
                project_id = project.id

            filters = _scope_filters(project_id, repository_id)
            filters.append(SastFinding.status == SastFindingStatus.OPEN)
            filters.append(SastFinding.severity.in_(["critical", "high"]))

            rows = (await db.execute(
                select(
                    SastFinding.severity, SastFinding.rule_id,
                    SastFinding.file_path, SastFinding.start_line,
                    SastFinding.message, SastFinding.confidence,
                    SastFinding.last_detected_at,
                    Repository.name.label("repo"),
                )
                .join(Repository, Repository.id == SastFinding.repository_id)
                .where(*filters)
                .order_by(
                    case((SastFinding.severity == "critical", 0), else_=1),
                    SastFinding.last_detected_at.desc(),
                )
                .limit(50)
            )).all()
            if not rows:
                return "No open critical or high severity findings. Your security posture looks healthy."

            return _table(
                ["Severity", "Rule", "File", "Line", "Message", "Confidence", "Repo"],
                [
                    (
                        r.severity.upper() if hasattr(r.severity, 'upper') else str(r.severity),
                        (r.rule_id or "")[:35],
                        r.file_path,
                        r.start_line,
                        (r.message or "")[:50],
                        r.confidence,
                        r.repo,
                    )
                    for r in rows
                ],
            )
        return await _safe(db, _impl())

    @tool
    async def get_sast_contributor_exposure(
        project_name: Optional[str] = None,
        repo_name: Optional[str] = None,
        days: int = 30,
        limit: int = 15,
    ) -> str:
        """Show contributors whose recent commits touch files with open SAST findings.
        Helps identify who can best remediate each vulnerability.

        Args:
            project_name: Project name (partial match).
            repo_name: Repository name (partial match).
            days: Look-back window for recent commits (default 30).
            limit: Max contributors (default 15, max 30).
        """
        async def _impl():
            from datetime import date, timedelta
            cutoff = date.today() - timedelta(days=days)

            project_id = repository_id = None
            if repo_name:
                repo = await _resolve_repository(db, repo_name, project_name)
                if not repo:
                    return f"No repository found matching '{repo_name}'."
                repository_id = repo.id
            elif project_name:
                project = await _resolve_project(db, project_name)
                if not project:
                    return f"No project found matching '{project_name}'."
                project_id = project.id

            finding_filters = _scope_filters(project_id, repository_id)
            finding_filters.append(SastFinding.status == SastFindingStatus.OPEN)

            vuln_files = (
                select(SastFinding.file_path, SastFinding.repository_id)
                .where(*finding_filters)
                .distinct()
                .subquery()
            )

            commit_filters = [
                Commit.authored_at >= cutoff,
                CommitFile.file_path == vuln_files.c.file_path,
                Commit.repository_id == vuln_files.c.repository_id,
            ]

            rows = (await db.execute(
                select(
                    Contributor.canonical_name,
                    func.count(CommitFile.file_path.distinct()).label("vuln_files_touched"),
                    func.count(Commit.id.distinct()).label("commits"),
                    func.max(Commit.authored_at).label("last_commit"),
                )
                .join(Commit, Commit.id == CommitFile.commit_id)
                .join(Contributor, Contributor.id == Commit.contributor_id)
                .join(vuln_files, and_(*commit_filters))
                .group_by(Contributor.id, Contributor.canonical_name)
                .order_by(func.count(CommitFile.file_path.distinct()).desc())
                .limit(min(limit, 30))
            )).all()
            if not rows:
                return "No recent contributors found touching files with open findings."

            return _table(
                ["Contributor", "Vuln Files Touched", "Recent Commits", "Last Commit"],
                [
                    (r.canonical_name, r.vuln_files_touched, r.commits,
                     str(r.last_commit)[:10] if r.last_commit else "—")
                    for r in rows
                ],
            )
        return await _safe(db, _impl())

    @tool
    async def get_sast_fix_rate(
        project_name: Optional[str] = None,
        repo_name: Optional[str] = None,
    ) -> str:
        """Get the SAST finding resolution rate — what percentage of all-time
        detected findings have been fixed, dismissed, or marked false positive.

        Args:
            project_name: Project name (partial match).
            repo_name: Repository name (partial match).
        """
        async def _impl():
            project_id = repository_id = None
            label = "All"
            if repo_name:
                repo = await _resolve_repository(db, repo_name, project_name)
                if not repo:
                    return f"No repository found matching '{repo_name}'."
                repository_id = repo.id
                label = repo.name
            elif project_name:
                project = await _resolve_project(db, project_name)
                if not project:
                    return f"No project found matching '{project_name}'."
                project_id = project.id
                label = project.name

            filters = _scope_filters(project_id, repository_id)

            status_rows = (await db.execute(
                select(SastFinding.status, func.count().label("cnt"))
                .where(*filters)
                .group_by(SastFinding.status)
            )).all()
            if not status_rows:
                return f"No SAST findings found for '{label}'."

            by_status = {r.status: r.cnt for r in status_rows}
            total = sum(by_status.values())
            resolved = by_status.get("fixed", 0) + by_status.get("dismissed", 0) + by_status.get("false_positive", 0)
            rate = round(resolved / total * 100, 1) if total else 0

            return _kv_block({
                "scope": label,
                "total_detected_all_time": total,
                "open": by_status.get("open", 0),
                "fixed": by_status.get("fixed", 0),
                "dismissed": by_status.get("dismissed", 0),
                "false_positive": by_status.get("false_positive", 0),
                "resolution_rate": f"{rate}%",
                "mean_time_to_fix": "—",
            }, f"SAST Fix Rate: {label}")
        return await _safe(db, _impl())

    @tool
    async def get_sast_file_risk(
        project_name: Optional[str] = None,
        repo_name: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        """Compute a per-file risk score combining SAST finding severity with
        code churn (commit frequency). Files that are both vulnerable and
        frequently changed are the highest priority to fix.

        Risk = finding_weight × (1 + log2(commits)).

        Args:
            project_name: Project name (partial match).
            repo_name: Repository name (partial match).
            limit: Number of files to return (default 20, max 50).
        """
        async def _impl():
            import math

            project_id = repository_id = None
            if repo_name:
                repo = await _resolve_repository(db, repo_name, project_name)
                if not repo:
                    return f"No repository found matching '{repo_name}'."
                repository_id = repo.id
            elif project_name:
                project = await _resolve_project(db, project_name)
                if not project:
                    return f"No project found matching '{project_name}'."
                project_id = project.id

            finding_filters = _scope_filters(project_id, repository_id)
            finding_filters.append(SastFinding.status == SastFindingStatus.OPEN)

            file_findings = (await db.execute(
                select(
                    SastFinding.file_path,
                    SastFinding.repository_id,
                    func.count().label("findings"),
                    func.sum(case(
                        (SastFinding.severity == "critical", 10),
                        (SastFinding.severity == "high", 5),
                        (SastFinding.severity == "medium", 2),
                        (SastFinding.severity == "low", 1),
                        else_=0,
                    )).label("sev_weight"),
                )
                .where(*finding_filters)
                .group_by(SastFinding.file_path, SastFinding.repository_id)
            )).all()
            if not file_findings:
                return "No open SAST findings found."

            results = []
            for ff in file_findings:
                churn = await db.scalar(
                    select(func.count(CommitFile.commit_id.distinct()))
                    .join(Commit, Commit.id == CommitFile.commit_id)
                    .where(
                        CommitFile.file_path == ff.file_path,
                        Commit.repository_id == ff.repository_id,
                    )
                ) or 0
                risk = round(float(ff.sev_weight) * (1 + math.log2(max(churn, 1))), 1)
                results.append((ff.file_path, ff.findings, ff.sev_weight, churn, risk))

            results.sort(key=lambda x: x[4], reverse=True)
            return _table(
                ["File", "Open Findings", "Severity Weight", "Commits (churn)", "Risk Score"],
                results[:min(limit, 50)],
            )
        return await _safe(db, _impl())

    return [
        get_sast_summary,
        get_sast_findings,
        get_sast_finding_detail,
        get_sast_hotspot_files,
        get_sast_top_rules,
        get_sast_cwe_breakdown,
        get_sast_scan_history,
        get_sast_trend,
        get_sast_open_critical,
        get_sast_contributor_exposure,
        get_sast_fix_rate,
        get_sast_file_risk,
    ]


register_tool_category(CATEGORY, DEFINITIONS, _build_sast_tools)
