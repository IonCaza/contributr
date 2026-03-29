from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user, require_admin
from app.db.base import get_db
from app.db.models.agent_config import AgentConfig, AgentToolAssignment, SupervisorMember
from app.db.models.knowledge_graph import AgentKnowledgeGraphAssignment, KnowledgeGraph
from app.db.models.user import User

router = APIRouter(prefix="/ai/agents", tags=["ai"])


class AgentOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    agent_type: str
    llm_provider_id: uuid.UUID | None
    system_prompt: str
    max_iterations: int
    summary_token_limit: int | None
    enabled: bool
    is_builtin: bool
    tool_slugs: list[str]
    knowledge_graph_ids: list[uuid.UUID]
    member_agent_ids: list[uuid.UUID]

    model_config = {"from_attributes": True}


class AgentCreate(BaseModel):
    slug: str
    name: str
    description: str | None = None
    agent_type: str = "standard"
    llm_provider_id: uuid.UUID | None = None
    system_prompt: str = ""
    max_iterations: int = 10
    summary_token_limit: int | None = None
    enabled: bool = True
    tool_slugs: list[str] = []
    knowledge_graph_ids: list[uuid.UUID] = []
    member_agent_ids: list[uuid.UUID] = []


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    agent_type: str | None = None
    llm_provider_id: uuid.UUID | None = None
    system_prompt: str | None = None
    max_iterations: int | None = None
    summary_token_limit: int | None = None
    enabled: bool | None = None
    tool_slugs: list[str] | None = None
    knowledge_graph_ids: list[uuid.UUID] | None = None
    member_agent_ids: list[uuid.UUID] | None = None


def _agent_query():
    return (
        select(AgentConfig)
        .options(
            selectinload(AgentConfig.tool_assignments),
            selectinload(AgentConfig.knowledge_graph_assignments),
            selectinload(AgentConfig.member_agents),
        )
    )


def _to_out(row: AgentConfig) -> AgentOut:
    return AgentOut(
        id=row.id,
        slug=row.slug,
        name=row.name,
        description=row.description,
        agent_type=row.agent_type,
        llm_provider_id=row.llm_provider_id,
        system_prompt=row.system_prompt,
        max_iterations=row.max_iterations,
        summary_token_limit=row.summary_token_limit,
        enabled=row.enabled,
        is_builtin=row.is_builtin,
        tool_slugs=[a.tool_slug for a in row.tool_assignments],
        knowledge_graph_ids=[a.knowledge_graph_id for a in row.knowledge_graph_assignments],
        member_agent_ids=[m.id for m in (row.member_agents or [])],
    )


async def _sync_members(
    db: AsyncSession, agent_id: uuid.UUID, member_ids: list[uuid.UUID],
) -> None:
    """Replace all supervisor member assignments for an agent."""
    existing = (await db.execute(
        select(SupervisorMember).where(SupervisorMember.supervisor_id == agent_id)
    )).scalars().all()
    for row in existing:
        await db.delete(row)
    await db.flush()

    for mid in member_ids:
        target = await db.get(AgentConfig, mid)
        if not target:
            continue
        if target.agent_type == "supervisor":
            continue
        db.add(SupervisorMember(supervisor_id=agent_id, member_agent_id=mid))


@router.get("", response_model=list[AgentOut])
async def list_agents(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(_agent_query().order_by(AgentConfig.name))
    return [_to_out(r) for r in result.unique().scalars().all()]


@router.get("/{slug}", response_model=AgentOut)
async def get_agent(
    slug: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(_agent_query().where(AgentConfig.slug == slug))
    row = result.unique().scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return _to_out(row)


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: AgentCreate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(AgentConfig.id).where(AgentConfig.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent slug already exists")

    if body.agent_type not in ("standard", "supervisor"):
        raise HTTPException(status_code=422, detail="agent_type must be 'standard' or 'supervisor'")

    row = AgentConfig(
        slug=body.slug,
        name=body.name,
        description=body.description,
        agent_type=body.agent_type,
        llm_provider_id=body.llm_provider_id,
        system_prompt=body.system_prompt,
        max_iterations=body.max_iterations,
        summary_token_limit=body.summary_token_limit,
        enabled=body.enabled,
        is_builtin=False,
    )
    db.add(row)
    await db.flush()

    for slug in body.tool_slugs:
        db.add(AgentToolAssignment(agent_id=row.id, tool_slug=slug))
    for kg_id in body.knowledge_graph_ids:
        if await db.get(KnowledgeGraph, kg_id):
            db.add(AgentKnowledgeGraphAssignment(agent_id=row.id, knowledge_graph_id=kg_id))

    if body.agent_type == "supervisor" and body.member_agent_ids:
        await _sync_members(db, row.id, body.member_agent_ids)

    await db.commit()

    refreshed = await db.execute(_agent_query().where(AgentConfig.id == row.id))
    return _to_out(refreshed.unique().scalar_one())


@router.put("/{slug}", response_model=AgentOut)
async def update_agent(
    slug: str,
    body: AgentUpdate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(_agent_query().where(AgentConfig.slug == slug))
    row = result.unique().scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    if body.name is not None:
        row.name = body.name
    if body.description is not None:
        row.description = body.description
    if body.agent_type is not None:
        if body.agent_type not in ("standard", "supervisor"):
            raise HTTPException(status_code=422, detail="agent_type must be 'standard' or 'supervisor'")
        row.agent_type = body.agent_type
    if body.llm_provider_id is not None:
        row.llm_provider_id = body.llm_provider_id
    if body.system_prompt is not None:
        row.system_prompt = body.system_prompt
    if body.max_iterations is not None:
        row.max_iterations = body.max_iterations
    if body.summary_token_limit is not None:
        row.summary_token_limit = body.summary_token_limit if body.summary_token_limit else None
    if body.enabled is not None:
        row.enabled = body.enabled

    if body.tool_slugs is not None:
        for existing in list(row.tool_assignments):
            await db.delete(existing)
        await db.flush()
        for ts in body.tool_slugs:
            db.add(AgentToolAssignment(agent_id=row.id, tool_slug=ts))

    if body.knowledge_graph_ids is not None:
        for existing in list(row.knowledge_graph_assignments):
            await db.delete(existing)
        await db.flush()
        for kg_id in body.knowledge_graph_ids:
            if await db.get(KnowledgeGraph, kg_id):
                db.add(AgentKnowledgeGraphAssignment(agent_id=row.id, knowledge_graph_id=kg_id))

    if body.member_agent_ids is not None:
        await _sync_members(db, row.id, body.member_agent_ids)

    await db.commit()

    refreshed = await db.execute(_agent_query().where(AgentConfig.id == row.id))
    return _to_out(refreshed.unique().scalar_one())


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    slug: str,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AgentConfig).where(AgentConfig.slug == slug))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if row.is_builtin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Built-in agents cannot be deleted.",
        )
    await db.delete(row)
    await db.commit()
