from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.db.models.agent_config import AgentConfig
from app.db.models.ai_settings import AiSettings, SINGLETON_ID
from app.db.models.knowledge_graph import AgentKnowledgeGraphAssignment, KnowledgeGraph

import app.agents.tools.contribution_analytics  # noqa: F401 — registers tools
import app.agents.tools.sql_query  # noqa: F401 — registers tools
import app.agents.tools.delivery_analytics  # noqa: F401 — registers tools
import app.agents.tools.sast_analytics  # noqa: F401 — registers tools
import app.agents.tools.code_access  # noqa: F401 — registers tools
import app.agents.tools.dependency_analytics  # noqa: F401 — registers tools


async def is_ai_enabled(db: AsyncSession) -> bool:
    result = await db.execute(select(AiSettings).where(AiSettings.id == SINGLETON_ID))
    row = result.scalar_one_or_none()
    return bool(row and row.enabled)


async def get_agent_by_slug(db: AsyncSession, slug: str) -> AgentConfig | None:
    result = await db.execute(
        select(AgentConfig)
        .options(
            selectinload(AgentConfig.tool_assignments),
            joinedload(AgentConfig.llm_provider),
            selectinload(AgentConfig.knowledge_graph_assignments)
            .joinedload(AgentKnowledgeGraphAssignment.knowledge_graph),
            selectinload(AgentConfig.member_agents)
            .selectinload(AgentConfig.tool_assignments),
            selectinload(AgentConfig.member_agents)
            .selectinload(AgentConfig.knowledge_graph_assignments)
            .joinedload(AgentKnowledgeGraphAssignment.knowledge_graph),
        )
        .where(AgentConfig.slug == slug, AgentConfig.enabled.is_(True))
    )
    return result.unique().scalar_one_or_none()


async def list_enabled_agents(db: AsyncSession) -> list[AgentConfig]:
    result = await db.execute(
        select(AgentConfig)
        .options(
            selectinload(AgentConfig.tool_assignments),
            joinedload(AgentConfig.llm_provider),
            selectinload(AgentConfig.knowledge_graph_assignments)
            .joinedload(AgentKnowledgeGraphAssignment.knowledge_graph),
            selectinload(AgentConfig.member_agents),
        )
        .where(AgentConfig.enabled.is_(True))
        .order_by(AgentConfig.name)
    )
    return list(result.unique().scalars().all())
