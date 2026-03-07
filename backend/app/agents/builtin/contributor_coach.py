"""Seed data for the built-in Contributor Coach agent."""

from app.agents.builtin import BuiltinAgentSpec
from app.agents.prompts.defaults import CONTRIBUTOR_COACH_PROMPT

SPEC = BuiltinAgentSpec(
    slug="contributor-coach",
    name="Contributor Coach",
    description=(
        "Analyzes automated findings about individual contributors and "
        "generates supportive, actionable coaching recommendations to "
        "help developers improve their habits, code quality, and collaboration."
    ),
    system_prompt=CONTRIBUTOR_COACH_PROMPT,
    tool_slugs=[
        "find_contributor",
        "get_contributor_profile",
        "get_project_overview",
        "get_quality_summary",
        "get_pr_review_cycle",
    ],
)
