"""Seed data for the built-in ADR Architect agent."""

from app.agents.builtin import BuiltinAgentSpec
from app.agents.prompts.defaults import ADR_ARCHITECT_PROMPT

SPEC = BuiltinAgentSpec(
    slug="adr-architect",
    name="ADR Architect",
    description=(
        "Expert in Architecture Decision Records. Creates, manages, and generates "
        "ADRs from freeform text. Helps teams document and reason about "
        "architectural decisions using established templates."
    ),
    system_prompt=ADR_ARCHITECT_PROMPT,
    tool_slugs=[
        "find_project",
        "find_repository",
        "list_adrs",
        "read_adr",
        "create_adr",
        "update_adr",
        "generate_adr_from_text",
        "suggest_adr",
    ],
)
