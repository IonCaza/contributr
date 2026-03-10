from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, AsyncIterator

from langchain_core.messages import HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import build_agent
from app.agents.llm.manager import build_llm_from_provider
from app.agents.memory.cleanup import cleanup_checkpoint
from app.agents.memory.extraction import extract_memories
from app.agents.memory.tools import build_memory_tools
from app.agents.supervisor import build_delegation_tools
from app.agents.registry import is_ai_enabled, get_agent_by_slug
from app.agents.tools.chat_history import build_search_chat_history_tool
from app.agents.tools.feedback_gap import build_report_capability_gap_tool
from app.db.models.llm_provider import LlmProvider

logger = logging.getLogger(__name__)

DELEGATION_PREFIX = "ask_"


async def run_agent_stream(
    db: AsyncSession,
    user_input: str,
    agent_slug: str = "contribution-analyst",
    *,
    session_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Run a named agent and yield structured event dicts.

    Event types:
        {"type": "token", "content": str}
        {"type": "agent_start", "run_id": str, "slug": str}
        {"type": "agent_token", "run_id": str, "content": str}
        {"type": "agent_done", "run_id": str}

    The checkpointer handles message history natively via thread_id.
    Only the new user message is passed in; all prior context is loaded
    from the checkpoint automatically.
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
            .where(LlmProvider.model_type == "chat")
            .limit(1)
        )
        provider = result.scalar_one_or_none()
    if not provider:
        result = await db.execute(
            select(LlmProvider).where(LlmProvider.model_type == "chat").limit(1)
        )
        provider = result.scalar_one_or_none()
    if not provider:
        raise RuntimeError("No LLM provider available — configure one in Settings > AI")

    extra_tools = []
    if session_id is not None:
        extra_tools.append(build_search_chat_history_tool(db, session_id))
        extra_tools.append(build_report_capability_gap_tool(session_id, agent_slug))
    if user_id is not None:
        extra_tools.extend(build_memory_tools(user_id))

    is_supervisor = getattr(agent_config, "agent_type", "standard") == "supervisor"
    if is_supervisor:
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

    thread_id = str(session_id) if session_id else str(uuid.uuid4())
    run_config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": (max_iterations or 25) * 2,
    }

    active_delegations: dict[str, dict[str, str]] = {}
    collected = ""
    pending_separator = False

    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=user_input)]},
        version="v2",
        config=run_config,
    ):
        kind = event["event"]
        name = event.get("name", "")
        run_id = event.get("run_id", "")
        parent_ids: list[str] = event.get("parent_ids", [])

        if kind == "on_tool_start" and name.startswith(DELEGATION_PREFIX):
            slug = name[len(DELEGATION_PREFIX):].replace("_", "-")
            active_delegations[run_id] = {"slug": slug}
            yield {"type": "agent_start", "run_id": run_id, "slug": slug}

        elif kind == "on_tool_end" and name.startswith(DELEGATION_PREFIX):
            info = active_delegations.pop(run_id, None)
            if info:
                yield {"type": "agent_done", "run_id": run_id}
            if collected:
                pending_separator = True

        elif kind == "on_tool_end":
            if collected:
                pending_separator = True

        elif kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            content = getattr(chunk, "content", "")
            if not isinstance(content, str) or not content:
                continue

            child_run = next(
                (pid for pid in parent_ids if pid in active_delegations),
                None,
            )
            if child_run:
                yield {"type": "agent_token", "run_id": child_run, "content": content}
            else:
                if pending_separator:
                    collected += "\n\n"
                    yield {"type": "token", "content": "\n\n"}
                    pending_separator = False
                collected += content
                yield {"type": "token", "content": content}

    if not collected:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=user_input)]},
            config=run_config,
        )
        last_msg = result["messages"][-1]
        output = last_msg.content if hasattr(last_msg, "content") else "I wasn't able to generate a response."
        yield {"type": "token", "content": output}
        collected = output

    llm = build_llm_from_provider(provider, streaming=False)
    await cleanup_checkpoint(agent, run_config, llm, agent_config, provider)

    if user_id and collected:
        turn_msgs = [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": collected},
        ]
        asyncio.create_task(extract_memories(user_id, turn_msgs))
