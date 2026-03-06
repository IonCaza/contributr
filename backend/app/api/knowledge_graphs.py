from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_admin
from app.db.base import get_db
from app.db.models.knowledge_graph import KnowledgeGraph
from app.db.models.user import User
from app.agents.knowledge.generator import generate_graph_data, generate_content

router = APIRouter(prefix="/ai/knowledge-graphs", tags=["ai"])


class KnowledgeGraphListItem(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    generation_mode: str
    excluded_entities: list[str]
    node_count: int
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class KnowledgeGraphOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    generation_mode: str
    content: str
    graph_data: dict
    excluded_entities: list[str]
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class KnowledgeGraphCreate(BaseModel):
    name: str
    description: str | None = None
    generation_mode: str = "schema_and_entities"


class KnowledgeGraphUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    content: str | None = None
    excluded_entities: list[str] | None = None


VALID_MODES = {"schema_only", "entities_only", "schema_and_entities", "manual"}


def _to_list_item(row: KnowledgeGraph) -> KnowledgeGraphListItem:
    gd = row.graph_data or {}
    return KnowledgeGraphListItem(
        id=row.id,
        name=row.name,
        description=row.description,
        generation_mode=row.generation_mode,
        excluded_entities=row.excluded_entities or [],
        node_count=len(gd.get("nodes", [])),
        created_at=str(row.created_at),
        updated_at=str(row.updated_at),
    )


def _to_out(row: KnowledgeGraph) -> KnowledgeGraphOut:
    return KnowledgeGraphOut(
        id=row.id,
        name=row.name,
        description=row.description,
        generation_mode=row.generation_mode,
        content=row.content,
        graph_data=row.graph_data or {},
        excluded_entities=row.excluded_entities or [],
        created_at=str(row.created_at),
        updated_at=str(row.updated_at),
    )


@router.get("", response_model=list[KnowledgeGraphListItem])
async def list_knowledge_graphs(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeGraph).order_by(KnowledgeGraph.name))
    return [_to_list_item(r) for r in result.scalars().all()]


@router.get("/{kg_id}", response_model=KnowledgeGraphOut)
async def get_knowledge_graph(
    kg_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeGraph).where(KnowledgeGraph.id == kg_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge graph not found")
    return _to_out(row)


@router.post("", response_model=KnowledgeGraphOut, status_code=status.HTTP_201_CREATED)
async def create_knowledge_graph(
    body: KnowledgeGraphCreate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if body.generation_mode not in VALID_MODES:
        raise HTTPException(status_code=422, detail=f"Invalid mode. Must be one of: {', '.join(VALID_MODES)}")

    existing = await db.execute(select(KnowledgeGraph.id).where(KnowledgeGraph.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Knowledge graph name already exists")

    graph_data: dict = {}
    content = ""
    if body.generation_mode != "manual":
        graph_data = await generate_graph_data(db, body.generation_mode, [])
        content = generate_content(graph_data, body.generation_mode)

    row = KnowledgeGraph(
        name=body.name,
        description=body.description,
        generation_mode=body.generation_mode,
        content=content,
        graph_data=graph_data,
        excluded_entities=[],
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.put("/{kg_id}", response_model=KnowledgeGraphOut)
async def update_knowledge_graph(
    kg_id: uuid.UUID,
    body: KnowledgeGraphUpdate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeGraph).where(KnowledgeGraph.id == kg_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge graph not found")

    if body.name is not None:
        row.name = body.name
    if body.description is not None:
        row.description = body.description
    if body.content is not None:
        row.content = body.content
    if body.excluded_entities is not None:
        row.excluded_entities = body.excluded_entities

    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.delete("/{kg_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_graph(
    kg_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeGraph).where(KnowledgeGraph.id == kg_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge graph not found")
    await db.delete(row)
    await db.commit()


@router.post("/{kg_id}/regenerate", response_model=KnowledgeGraphOut)
async def regenerate_knowledge_graph(
    kg_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeGraph).where(KnowledgeGraph.id == kg_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge graph not found")
    if row.generation_mode == "manual":
        raise HTTPException(status_code=422, detail="Cannot regenerate a manual knowledge graph")

    graph_data = await generate_graph_data(db, row.generation_mode, row.excluded_entities or [])
    content = generate_content(graph_data, row.generation_mode)
    row.graph_data = graph_data
    row.content = content
    await db.commit()
    await db.refresh(row)
    return _to_out(row)
