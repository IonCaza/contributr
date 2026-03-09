"""Platform-level tool for reporting capability gaps.

Injected dynamically into every agent by the runner -- not part of the
assignable tool registry. When an agent cannot fulfil a user's request it
calls this tool to record the gap in the feedback table.
"""
from __future__ import annotations

import uuid

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.feedback import Feedback, FeedbackSource


def build_report_capability_gap_tool(
    db: AsyncSession,
    session_id: uuid.UUID,
    agent_slug: str,
):
    """Return a @tool bound to a specific chat session, db session, and agent."""

    @tool
    async def report_capability_gap(
        user_request: str,
        gap_description: str,
        category: str = "capability_gap",
    ) -> str:
        """Report that you cannot fulfill a user's request due to missing
        tools, data access, or capabilities. Call this BEFORE telling
        the user you can't help, so the gap is logged for future improvement.

        Args:
            user_request: What the user asked for.
            gap_description: What is missing (tool, data source, permission, etc.).
            category: One of: capability_gap, missing_data, missing_tool, integration_needed.
        """
        feedback = Feedback(
            source=FeedbackSource.AGENT,
            category=category,
            content=gap_description,
            user_query=user_request,
            agent_slug=agent_slug,
            session_id=session_id,
        )
        db.add(feedback)
        await db.flush()
        return (
            "Gap recorded. Thank the user for their question, explain what "
            "you cannot do, and suggest alternatives if possible."
        )

    return report_capability_gap
