from __future__ import annotations

import logging
import uuid
from typing import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import build_agent_executor, resolve_system_prompt
from app.agents.context.manager import prepare_history
from app.agents.llm.manager import build_llm_from_provider
from app.agents.registry import is_ai_enabled, get_agent_by_slug
from app.agents.tools.chat_history import build_search_chat_history_tool
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
        raise RuntimeError(f"Agent '{agent_slug}' has no LLM provider configured")

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

    executor = build_agent_executor(
        agent_config, provider, db, extra_tools=extra_tools,
    )
    messages = history_to_messages(trimmed_history)

    collected = ""
    pending_separator = False
    async for event in executor.astream_events(
        {"input": user_input, "chat_history": messages},
        version="v2",
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
        result = await executor.ainvoke(
            {"input": user_input, "chat_history": messages}
        )
        output = result.get("output", "I wasn't able to generate a response.")
        yield output
