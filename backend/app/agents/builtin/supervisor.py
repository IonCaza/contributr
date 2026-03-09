"""Seed data for the built-in Supervisor agent."""

from app.agents.builtin import BuiltinAgentSpec
from app.agents.prompts.defaults import SUPERVISOR_SYSTEM_PROMPT

SPEC = BuiltinAgentSpec(
    slug="supervisor",
    name="Contributr Supervisor",
    description=(
        "Coordinating agent that orchestrates all specialist agents. "
        "Routes questions to the right domain expert(s), synthesizes "
        "cross-domain responses, and handles complex queries spanning "
        "code, delivery, security, and insights."
    ),
    system_prompt=SUPERVISOR_SYSTEM_PROMPT,
    tool_slugs=[],
    agent_type="supervisor",
    member_slugs=[
        "contribution-analyst",
        "text-to-sql",
        "delivery-analyst",
        "delivery-code-analyst",
        "insights-analyst",
        "contributor-coach",
        "sast-analyst",
        "code-reviewer",
    ],
)
