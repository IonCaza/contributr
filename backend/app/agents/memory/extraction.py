"""Tier 3: LangMem background memory extraction.

After each agent turn, extracts facts, preferences, and patterns from
the conversation and stores them in the long-term PostgresStore.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from app.agents.memory.pool import get_store

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage

logger = logging.getLogger(__name__)

_manager = None


def _get_memory_manager():
    """Lazy-init the memory store manager (requires langmem + store)."""
    global _manager
    if _manager is not None:
        return _manager

    store = get_store()
    if store is None:
        return None

    try:
        from langmem import create_memory_store_manager

        _manager = create_memory_store_manager(
            "anthropic:claude-3-5-sonnet-latest",
            namespace=("memories", "{user_id}"),
        )
        logger.info("LangMem memory store manager initialised")
        return _manager
    except Exception:
        logger.debug("LangMem not available or failed to initialise", exc_info=True)
        return None


async def extract_memories(
    user_id: uuid.UUID,
    messages: list[dict],
) -> None:
    """Extract memories from a turn's messages in the background.

    Args:
        user_id: Scope extraction to this user's namespace.
        messages: List of {"role": ..., "content": ...} dicts from the turn.
    """
    manager = _get_memory_manager()
    if manager is None:
        return

    try:
        formatted = []
        for msg in messages:
            formatted.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        await manager.ainvoke(
            {"messages": formatted},
            config={"configurable": {"user_id": str(user_id)}},
        )
        logger.debug("LangMem extraction completed for user %s", user_id)
    except Exception:
        logger.debug("LangMem extraction failed (non-critical)", exc_info=True)
