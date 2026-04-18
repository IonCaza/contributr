"""Seed data for the built-in Dependency Analyst agent."""

from app.agents.builtin import BuiltinAgentSpec
from app.agents.prompts.defaults import DEPENDENCY_ANALYST_PROMPT

SPEC = BuiltinAgentSpec(
    slug="dependency-analyst",
    name="Dependency Analyst",
    description=(
        "Analyzes third-party dependency scan results across repositories. "
        "Provides supply-chain health overviews, vulnerable package "
        "prioritization by severity, outdated dependency tracking, "
        "ecosystem breakdowns, and actionable upgrade guidance."
    ),
    system_prompt=DEPENDENCY_ANALYST_PROMPT,
    tool_slugs=[
        "find_project",
        "find_repository",
        "get_dependency_summary",
        "get_vulnerable_dependencies",
        "get_outdated_dependencies",
        "get_dependency_files",
        "get_dependency_scan_history",
        "search_dependency",
    ],
)
