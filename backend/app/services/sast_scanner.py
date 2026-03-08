from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from git import Repo as GitRepo
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models.sast import (
    SastFinding, SastFindingStatus, SastIgnoredRule, SastRuleProfile,
    SastScanRun, SastScanStatus, SastSeverity, SastConfidence,
)

if TYPE_CHECKING:
    from app.services.sync_logger import SyncLogger

logger = logging.getLogger(__name__)

SEVERITY_MAP = {
    "ERROR": SastSeverity.HIGH,
    "WARNING": SastSeverity.MEDIUM,
    "INFO": SastSeverity.LOW,
}


@dataclass
class SemgrepResult:
    rule_id: str
    severity: SastSeverity
    confidence: SastConfidence
    file_path: str
    start_line: int
    end_line: int
    start_col: int | None
    end_col: int | None
    message: str
    code_snippet: str | None
    fix_suggestion: str | None
    cwe_ids: list[str] = field(default_factory=list)
    owasp_ids: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def _map_severity(raw: str) -> SastSeverity:
    return SEVERITY_MAP.get(raw.upper(), SastSeverity.MEDIUM)


def _map_confidence(raw: str) -> SastConfidence:
    val = raw.upper()
    if val == "HIGH":
        return SastConfidence.HIGH
    if val == "LOW":
        return SastConfidence.LOW
    return SastConfidence.MEDIUM


def _extract_cwe(meta: dict) -> list[str]:
    cwe_raw = meta.get("cwe") or meta.get("cwe-id") or []
    if isinstance(cwe_raw, str):
        cwe_raw = [cwe_raw]
    return [c.split(":")[0].strip() if ":" in c else c.strip() for c in cwe_raw]


def _extract_owasp(meta: dict) -> list[str]:
    owasp_raw = meta.get("owasp") or []
    if isinstance(owasp_raw, str):
        owasp_raw = [owasp_raw]
    return [o.split(" - ")[0].strip() if " - " in o else o.strip() for o in owasp_raw]


def parse_semgrep_output(raw_json: str, worktree_path: str) -> list[SemgrepResult]:
    data = json.loads(raw_json)
    results: list[SemgrepResult] = []

    for r in data.get("results", []):
        extra = r.get("extra", {})
        meta = extra.get("metadata", {})

        file_path = r.get("path", "")
        if file_path.startswith(worktree_path):
            file_path = file_path[len(worktree_path):].lstrip("/")

        severity_raw = extra.get("severity", "WARNING")
        if meta.get("confidence") == "HIGH" and severity_raw == "WARNING":
            severity = SastSeverity.HIGH
        elif severity_raw == "ERROR" and meta.get("impact", "").upper() == "HIGH":
            severity = SastSeverity.CRITICAL
        else:
            severity = _map_severity(severity_raw)

        results.append(SemgrepResult(
            rule_id=r.get("check_id", "unknown"),
            severity=severity,
            confidence=_map_confidence(meta.get("confidence", "MEDIUM")),
            file_path=file_path,
            start_line=r.get("start", {}).get("line", 0),
            end_line=r.get("end", {}).get("line", 0),
            start_col=r.get("start", {}).get("col"),
            end_col=r.get("end", {}).get("col"),
            message=extra.get("message", ""),
            code_snippet=extra.get("lines", ""),
            fix_suggestion=extra.get("fix"),
            cwe_ids=_extract_cwe(meta),
            owasp_ids=_extract_owasp(meta),
            metadata={
                "category": meta.get("category", ""),
                "subcategory": meta.get("subcategory", []),
                "technology": meta.get("technology", []),
                "references": meta.get("references", []),
                "source": meta.get("source", ""),
            },
        ))

    return results


def _prepare_worktree(bare_repo_path: str, branch: str | None = None) -> tuple[str, str | None]:
    """Create a temporary worktree from a bare/mirror repo. Returns (worktree_path, resolved_sha)."""
    worktree_dir = tempfile.mkdtemp(prefix="contributr_sast_")

    try:
        git_repo = GitRepo(bare_repo_path)
        git_repo.git.worktree("add", "--detach", worktree_dir, branch or "HEAD")

        resolved_sha = git_repo.git.rev_parse("HEAD" if not branch else branch)
        return worktree_dir, resolved_sha
    except Exception:
        shutil.rmtree(worktree_dir, ignore_errors=True)
        raise


def _cleanup_worktree(bare_repo_path: str, worktree_dir: str) -> None:
    try:
        git_repo = GitRepo(bare_repo_path)
        git_repo.git.worktree("remove", "-f", worktree_dir)
    except Exception:
        logger.warning("git worktree remove failed, falling back to rm", exc_info=True)
    shutil.rmtree(worktree_dir, ignore_errors=True)


async def _run_semgrep(worktree_path: str, profile: SastRuleProfile | None, slog: SyncLogger | None = None) -> str:
    cmd = ["semgrep", "scan", "--json", "--quiet"]

    if profile and profile.rulesets:
        for ruleset in profile.rulesets:
            cmd.extend(["--config", ruleset])
    else:
        cmd.extend(["--config", "auto"])

    custom_rules_file = None
    if profile and profile.custom_rules_yaml:
        fd, custom_rules_file = tempfile.mkstemp(suffix=".yml", prefix="sast_rules_")
        os.write(fd, profile.custom_rules_yaml.encode())
        os.close(fd)
        cmd.extend(["--config", custom_rules_file])

    cmd.append(worktree_path)

    if slog:
        slog.info("scan", f"Running: {' '.join(cmd[:6])}...")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)

        if stderr:
            stderr_preview = stderr.decode(errors="replace")[:2000].strip()
            if stderr_preview:
                logger.info("semgrep stderr: %s", stderr_preview)

        stdout_text = stdout.decode(errors="replace")
        stderr_text_full = stderr.decode(errors="replace") if stderr else ""

        if proc.returncode not in (0, 1):
            raise RuntimeError(
                f"semgrep exited with code {proc.returncode}: {stderr_text_full[:2000]}"
            )

        if not stdout_text.strip():
            raise RuntimeError(
                f"semgrep produced no output (exit code {proc.returncode}). "
                f"stderr: {stderr_text_full[:2000]}"
            )

        return stdout_text

    finally:
        if custom_rules_file and os.path.exists(custom_rules_file):
            os.unlink(custom_rules_file)


async def persist_sast_findings(
    db: AsyncSession,
    scan_run: SastScanRun,
    results: list[SemgrepResult],
) -> int:
    """Persist findings with dedup: same (repo, rule_id, file_path, start_line) updates last_detected_at."""
    now = datetime.now(timezone.utc)
    new_count = 0
    seen_keys: set[tuple[str, str, int]] = set()

    existing_q = select(SastFinding).where(
        SastFinding.repository_id == scan_run.repository_id,
        SastFinding.status.in_([SastFindingStatus.OPEN]),
    )
    existing_rows = (await db.execute(existing_q)).scalars().all()
    existing_map: dict[tuple[str, str, int], SastFinding] = {
        (f.rule_id, f.file_path, f.start_line): f for f in existing_rows
    }

    for r in results:
        key = (r.rule_id, r.file_path, r.start_line)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        existing = existing_map.get(key)
        if existing:
            existing.last_detected_at = now
            existing.scan_run_id = scan_run.id
            existing.severity = r.severity
            existing.confidence = r.confidence
            existing.message = r.message
            existing.code_snippet = r.code_snippet
            existing.fix_suggestion = r.fix_suggestion
            existing.cwe_ids = r.cwe_ids
            existing.owasp_ids = r.owasp_ids
            existing.extra_metadata = r.metadata
        else:
            db.add(SastFinding(
                scan_run_id=scan_run.id,
                repository_id=scan_run.repository_id,
                project_id=scan_run.project_id,
                rule_id=r.rule_id,
                severity=r.severity,
                confidence=r.confidence,
                file_path=r.file_path,
                start_line=r.start_line,
                end_line=r.end_line,
                start_col=r.start_col,
                end_col=r.end_col,
                message=r.message,
                code_snippet=r.code_snippet,
                fix_suggestion=r.fix_suggestion,
                cwe_ids=r.cwe_ids,
                owasp_ids=r.owasp_ids,
                extra_metadata=r.metadata,
                first_detected_at=now,
                last_detected_at=now,
            ))
            new_count += 1

    # Mark findings not seen in this scan as fixed
    for key, finding in existing_map.items():
        if key not in seen_keys:
            finding.status = SastFindingStatus.FIXED

    await db.flush()
    return len(seen_keys)


async def run_sast_scan(
    db: AsyncSession,
    scan_run: SastScanRun,
    branch: str | None = None,
    profile: SastRuleProfile | None = None,
    slog: SyncLogger | None = None,
) -> int:
    """Execute a SAST scan for a repository. Returns total findings count."""
    bare_repo_path = os.path.join(settings.repos_cache_dir, str(scan_run.repository_id))

    if not os.path.exists(bare_repo_path):
        raise FileNotFoundError(
            f"Repository cache not found at {bare_repo_path}. Sync the repository first."
        )

    if slog:
        slog.info("worktree", "Creating temporary working tree from cached repo...")

    worktree_dir, resolved_sha = _prepare_worktree(bare_repo_path, branch)

    if resolved_sha:
        scan_run.commit_sha = resolved_sha[:40]
    if branch:
        scan_run.branch = branch

    try:
        if slog:
            slog.info("scan", f"Scanning {worktree_dir} with Semgrep...")

        raw_output = await _run_semgrep(worktree_dir, profile, slog)

        if slog:
            slog.info("parse", "Parsing Semgrep results...")

        results = parse_semgrep_output(raw_output, worktree_dir)

        if slog:
            slog.info("parse", f"Found {len(results)} raw findings")

        ignored = await _load_ignored_rules(db, scan_run.repository_id)
        if ignored:
            before = len(results)
            results = [r for r in results if r.rule_id not in ignored]
            filtered_count = before - len(results)
            if filtered_count and slog:
                slog.info("filter", f"Filtered {filtered_count} findings from {len(ignored)} ignored rules")

        count = await persist_sast_findings(db, scan_run, results)
        return count

    finally:
        if slog:
            slog.info("cleanup", "Removing temporary working tree...")
        _cleanup_worktree(bare_repo_path, worktree_dir)


async def _load_ignored_rules(db: AsyncSession, repository_id: uuid.UUID) -> set[str]:
    """Load ignored rule IDs (global + repo-specific)."""
    from sqlalchemy import or_
    q = select(SastIgnoredRule.rule_id).where(
        or_(
            SastIgnoredRule.repository_id.is_(None),
            SastIgnoredRule.repository_id == repository_id,
        )
    )
    rows = (await db.execute(q)).scalars().all()
    return set(rows)
