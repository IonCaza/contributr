"""Seed data for the built-in Supervisor agent."""

from app.agents.builtin import BuiltinAgentSpec
from app.agents.prompts.coordinator import COORDINATOR_SYSTEM_PROMPT

SPEC = BuiltinAgentSpec(
    slug="supervisor",
    name="Contributr Supervisor",
    description=(
        "Coordinating agent that orchestrates all specialist agents. "
        "Decomposes complex requests into tasks, delegates to domain "
        "experts, synthesizes cross-domain responses, and verifies "
        "results before reporting."
    ),
    system_prompt=COORDINATOR_SYSTEM_PROMPT,
    tool_slugs=[
        "create_task",
        "update_task",
        "list_tasks",
        "get_task",
        "use_skill",
        "list_skills",
        "save_memory",
        "search_memories",
        "update_memory",
        "forget_memory",
        "get_screen_context",
        "navigate_user",
        "get_app_routes",
    ],
    agent_type="supervisor",
    member_slugs=[
        "contribution-analyst",
        "text-to-sql",
        "delivery-analyst",
        "delivery-code-analyst",
        "insights-analyst",
        "contributor-coach",
        "sast-analyst",
        "dependency-analyst",
        "code-reviewer",
        "verification-agent",
    ],
    max_iterations=50,
)
