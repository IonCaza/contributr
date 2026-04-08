"""Seed data for the built-in Verification Agent."""

from app.agents.builtin import BuiltinAgentSpec
from app.agents.prompts.coordinator import VERIFICATION_PROMPT

SPEC = BuiltinAgentSpec(
    slug="verification-agent",
    name="Verification Agent",
    description=(
        "Independently confirms work products are correct, complete, and "
        "honestly reported. Re-derives key results, checks edge cases, and "
        "issues a PASS / PARTIAL / FAIL verdict."
    ),
    system_prompt=VERIFICATION_PROMPT,
    tool_slugs=[],
    agent_type="standard",
)
