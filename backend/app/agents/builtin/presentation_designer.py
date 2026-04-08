"""Seed data for the built-in Presentation Designer agent."""

from app.agents.builtin import BuiltinAgentSpec
from app.agents.prompts.defaults import PRESENTATION_DESIGNER_PROMPT

SPEC = BuiltinAgentSpec(
    slug="presentation-designer",
    name="Presentation Designer",
    description=(
        "Creates beautiful, interactive dashboard presentations from project data. "
        "Generates React component code that renders in a sandboxed iframe with live "
        "data access via the PostMessage bridge. Delegates domain-specific data "
        "queries to specialist analysts and synthesizes the results."
    ),
    system_prompt=PRESENTATION_DESIGNER_PROMPT,
    tool_slugs=[
        "find_project",
        "run_sql_query",
        "list_tables",
        "describe_table",
        "save_presentation",
        "get_presentation",
        "update_presentation",
        "get_presentation_template",
        "update_presentation_template",
        "list_skills",
        "use_skill",
    ],
    agent_type="supervisor",
    member_slugs=[
        "contribution-analyst",
        "delivery-analyst",
        "insights-analyst",
        "sast-analyst",
    ],
    max_iterations=50,
)
