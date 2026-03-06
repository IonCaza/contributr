from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_admin
from app.db.base import get_db
from app.db.models.ai_settings import AiSettings, SINGLETON_ID
from app.db.models.llm_provider import LlmProvider
from app.db.models.agent_config import AgentConfig
from app.db.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai/settings", tags=["ai"])


class AiSettingsOut(BaseModel):
    enabled: bool

    model_config = {"from_attributes": True}


class AiSettingsUpdate(BaseModel):
    enabled: bool | None = None


class AiStatusOut(BaseModel):
    enabled: bool
    configured: bool


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
    return AiSettingsOut(enabled=row.enabled)


@router.put("", response_model=AiSettingsOut)
async def update_ai_settings(
    body: AiSettingsUpdate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_or_create(db)
    if body.enabled is not None:
        row.enabled = body.enabled
    await db.commit()
    await db.refresh(row)
    return AiSettingsOut(enabled=row.enabled)


@router.get("/status", response_model=AiStatusOut)
async def ai_status(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lightweight check: is AI enabled and is there at least one configured provider + agent?"""
    result = await db.execute(select(AiSettings).where(AiSettings.id == SINGLETON_ID))
    row = result.scalar_one_or_none()
    if row is None:
        return AiStatusOut(enabled=False, configured=False)

    has_provider = (await db.execute(
        select(LlmProvider.id).where(LlmProvider.api_key_encrypted.isnot(None)).limit(1)
    )).scalar_one_or_none() is not None

    has_agent = (await db.execute(
        select(AgentConfig.id).where(AgentConfig.enabled.is_(True)).limit(1)
    )).scalar_one_or_none() is not None

    configured = has_provider and has_agent
    return AiStatusOut(enabled=row.enabled, configured=configured)
