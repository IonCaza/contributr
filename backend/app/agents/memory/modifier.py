"""Prompt callable that trims checkpoint messages to fit the context window.

Plugged into create_react_agent as ``prompt``. Runs before every LLM call
within a turn: receives the full accumulated state and returns a message
list that fits within the token budget.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Sequence

from langchain_core.messages import BaseMessage, SystemMessage

from app.agents.context.manager import (
    RESPONSE_RESERVE,
    SCRATCHPAD_RESERVE,
    count_tokens,
    get_context_window,
)

if TYPE_CHECKING:
    from app.db.models.agent_config import AgentConfig
    from app.db.models.llm_provider import LlmProvider

logger = logging.getLogger(__name__)


def _msg_text(msg: BaseMessage) -> str:
    if isinstance(msg.content, str):
        return msg.content
    return str(msg.content)


def make_state_modifier(
    system_prompt: str,
    agent_config: "AgentConfig",
    provider: "LlmProvider",
):
    """Return a callable that trims messages for the LLM's context window."""
    model = provider.model
    ctx_window = get_context_window(provider)
    system_tokens = count_tokens(model, system_prompt)

    async def _modifier(state: dict) -> list[BaseMessage]:
        messages: Sequence[BaseMessage] = state.get("messages", [])
        summary: str | None = state.get("context_summary")

        budget = ctx_window - system_tokens - RESPONSE_RESERVE - SCRATCHPAD_RESERVE
        if summary:
            budget -= count_tokens(model, summary) + 4

        if budget <= 0:
            result = [SystemMessage(content=system_prompt)]
            if summary:
                result.append(SystemMessage(content=f"Previous conversation context:\n{summary}"))
            if messages:
                result.append(messages[-1])
            return result

        keep: list[BaseMessage] = []
        keep_tokens = 0
        for msg in reversed(messages):
            tok = count_tokens(model, _msg_text(msg)) + 4
            if keep_tokens + tok > budget:
                break
            keep.insert(0, msg)
            keep_tokens += tok

        result: list[BaseMessage] = [SystemMessage(content=system_prompt)]
        if summary and len(keep) < len(messages):
            result.append(
                SystemMessage(content=f"Previous conversation context:\n{summary}")
            )
        result.extend(keep)
        return result

    return _modifier
