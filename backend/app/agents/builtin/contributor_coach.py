"""Seed data for the built-in Contributor Coach agent."""

from app.agents.builtin import BuiltinAgentSpec
from app.agents.prompts.defaults import CONTRIBUTOR_COACH_PROMPT

SPEC = BuiltinAgentSpec(
    slug="contributor-coach",
    name="Contributor Coach",
    description=(
        "Investigates automated findings about individual contributors using "
        "analytics tools, then generates deeply-researched, supportive coaching "
        "recommendations backed by real data points."
    ),
    system_prompt=CONTRIBUTOR_COACH_PROMPT,
    tool_slugs=[
        "find_contributor",
        "get_contributor_profile",
        "get_work_patterns",
        "get_contributor_pr_summary",
        "get_contributor_file_focus",
        "get_contributor_cross_repo",
        "get_review_network",
        "get_reviewer_leaderboard",
        "get_file_ownership",
        "get_code_hotspots",
        "get_pr_review_cycle",
        "get_pr_size_analysis",
        "get_contribution_trends",
        "compare_contributors",
        "get_cycle_time_stats",
        "get_wip_analysis",
        "get_sprint_overview",
        "get_quality_summary",
        "get_code_delivery_intersection",
    ],
)
