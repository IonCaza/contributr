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
    from app.agents.builtin.delivery_analyst import SPEC as delivery_analyst
    from app.agents.builtin.delivery_code_analyst import SPEC as delivery_code_analyst
    from app.agents.builtin.insights_analyst import SPEC as insights_analyst
    from app.agents.builtin.contributor_coach import SPEC as contributor_coach

    return [
        contribution_analyst,
        text_to_sql,
        delivery_analyst,
        delivery_code_analyst,
        insights_analyst,
        contributor_coach,
    ]
