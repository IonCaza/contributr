"""Post-turn checkpoint cleanup: trims old messages and maintains a rolling summary.

After each agent turn, checks whether checkpoint messages exceed a threshold.
If they do, summarises the oldest messages and removes them from the checkpoint
via RemoveMessage, keeping the checkpoint lean.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_core.messages import RemoveMessage, BaseMessage

from app.agents.context.manager import (
    count_tokens,
    get_context_window,
    resolve_summary_limit,
)
from app.agents.context.summarizer import summarize_messages

if TYPE_CHECKING:
    from langgraph.prebuilt import create_react_agent
    from langchain_litellm import ChatLiteLLM
    from app.db.models.agent_config import AgentConfig
    from app.db.models.llm_provider import LlmProvider

logger = logging.getLogger(__name__)

CLEANUP_THRESHOLD_RATIO = 0.6


def _msg_to_dict(msg: BaseMessage) -> dict:
    role = "assistant"
    if msg.type == "human":
        role = "user"
    elif msg.type == "system":
        role = "system"
    content = msg.content if isinstance(msg.content, str) else str(msg.content)
    return {"role": role, "content": content}


async def cleanup_checkpoint(
    agent,
    config: dict,
    llm: "ChatLiteLLM",
    agent_config: "AgentConfig",
    provider: "LlmProvider",
) -> None:
    """Trim checkpoint messages if they exceed the context-window threshold."""
    try:
        snapshot = await agent.aget_state(config)
    except Exception:
        logger.debug("No checkpoint state to clean up")
        return

    if not snapshot or not snapshot.values:
        return

    messages: list[BaseMessage] = snapshot.values.get("messages", [])
    existing_summary: str | None = snapshot.values.get("context_summary")

    if len(messages) < 6:
        return

    model = provider.model
    ctx_window = get_context_window(provider)
    threshold = int(ctx_window * CLEANUP_THRESHOLD_RATIO)

    total_tokens = sum(
        count_tokens(model, m.content if isinstance(m.content, str) else str(m.content)) + 4
        for m in messages
    )
    if total_tokens <= threshold:
        return

    keep_count = max(4, len(messages) // 2)
    evicted = messages[: len(messages) - keep_count]
    if not evicted:
        return

    logger.info(
        "Checkpoint cleanup: evicting %d of %d messages (%d tokens > %d threshold)",
        len(evicted), len(messages), total_tokens, threshold,
    )

    summary_limit = resolve_summary_limit(agent_config, ctx_window)
    evicted_dicts = [_msg_to_dict(m) for m in evicted]

    try:
        new_summary = await summarize_messages(
            llm, evicted_dicts, existing_summary, summary_limit,
        )
    except Exception:
        logger.exception("Checkpoint summarization failed, keeping messages")
        return

    remove_ops = [RemoveMessage(id=m.id) for m in evicted if hasattr(m, "id") and m.id]
    update: dict = {"context_summary": new_summary}
    if remove_ops:
        update["messages"] = remove_ops

    try:
        await agent.aupdate_state(config, update)
        logger.info("Checkpoint trimmed: removed %d messages, summary updated", len(remove_ops))
    except Exception:
        logger.exception("Failed to update checkpoint state")
