import logging

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool, StructuredTool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import build_agent
from app.db.models.agent_config import AgentConfig
from app.db.models.llm_provider import LlmProvider

logger = logging.getLogger(__name__)


async def _resolve_child_provider(
    db: AsyncSession,
    member: AgentConfig,
    fallback_provider: LlmProvider,
) -> LlmProvider:
    """Get the child agent's own LLM provider, falling back to the supervisor's."""
    if member.llm_provider_id:
        result = await db.execute(
            select(LlmProvider).where(LlmProvider.id == member.llm_provider_id)
        )
        row = result.scalar_one_or_none()
        if row:
            return row
    return fallback_provider


def _make_child_runner(db, member, fallback_provider):
    """Factory that returns a clean async function with only ``query: str`` in its signature."""

    async def _run_child(query: str) -> str:
        logger.info("Supervisor delegating to %s: %s", member.slug, query[:120])
        try:
            provider = await _resolve_child_provider(db, member, fallback_provider)
            child_agent, max_iter = build_agent(
                member, provider, db, extra_tools=None,
            )
            result = await child_agent.ainvoke(
                {"messages": [HumanMessage(content=query)]},
                config={"recursion_limit": (max_iter or 25) * 2},
            )
            last_msg = result["messages"][-1]
            response = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
            logger.info("Child agent %s responded (%d chars)", member.slug, len(response))
            return response
        except Exception as e:
            logger.exception("Child agent %s failed: %s", member.slug, e)
            return f"The {member.name} agent encountered an error: {e}"

    return _run_child


def build_delegation_tools(
    db: AsyncSession,
    member_configs: list[AgentConfig],
    fallback_provider: LlmProvider,
) -> list[BaseTool]:
    """Wrap each member agent as a callable LangChain tool for the supervisor.

    Each tool runs the child agent's full tool-calling loop internally
    and returns the final text response.
    """
    tools: list[BaseTool] = []

    for member in member_configs:
        if not member.enabled:
            continue

        tool_name = f"ask_{member.slug.replace('-', '_')}"
        tool_desc = (
            f"Delegate a question to the {member.name} agent. "
            f"{member.description or ''} "
            f"Use this when the user's question falls within this agent's domain."
        ).strip()

        runner = _make_child_runner(db, member, fallback_provider)

        tool = StructuredTool.from_function(
            coroutine=runner,
            name=tool_name,
            description=tool_desc,
        )
        tools.append(tool)

    return tools
