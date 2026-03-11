from __future__ import annotations

import logging
from typing import Optional

from langchain_core.tools import tool
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project, Repository
from app.db.models.dependency import (
    DependencyFinding, DepFindingStatus, DepFindingSeverity,
    DepScanRun, DepScanStatus,
)
from app.agents.tools.base import ToolDefinition
from app.agents.tools.registry import register_tool_category

logger = logging.getLogger(__name__)

CATEGORY = "dependency_analytics"

DEFINITIONS = [
    ToolDefinition("get_dependency_summary", "Dependency Summary", "Get dependency scan summary for a project or repo: total packages, vulnerable, outdated counts, ecosystem breakdown", CATEGORY),
    ToolDefinition("get_vulnerable_dependencies", "Vulnerable Dependencies", "List packages with known CVE vulnerabilities in a project or repo", CATEGORY),
    ToolDefinition("get_outdated_dependencies", "Outdated Dependencies", "List packages behind the latest version in a project or repo", CATEGORY),
    ToolDefinition("get_dependency_files", "Dependency Files", "List discovered dependency manifest files and their ecosystems for a project or repo", CATEGORY),
    ToolDefinition("get_dependency_scan_history", "Dependency Scan History", "Get recent dependency scan runs and their results", CATEGORY),
    ToolDefinition("search_dependency", "Search Dependency", "Search for a specific package across all repos by name", CATEGORY),
]


def _build_dependency_tools(db: AsyncSession) -> list:

    @tool
    async def get_dependency_summary(
        project_name: Optional[str] = None,
        repository_name: Optional[str] = None,
    ) -> str:
        """Get dependency scan summary: total packages, vulnerable, outdated, ecosystem breakdown.
        Provide project_name or repository_name to scope results."""
        scope_filter = await _resolve_scope(db, project_name, repository_name)
        if isinstance(scope_filter, str):
            return scope_filter

        q = select(DependencyFinding).where(
            DependencyFinding.status == DepFindingStatus.ACTIVE,
            *scope_filter,
        )
        findings = (await db.execute(q)).scalars().all()

        if not findings:
            return "No dependency findings found. Run a dependency scan first."

        total = len(findings)
        vulnerable = sum(1 for f in findings if f.is_vulnerable)
        outdated = sum(1 for f in findings if f.is_outdated)
        up_to_date = sum(1 for f in findings if not f.is_outdated and not f.is_vulnerable)

        by_eco: dict[str, int] = {}
        sev_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for f in findings:
            by_eco[f.ecosystem] = by_eco.get(f.ecosystem, 0) + 1
            if f.is_vulnerable:
                sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
                if sev in sev_counts:
                    sev_counts[sev] += 1

        eco_str = ", ".join(f"{k}: {v}" for k, v in sorted(by_eco.items(), key=lambda x: -x[1]))
        health = round((up_to_date / total) * 100) if total else 0

        return (
            f"Dependency Summary ({total} packages, {health}% healthy):\n"
            f"  Vulnerable: {vulnerable} (Critical: {sev_counts['critical']}, High: {sev_counts['high']}, "
            f"Medium: {sev_counts['medium']}, Low: {sev_counts['low']})\n"
            f"  Outdated: {outdated}\n"
            f"  Up to date: {up_to_date}\n"
            f"  Ecosystems: {eco_str}"
        )

    @tool
    async def get_vulnerable_dependencies(
        project_name: Optional[str] = None,
        repository_name: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        """List packages with known CVE vulnerabilities. Optionally filter by severity (critical/high/medium/low)."""
        scope_filter = await _resolve_scope(db, project_name, repository_name)
        if isinstance(scope_filter, str):
            return scope_filter

        q = select(DependencyFinding).where(
            DependencyFinding.status == DepFindingStatus.ACTIVE,
            DependencyFinding.is_vulnerable.is_(True),
            *scope_filter,
        )
        if severity:
            try:
                q = q.where(DependencyFinding.severity == DepFindingSeverity(severity.lower()))
            except ValueError:
                pass
        q = q.order_by(DependencyFinding.severity).limit(limit)
        findings = (await db.execute(q)).scalars().all()

        if not findings:
            return "No vulnerable dependencies found."

        lines = [f"Vulnerable dependencies ({len(findings)} found):"]
        for f in findings:
            vuln_ids = ", ".join(v.get("id", "?") for v in (f.vulnerabilities or [])[:3])
            sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
            lines.append(
                f"  [{sev.upper()}] {f.package_name} {f.current_version or '?'} "
                f"({f.ecosystem}, {f.file_path}) — {vuln_ids}"
            )
        return "\n".join(lines)

    @tool
    async def get_outdated_dependencies(
        project_name: Optional[str] = None,
        repository_name: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        """List packages behind the latest version."""
        scope_filter = await _resolve_scope(db, project_name, repository_name)
        if isinstance(scope_filter, str):
            return scope_filter

        q = select(DependencyFinding).where(
            DependencyFinding.status == DepFindingStatus.ACTIVE,
            DependencyFinding.is_outdated.is_(True),
            *scope_filter,
        ).order_by(DependencyFinding.ecosystem, DependencyFinding.package_name).limit(limit)
        findings = (await db.execute(q)).scalars().all()

        if not findings:
            return "No outdated dependencies found."

        lines = [f"Outdated dependencies ({len(findings)} found):"]
        for f in findings:
            lines.append(
                f"  {f.package_name}: {f.current_version or '?'} → {f.latest_version or '?'} "
                f"({f.ecosystem}, {f.file_path})"
            )
        return "\n".join(lines)

    @tool
    async def get_dependency_files(
        project_name: Optional[str] = None,
        repository_name: Optional[str] = None,
    ) -> str:
        """List discovered dependency manifest files and their ecosystems."""
        scope_filter = await _resolve_scope(db, project_name, repository_name)
        if isinstance(scope_filter, str):
            return scope_filter

        q = (
            select(
                DependencyFinding.file_path,
                DependencyFinding.ecosystem,
                DependencyFinding.file_type,
                func.count().label("pkg_count"),
            )
            .where(DependencyFinding.status == DepFindingStatus.ACTIVE, *scope_filter)
            .group_by(DependencyFinding.file_path, DependencyFinding.ecosystem, DependencyFinding.file_type)
            .order_by(DependencyFinding.ecosystem, DependencyFinding.file_path)
        )
        rows = (await db.execute(q)).all()

        if not rows:
            return "No dependency files found. Run a dependency scan first."

        lines = [f"Dependency files ({len(rows)} files):"]
        for r in rows:
            lines.append(f"  {r.file_path} — {r.ecosystem} ({r.pkg_count} packages)")
        return "\n".join(lines)

    @tool
    async def get_dependency_scan_history(
        project_name: Optional[str] = None,
        repository_name: Optional[str] = None,
        limit: int = 5,
    ) -> str:
        """Get recent dependency scan runs and their results."""
        scope_filter = await _resolve_scope(db, project_name, repository_name)
        if isinstance(scope_filter, str):
            return scope_filter

        q = select(DepScanRun).where(*scope_filter).order_by(DepScanRun.created_at.desc()).limit(limit)
        runs = (await db.execute(q)).scalars().all()

        if not runs:
            return "No dependency scans have been run yet."

        lines = [f"Recent dependency scans ({len(runs)} runs):"]
        for r in runs:
            status = r.status.value if hasattr(r.status, "value") else str(r.status)
            ts = r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "?"
            lines.append(
                f"  [{status.upper()}] {ts} — {r.findings_count} packages, "
                f"{r.vulnerable_count} vulnerable, {r.outdated_count} outdated"
                + (f" — Error: {r.error_message[:100]}" if r.error_message else "")
            )
        return "\n".join(lines)

    @tool
    async def search_dependency(
        package_name: str,
        project_name: Optional[str] = None,
    ) -> str:
        """Search for a specific package by name across all repos."""
        filters = []
        if project_name:
            proj = (await db.execute(
                select(Project).where(func.lower(Project.name) == project_name.lower())
            )).scalar_one_or_none()
            if proj:
                filters.append(DependencyFinding.project_id == proj.id)

        q = select(DependencyFinding).where(
            DependencyFinding.status == DepFindingStatus.ACTIVE,
            DependencyFinding.package_name.ilike(f"%{package_name}%"),
            *filters,
        ).order_by(DependencyFinding.package_name).limit(20)
        findings = (await db.execute(q)).scalars().all()

        if not findings:
            return f"No dependency matching '{package_name}' found."

        lines = [f"Found {len(findings)} matches for '{package_name}':"]
        for f in findings:
            status_parts = []
            if f.is_vulnerable:
                vuln_count = len(f.vulnerabilities or [])
                status_parts.append(f"{vuln_count} vulns")
            if f.is_outdated:
                status_parts.append(f"outdated ({f.current_version} → {f.latest_version})")
            if not status_parts:
                status_parts.append("up to date")

            lines.append(
                f"  {f.package_name} {f.current_version or '?'} ({f.ecosystem}) "
                f"in {f.file_path} — {', '.join(status_parts)}"
            )
        return "\n".join(lines)

    return [
        get_dependency_summary, get_vulnerable_dependencies,
        get_outdated_dependencies, get_dependency_files,
        get_dependency_scan_history, search_dependency,
    ]


async def _resolve_scope(
    db: AsyncSession,
    project_name: str | None,
    repository_name: str | None,
) -> list | str:
    """Resolve project/repo names to SQLAlchemy filter clauses."""
    filters = []
    if repository_name:
        repo = (await db.execute(
            select(Repository).where(func.lower(Repository.name) == repository_name.lower())
        )).scalar_one_or_none()
        if not repo:
            return f"Repository '{repository_name}' not found."
        filters.append(DependencyFinding.repository_id == repo.id)
    elif project_name:
        proj = (await db.execute(
            select(Project).where(func.lower(Project.name) == project_name.lower())
        )).scalar_one_or_none()
        if not proj:
            return f"Project '{project_name}' not found."
        filters.append(DependencyFinding.project_id == proj.id)
    return filters


register_tool_category(CATEGORY, DEFINITIONS, _build_dependency_tools)
