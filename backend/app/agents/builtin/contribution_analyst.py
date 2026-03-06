"""Seed data for the built-in Contribution Analyst agent."""

from app.agents.builtin import BuiltinAgentSpec
from app.agents.prompts.defaults import CONTRIBUTION_ANALYST_PROMPT

SPEC = BuiltinAgentSpec(
    slug="contribution-analyst",
    name="Contribution Analyst",
    description=(
        "Analyzes git contribution data across projects, repositories, and contributors. "
        "Provides metrics on commits, code churn, PR cycle times, bus factor, "
        "contribution distribution, trends, file ownership, review networks, "
        "work patterns, branch analysis, and data freshness."
    ),
    system_prompt=CONTRIBUTION_ANALYST_PROMPT,
    tool_slugs=[
        "find_project",
        "find_contributor",
        "find_repository",
        "get_project_overview",
        "get_top_contributors",
        "get_contributor_profile",
        "get_repository_overview",
        "get_pr_activity",
        "get_contribution_trends",
        "get_code_hotspots",
        "get_pr_review_cycle",
        "get_reviewer_leaderboard",
        "get_review_network",
        "get_pr_size_analysis",
        "get_contributor_pr_summary",
        "get_file_ownership",
        "get_contributor_file_focus",
        "get_file_collaboration",
        "compare_contributors",
        "get_work_patterns",
        "get_contributor_cross_repo",
        "get_inactive_contributors",
        "get_branch_summary",
        "get_branch_comparison",
        "get_data_freshness",
    ],
)
