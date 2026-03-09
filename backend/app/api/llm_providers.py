from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm.manager import encrypt_key
from app.auth.dependencies import require_admin
from app.db.base import get_db
from app.db.models.llm_provider import LlmProvider
from app.db.models.agent_config import AgentConfig
from app.db.models.user import User

router = APIRouter(prefix="/ai/llm-providers", tags=["ai"])


class LlmProviderOut(BaseModel):
    id: uuid.UUID
    name: str
    provider_type: str
    model: str
    model_type: str
    has_api_key: bool
    base_url: str | None
    temperature: float
    context_window: int | None
    is_default: bool

    model_config = {"from_attributes": True}


class LlmProviderCreate(BaseModel):
    name: str
    provider_type: str = "openai"
    model: str
    model_type: str = "chat"
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.1
    context_window: int | None = None
    is_default: bool = False


class LlmProviderUpdate(BaseModel):
    name: str | None = None
    provider_type: str | None = None
    model: str | None = None
    model_type: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    temperature: float | None = None
    context_window: int | None = None
    is_default: bool | None = None


def _to_out(row: LlmProvider) -> LlmProviderOut:
    return LlmProviderOut(
        id=row.id,
        name=row.name,
        provider_type=row.provider_type,
        model=row.model,
        model_type=row.model_type,
        has_api_key=bool(row.api_key_encrypted),
        base_url=row.base_url,
        temperature=row.temperature,
        context_window=row.context_window,
        is_default=row.is_default,
    )


@router.get("", response_model=list[LlmProviderOut])
async def list_providers(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(LlmProvider).order_by(LlmProvider.name))
    return [_to_out(r) for r in result.scalars().all()]


@router.post("", response_model=LlmProviderOut, status_code=status.HTTP_201_CREATED)
async def create_provider(
    body: LlmProviderCreate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if body.is_default:
        await _clear_default(db)

    row = LlmProvider(
        name=body.name,
        provider_type=body.provider_type,
        model=body.model,
        model_type=body.model_type,
        api_key_encrypted=encrypt_key(body.api_key) if body.api_key else None,
        base_url=body.base_url or None,
        temperature=body.temperature,
        context_window=body.context_window,
        is_default=body.is_default,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.put("/{provider_id}", response_model=LlmProviderOut)
async def update_provider(
    provider_id: uuid.UUID,
    body: LlmProviderUpdate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(LlmProvider, provider_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    if body.name is not None:
        row.name = body.name
    if body.provider_type is not None:
        row.provider_type = body.provider_type
    if body.model is not None:
        row.model = body.model
    if body.model_type is not None:
        row.model_type = body.model_type
    if body.api_key is not None:
        row.api_key_encrypted = encrypt_key(body.api_key) if body.api_key else None
    if body.base_url is not None:
        row.base_url = body.base_url or None
    if body.temperature is not None:
        row.temperature = body.temperature
    if body.context_window is not None:
        row.context_window = body.context_window if body.context_window else None
    if body.is_default is not None:
        if body.is_default:
            await _clear_default(db)
        row.is_default = body.is_default

    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(LlmProvider, provider_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    refs = await db.execute(
        select(AgentConfig.id).where(AgentConfig.llm_provider_id == provider_id).limit(1)
    )
    if refs.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete provider that is assigned to an agent. Reassign or delete the agent first.",
        )

    await db.delete(row)
    await db.commit()


async def _clear_default(db: AsyncSession) -> None:
    result = await db.execute(select(LlmProvider).where(LlmProvider.is_default.is_(True)))
    for p in result.scalars().all():
        p.is_default = False
