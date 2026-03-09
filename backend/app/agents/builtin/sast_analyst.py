"""Seed data for the built-in SAST Analyst agent."""

from app.agents.builtin import BuiltinAgentSpec
from app.agents.prompts.defaults import SAST_ANALYST_PROMPT

SPEC = BuiltinAgentSpec(
    slug="sast-analyst",
    name="SAST Analyst",
    description=(
        "Analyzes static application security testing (SAST) scan results. "
        "Provides security posture overviews, finding prioritization by risk, "
        "CWE/OWASP breakdowns, hotspot files, remediation trends, "
        "contributor exposure mapping, and actionable fix guidance."
    ),
    system_prompt=SAST_ANALYST_PROMPT,
    tool_slugs=[
        "find_project",
        "find_repository",
        "get_sast_summary",
        "get_sast_findings",
        "get_sast_finding_detail",
        "get_sast_hotspot_files",
        "get_sast_top_rules",
        "get_sast_cwe_breakdown",
        "get_sast_scan_history",
        "get_sast_trend",
        "get_sast_open_critical",
        "get_sast_contributor_exposure",
        "get_sast_fix_rate",
        "get_sast_file_risk",
    ],
)
