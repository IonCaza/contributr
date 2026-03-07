"""Seed data for the built-in Insights Analyst agent."""

from app.agents.builtin import BuiltinAgentSpec
from app.agents.prompts.defaults import INSIGHTS_ANALYST_PROMPT

SPEC = BuiltinAgentSpec(
    slug="insights-analyst",
    name="Insights Analyst",
    description=(
        "Analyzes automated findings from the project insights engine and "
        "generates enriched descriptions, root-cause hypotheses, and "
        "specific actionable recommendations for engineering managers."
    ),
    system_prompt=INSIGHTS_ANALYST_PROMPT,
    tool_slugs=[
        "find_project",
        "find_contributor",
        "find_work_item",
        "find_iteration",
        "find_team",
        "get_project_overview",
        "get_contributor_profile",
        "get_sprint_overview",
        "get_velocity_trend",
        "get_cycle_time_stats",
        "get_backlog_overview",
        "get_team_delivery_overview",
        "get_code_delivery_intersection",
        "get_pr_review_cycle",
        "get_wip_analysis",
        "get_quality_summary",
    ],
)
