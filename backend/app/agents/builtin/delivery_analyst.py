"""Seed data for the built-in Delivery Analyst agent."""

from app.agents.builtin import BuiltinAgentSpec
from app.agents.prompts.defaults import DELIVERY_ANALYST_PROMPT

SPEC = BuiltinAgentSpec(
    slug="delivery-analyst",
    name="Delivery Analyst",
    description=(
        "Analyzes delivery and project management data — sprints, velocity, "
        "throughput, cycle time, backlog health, team performance, and quality "
        "metrics sourced from Azure DevOps and similar platforms."
    ),
    system_prompt=DELIVERY_ANALYST_PROMPT,
    tool_slugs=[
        # Lookup (reused from contribution_analytics for name resolution)
        "find_project",
        "find_contributor",
        # Delivery-specific lookup
        "find_work_item",
        "find_iteration",
        "find_team",
        # Sprint / Iteration Analysis
        "get_sprint_overview",
        "get_sprint_comparison",
        "get_sprint_burndown",
        "get_active_sprints",
        "get_sprint_scope_change",
        "get_sprint_carryover",
        # Velocity and Throughput
        "get_velocity_trend",
        "get_delivery_throughput_trend",
        "get_velocity_forecast",
        "get_team_velocity_comparison",
        # Cycle Time and Flow
        "get_cycle_time_stats",
        "get_lead_time_stats",
        "get_wip_analysis",
        "get_delivery_cumulative_flow",
        # Backlog Health
        "get_backlog_overview",
        "get_stale_items",
        "get_backlog_composition",
        "get_backlog_growth_trend",
        # Team Analytics
        "get_team_delivery_overview",
        "get_team_workload",
        "get_team_members_delivery",
        # Quality Metrics
        "get_bug_metrics",
        "get_quality_summary",
        # Code-Delivery Intersection
        "get_code_delivery_intersection",
        "get_work_item_linked_commits",
        # Work Item Description Editing
        "read_work_item_description",
        "propose_work_item_description",
    ],
)
