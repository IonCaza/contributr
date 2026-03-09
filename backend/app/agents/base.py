from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.tools import BaseTool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm.manager import build_llm_from_provider
from app.agents.tools.registry import build_tools_for_slugs, build_all_tools
from app.db.models.agent_config import AgentConfig
from app.db.models.llm_provider import LlmProvider


def resolve_system_prompt(agent_config: AgentConfig) -> str:
    """Build the full system prompt including knowledge-graph blocks."""
    system_prompt = agent_config.system_prompt or ""

    kg_blocks: list[str] = []
    for assignment in getattr(agent_config, "knowledge_graph_assignments", []):
        kg = getattr(assignment, "knowledge_graph", None)
        if kg and kg.content:
            kg_blocks.append(kg.content)
    if kg_blocks:
        system_prompt += "\n\n## Data Context\n\n" + "\n\n---\n\n".join(kg_blocks)

    return system_prompt


def build_agent(
    agent_config: AgentConfig,
    provider: LlmProvider,
    db: AsyncSession,
    *,
    extra_tools: list[BaseTool] | None = None,
):
    llm = build_llm_from_provider(provider, streaming=True)

    tool_slugs = {a.tool_slug for a in agent_config.tool_assignments}
    if tool_slugs:
        tools = build_tools_for_slugs(db, tool_slugs)
    else:
        tools = build_all_tools(db)

    if extra_tools:
        tools = tools + extra_tools

    system_prompt = resolve_system_prompt(agent_config)

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
    ), agent_config.max_iterations
