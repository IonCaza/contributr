from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BuiltinAgentSpec:
    slug: str
    name: str
    description: str
    system_prompt: str
    tool_slugs: list[str] = field(default_factory=list)
    agent_type: str = "standard"
    member_slugs: list[str] = field(default_factory=list)
    max_iterations: int | None = None


def get_builtin_agents() -> list[BuiltinAgentSpec]:
    """Return all built-in agent specs (standard agents first, then supervisors)."""
    from app.agents.builtin.contribution_analyst import SPEC as contribution_analyst
    from app.agents.builtin.text_to_sql import SPEC as text_to_sql
    from app.agents.builtin.delivery_analyst import SPEC as delivery_analyst
    from app.agents.builtin.delivery_code_analyst import SPEC as delivery_code_analyst
    from app.agents.builtin.insights_analyst import SPEC as insights_analyst
    from app.agents.builtin.contributor_coach import SPEC as contributor_coach
    from app.agents.builtin.sast_analyst import SPEC as sast_analyst
    from app.agents.builtin.code_reviewer import SPEC as code_reviewer
    from app.agents.builtin.supervisor import SPEC as supervisor
    from app.agents.builtin.adr_architect import SPEC as adr_architect
    from app.agents.builtin.presentation_designer import SPEC as presentation_designer

    return [
        contribution_analyst,
        text_to_sql,
        delivery_analyst,
        delivery_code_analyst,
        insights_analyst,
        contributor_coach,
        sast_analyst,
        code_reviewer,
        adr_architect,
        presentation_designer,
        supervisor,
    ]
