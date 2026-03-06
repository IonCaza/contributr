from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_admin
from app.config import settings as app_settings
from app.db.base import get_db
from app.db.models.ai_settings import AiSettings, SINGLETON_ID
from app.db.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai-settings", tags=["ai-settings"])


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(app_settings.secret_key.encode()).digest())
    return Fernet(key)


def _encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def _decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return ""


class AiSettingsOut(BaseModel):
    enabled: bool
    model: str
    has_api_key: bool
    base_url: str | None
    temperature: float
    max_iterations: int

    model_config = {"from_attributes": True}


class AiSettingsUpdate(BaseModel):
    enabled: bool | None = None
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    temperature: float | None = None
    max_iterations: int | None = None


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
    return AiSettingsOut(
        enabled=row.enabled,
        model=row.model,
        has_api_key=bool(row.api_key_encrypted),
        base_url=row.base_url,
        temperature=row.temperature,
        max_iterations=row.max_iterations,
    )


@router.put("", response_model=AiSettingsOut)
async def update_ai_settings(
    body: AiSettingsUpdate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_or_create(db)
    if body.enabled is not None:
        row.enabled = body.enabled
    if body.model is not None:
        row.model = body.model
    if body.api_key is not None:
        row.api_key_encrypted = _encrypt(body.api_key) if body.api_key else None
    if body.base_url is not None:
        row.base_url = body.base_url or None
    if body.temperature is not None:
        row.temperature = body.temperature
    if body.max_iterations is not None:
        row.max_iterations = body.max_iterations
    await db.commit()
    await db.refresh(row)
    return AiSettingsOut(
        enabled=row.enabled,
        model=row.model,
        has_api_key=bool(row.api_key_encrypted),
        base_url=row.base_url,
        temperature=row.temperature,
        max_iterations=row.max_iterations,
    )


@router.get("/status", response_model=AiStatusOut)
async def ai_status(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lightweight check for any authenticated user: is AI enabled and configured?"""
    result = await db.execute(select(AiSettings).where(AiSettings.id == SINGLETON_ID))
    row = result.scalar_one_or_none()
    if row is None:
        return AiStatusOut(enabled=False, configured=False)
    configured = bool(row.api_key_encrypted) and bool(row.model)
    return AiStatusOut(enabled=row.enabled, configured=configured)
