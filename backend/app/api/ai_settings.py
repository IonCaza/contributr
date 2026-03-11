from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_admin
from app.db.base import get_db
from app.db.models.ai_settings import AiSettings, SINGLETON_ID
from app.db.models.llm_provider import LlmProvider
from app.db.models.agent_config import AgentConfig
from app.db.models.user import User
from app.agents.settings_cache import invalidate_cache as _invalidate_memory_cache
from app.agents.memory.extraction import invalidate_extraction_cache as _invalidate_extraction_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai/settings", tags=["ai"])


class AiSettingsOut(BaseModel):
    enabled: bool
    memory_enabled: bool
    memory_embedding_provider_id: uuid.UUID | None = None
    extraction_enabled: bool
    extraction_provider_id: uuid.UUID | None = None
    extraction_enable_inserts: bool
    extraction_enable_updates: bool
    extraction_enable_deletes: bool
    cleanup_threshold_ratio: float
    summary_token_ratio: float

    model_config = {"from_attributes": True}


class AiSettingsUpdate(BaseModel):
    enabled: bool | None = None
    memory_enabled: bool | None = None
    memory_embedding_provider_id: uuid.UUID | None = None
    extraction_enabled: bool | None = None
    extraction_provider_id: uuid.UUID | None = None
    extraction_enable_inserts: bool | None = None
    extraction_enable_updates: bool | None = None
    extraction_enable_deletes: bool | None = None
    cleanup_threshold_ratio: float | None = Field(None, ge=0.3, le=0.9)
    summary_token_ratio: float | None = Field(None, ge=0.01, le=0.10)


_UPDATABLE_FIELDS = [
    "enabled",
    "memory_enabled",
    "memory_embedding_provider_id",
    "extraction_enabled",
    "extraction_provider_id",
    "extraction_enable_inserts",
    "extraction_enable_updates",
    "extraction_enable_deletes",
    "cleanup_threshold_ratio",
    "summary_token_ratio",
]


class AiStatusOut(BaseModel):
    enabled: bool
    configured: bool
    memory_configured: bool


async def _get_or_create(db: AsyncSession) -> AiSettings:
    result = await db.execute(select(AiSettings).where(AiSettings.id == SINGLETON_ID))
    row = result.scalar_one_or_none()
    if row is None:
        row = AiSettings(id=SINGLETON_ID)
        db.add(row)
        await db.flush()
    return row


@router.get("", response_model=AiSettingsOut)
async def get_ai_settings(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_or_create(db)
    await db.commit()
    return AiSettingsOut.model_validate(row)


@router.put("", response_model=AiSettingsOut)
async def update_ai_settings(
    body: AiSettingsUpdate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_or_create(db)
    payload = body.model_dump(exclude_unset=True)
    for field in _UPDATABLE_FIELDS:
        if field in payload:
            setattr(row, field, payload[field])
    await db.commit()
    await db.refresh(row)
    _invalidate_memory_cache()
    _invalidate_extraction_cache()
    return AiSettingsOut.model_validate(row)


@router.get("/status", response_model=AiStatusOut)
async def ai_status(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lightweight check: is AI enabled and is there at least one configured provider + agent?"""
    result = await db.execute(select(AiSettings).where(AiSettings.id == SINGLETON_ID))
    row = result.scalar_one_or_none()
    if row is None:
        return AiStatusOut(enabled=False, configured=False, memory_configured=False)

    has_provider = (await db.execute(
        select(LlmProvider.id).where(LlmProvider.api_key_encrypted.isnot(None)).limit(1)
    )).scalar_one_or_none() is not None

    has_agent = (await db.execute(
        select(AgentConfig.id).where(AgentConfig.enabled.is_(True)).limit(1)
    )).scalar_one_or_none() is not None

    has_embedding = row.memory_embedding_provider_id is not None
    memory_configured = row.memory_enabled and has_embedding

    configured = has_provider and has_agent
    return AiStatusOut(enabled=row.enabled, configured=configured, memory_configured=memory_configured)
