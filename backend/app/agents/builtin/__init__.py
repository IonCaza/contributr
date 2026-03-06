from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BuiltinAgentSpec:
    slug: str
    name: str
    description: str
    system_prompt: str
    tool_slugs: list[str] = field(default_factory=list)


def get_builtin_agents() -> list[BuiltinAgentSpec]:
    """Return all built-in agent specs.

    Uses a function to avoid circular imports at module load time.
    """
    from app.agents.builtin.contribution_analyst import SPEC as contribution_analyst
    from app.agents.builtin.text_to_sql import SPEC as text_to_sql

    return [
        contribution_analyst,
        text_to_sql,
    ]
