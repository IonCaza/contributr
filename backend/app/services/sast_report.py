from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sast import SastFinding, SastFindingStatus, SastScanRun


FINDING_COLUMNS = [
    "rule_id", "severity", "confidence", "file_path", "start_line", "end_line",
    "message", "code_snippet", "fix_suggestion", "cwe_ids", "owasp_ids", "status",
    "first_detected_at", "last_detected_at",
]


async def _load_findings(
    db: AsyncSession,
    *,
    project_id: str | None = None,
    repository_id: str | None = None,
    status_filter: str | None = None,
) -> list[SastFinding]:
    q = select(SastFinding)
    if project_id:
        q = q.where(SastFinding.project_id == project_id)
    if repository_id:
        q = q.where(SastFinding.repository_id == repository_id)
    if status_filter:
        q = q.where(SastFinding.status == SastFindingStatus(status_filter))
    else:
        q = q.where(SastFinding.status == SastFindingStatus.OPEN)
    q = q.order_by(SastFinding.severity, SastFinding.file_path, SastFinding.start_line)
    return list((await db.execute(q)).scalars().all())


def _finding_to_dict(f: SastFinding) -> dict:
    return {
        "id": str(f.id),
        "rule_id": f.rule_id,
        "severity": f.severity.value if hasattr(f.severity, "value") else str(f.severity),
        "confidence": f.confidence.value if hasattr(f.confidence, "value") else str(f.confidence),
        "file_path": f.file_path,
        "start_line": f.start_line,
        "end_line": f.end_line,
        "message": f.message,
        "code_snippet": f.code_snippet or "",
        "fix_suggestion": f.fix_suggestion or "",
        "cwe_ids": f.cwe_ids or [],
        "owasp_ids": f.owasp_ids or [],
        "status": f.status.value if hasattr(f.status, "value") else str(f.status),
        "first_detected_at": f.first_detected_at.isoformat() if f.first_detected_at else "",
        "last_detected_at": f.last_detected_at.isoformat() if f.last_detected_at else "",
    }


async def generate_json_report(
    db: AsyncSession,
    *,
    project_id: str | None = None,
    repository_id: str | None = None,
    status_filter: str | None = None,
) -> str:
    findings = await _load_findings(db, project_id=project_id, repository_id=repository_id, status_filter=status_filter)
    data = {
        "report": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tool": "semgrep",
            "total_findings": len(findings),
            "summary": _summarize(findings),
        },
        "findings": [_finding_to_dict(f) for f in findings],
    }
    return json.dumps(data, indent=2)


async def generate_csv_report(
    db: AsyncSession,
    *,
    project_id: str | None = None,
    repository_id: str | None = None,
    status_filter: str | None = None,
) -> str:
    findings = await _load_findings(db, project_id=project_id, repository_id=repository_id, status_filter=status_filter)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FINDING_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for f in findings:
        row = _finding_to_dict(f)
        row["cwe_ids"] = ", ".join(row["cwe_ids"])
        row["owasp_ids"] = ", ".join(row["owasp_ids"])
        writer.writerow(row)
    return buf.getvalue()


async def generate_pdf_report(
    db: AsyncSession,
    *,
    project_id: str | None = None,
    repository_id: str | None = None,
    status_filter: str | None = None,
) -> bytes:
    findings = await _load_findings(db, project_id=project_id, repository_id=repository_id, status_filter=status_filter)
    summary = _summarize(findings)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "SAST Security Report", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Total Open Findings: {len(findings)}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Summary table
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Severity Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)

    col_w = 38
    pdf.set_fill_color(240, 240, 240)
    for sev in ("critical", "high", "medium", "low", "info"):
        pdf.cell(col_w, 7, sev.capitalize(), border=1, fill=True)
    pdf.ln()
    for sev in ("critical", "high", "medium", "low", "info"):
        pdf.cell(col_w, 7, str(summary.get(sev, 0)), border=1)
    pdf.ln(10)

    # Findings table
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Findings Detail", new_x="LMARGIN", new_y="NEXT")

    if not findings:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 8, "No open findings detected.", new_x="LMARGIN", new_y="NEXT")
    else:
        for i, f in enumerate(findings, 1):
            sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)

            pdf.set_font("Helvetica", "B", 10)
            title = f"#{i}  [{sev.upper()}]  {f.rule_id}"
            pdf.multi_cell(0, 6, _safe(title), new_x="LMARGIN", new_y="NEXT")

            pdf.set_font("Helvetica", "", 9)
            pdf.cell(0, 5, _safe(f"File: {f.file_path}:{f.start_line}"), new_x="LMARGIN", new_y="NEXT")
            pdf.multi_cell(0, 5, _safe(f"Message: {f.message}"), new_x="LMARGIN", new_y="NEXT")

            if f.code_snippet:
                pdf.set_font("Courier", "", 8)
                snippet = f.code_snippet[:300]
                pdf.multi_cell(0, 4, _safe(snippet), new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", "", 9)

            if f.fix_suggestion:
                pdf.cell(0, 5, _safe(f"Fix: {f.fix_suggestion[:200]}"), new_x="LMARGIN", new_y="NEXT")

            cwes = ", ".join(f.cwe_ids) if f.cwe_ids else ""
            owasps = ", ".join(f.owasp_ids) if f.owasp_ids else ""
            if cwes or owasps:
                refs = []
                if cwes:
                    refs.append(f"CWE: {cwes}")
                if owasps:
                    refs.append(f"OWASP: {owasps}")
                pdf.cell(0, 5, _safe(" | ".join(refs)), new_x="LMARGIN", new_y="NEXT")

            pdf.ln(3)

    return pdf.output()


def _summarize(findings: list[SastFinding]) -> dict:
    counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
        counts[sev] = counts.get(sev, 0) + 1
    return counts


def _safe(text: str) -> str:
    """Ensure text is safe for fpdf (replace chars outside latin-1)."""
    return text.encode("latin-1", errors="replace").decode("latin-1")
