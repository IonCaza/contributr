"""Platform-level tool for searching chat session history.

Injected dynamically into every agent by the runner -- not part of the
assignable tool registry.
"""
from __future__ import annotations

import uuid

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.chat import ChatMessage

MAX_RESULTS = 15
MAX_CONTENT_LEN = 500


def build_search_chat_history_tool(
    db: AsyncSession,
    session_id: uuid.UUID,
):
    """Return a @tool bound to a specific chat session and db session."""

    @tool
    async def search_chat_history(query: str) -> str:
        """Search the full chat history for this session.

        Use this to find specific details from earlier in the conversation
        that may not be in your current context. Accepts a keyword or phrase
        and returns matching messages with timestamps.
        """
        pattern = f"%{query}%"
        result = await db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.content.ilike(pattern),
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(MAX_RESULTS)
        )
        rows = result.scalars().all()

        if not rows:
            return f"No messages found matching '{query}' in this session's history."

        parts: list[str] = []
        for msg in reversed(rows):
            ts = msg.created_at.strftime("%Y-%m-%d %H:%M UTC")
            content = msg.content
            if len(content) > MAX_CONTENT_LEN:
                content = content[:MAX_CONTENT_LEN] + "..."
            parts.append(f"[{ts}] [{msg.role.value.upper()}]: {content}")

        header = f"Found {len(rows)} matching message(s) for '{query}':\n\n"
        return header + "\n\n".join(parts)

    return search_chat_history
