"""Seed data for the built-in Delivery-Code Analyst agent."""

from app.agents.builtin import BuiltinAgentSpec
from app.agents.prompts.defaults import DELIVERY_CODE_ANALYST_PROMPT

SPEC = BuiltinAgentSpec(
    slug="delivery-code-analyst",
    name="Delivery-Code Analyst",
    description=(
        "Cross-domain analysis linking code contributions to delivery work items — "
        "commit-to-story traceability, development efficiency, and "
        "engineering-to-delivery correlation."
    ),
    system_prompt=DELIVERY_CODE_ANALYST_PROMPT,
    tool_slugs=[
        # Lookup (from both domains)
        "find_project",
        "find_contributor",
        "find_work_item",
        "find_team",
        # Code analysis (selected)
        "get_project_overview",
        "get_contributor_profile",
        "get_pr_review_cycle",
        # Delivery analysis (selected)
        "get_sprint_overview",
        "get_velocity_trend",
        "get_cycle_time_stats",
        "get_team_delivery_overview",
        "get_team_members_delivery",
        # Intersection
        "get_code_delivery_intersection",
        "get_work_item_linked_commits",
    ],
)
