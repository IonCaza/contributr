from __future__ import annotations

import logging
import uuid
from typing import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import build_agent, resolve_system_prompt
from app.agents.context.manager import prepare_history
from app.agents.llm.manager import build_llm_from_provider
from app.agents.supervisor import build_delegation_tools
from sqlalchemy import select

from app.agents.registry import is_ai_enabled, get_agent_by_slug
from app.agents.tools.chat_history import build_search_chat_history_tool
from app.agents.tools.feedback_gap import build_report_capability_gap_tool
from app.db.models.llm_provider import LlmProvider

logger = logging.getLogger(__name__)


def history_to_messages(history: list[dict]) -> list[HumanMessage | AIMessage]:
    messages: list[HumanMessage | AIMessage] = []
    for entry in history:
        if entry["role"] == "user":
            messages.append(HumanMessage(content=entry["content"]))
        elif entry["role"] == "assistant":
            messages.append(AIMessage(content=entry["content"]))
    return messages


async def run_agent_stream(
    db: AsyncSession,
    user_input: str,
    chat_history: list[dict],
    agent_slug: str = "contribution-analyst",
    *,
    session_id: uuid.UUID | None = None,
    session_summary: str | None = None,
    context_state: dict | None = None,
) -> AsyncIterator[str]:
    """Run a named agent and yield streamed text chunks.

    Args:
        context_state: Mutable dict. If summarization occurs the key
            ``"new_summary"`` is set so the caller can persist it.
    """
    if not await is_ai_enabled(db):
        raise RuntimeError("AI is not enabled")

    agent_config = await get_agent_by_slug(db, agent_slug)
    if not agent_config:
        raise RuntimeError(f"Agent '{agent_slug}' not found or not enabled")

    provider: LlmProvider | None = agent_config.llm_provider
    if not provider:
        result = await db.execute(
            select(LlmProvider)
            .where(LlmProvider.is_default.is_(True))
            .limit(1)
        )
        provider = result.scalar_one_or_none()
    if not provider:
        result = await db.execute(select(LlmProvider).limit(1))
        provider = result.scalar_one_or_none()
    if not provider:
        raise RuntimeError("No LLM provider available — configure one in Settings > AI")

    system_prompt = resolve_system_prompt(agent_config)
    llm = build_llm_from_provider(provider, streaming=False)

    trimmed_history, new_summary = await prepare_history(
        agent_config, provider, llm, system_prompt,
        user_input, chat_history, session_summary,
    )

    if new_summary is not None and context_state is not None:
        context_state["new_summary"] = new_summary

    extra_tools = []
    if session_id is not None:
        extra_tools.append(build_search_chat_history_tool(db, session_id))
        extra_tools.append(build_report_capability_gap_tool(session_id, agent_slug))

    if getattr(agent_config, "agent_type", "standard") == "supervisor":
        member_agents = getattr(agent_config, "member_agents", [])
        if member_agents:
            delegation_tools = build_delegation_tools(db, member_agents, provider)
            extra_tools.extend(delegation_tools)
            logger.info(
                "Supervisor %s: %d delegation tools for members %s",
                agent_slug,
                len(delegation_tools),
                [m.slug for m in member_agents],
            )

    agent, max_iterations = build_agent(
        agent_config, provider, db, extra_tools=extra_tools,
    )
    messages = history_to_messages(trimmed_history)
    messages.append(HumanMessage(content=user_input))

    run_config = {"recursion_limit": (max_iterations or 25) * 2}

    collected = ""
    pending_separator = False
    async for event in agent.astream_events(
        {"messages": messages},
        version="v2",
        config=run_config,
    ):
        kind = event["event"]
        if kind == "on_tool_end":
            if collected:
                pending_separator = True
        elif kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if hasattr(chunk, "content") and isinstance(chunk.content, str) and chunk.content:
                if pending_separator:
                    collected += "\n\n"
                    yield "\n\n"
                    pending_separator = False
                collected += chunk.content
                yield chunk.content

    if not collected:
        result = await agent.ainvoke(
            {"messages": messages},
            config=run_config,
        )
        last_msg = result["messages"][-1]
        output = last_msg.content if hasattr(last_msg, "content") else "I wasn't able to generate a response."
        yield output
