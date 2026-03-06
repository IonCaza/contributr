from __future__ import annotations

from langchain_community.chat_models import ChatLiteLLM
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ai_settings import _decrypt
from app.config import settings
from app.db.models.ai_settings import AiSettings, SINGLETON_ID


async def get_ai_config(db: AsyncSession) -> dict:
    """Load AI config from the database, falling back to env vars."""
    result = await db.execute(select(AiSettings).where(AiSettings.id == SINGLETON_ID))
    row = result.scalar_one_or_none()

    if row and row.enabled and row.api_key_encrypted:
        return {
            "model": row.model,
            "api_key": _decrypt(row.api_key_encrypted),
            "base_url": row.base_url or None,
            "temperature": row.temperature,
            "max_iterations": row.max_iterations,
            "enabled": True,
        }

    if settings.ai_api_key:
        return {
            "model": settings.ai_model,
            "api_key": settings.ai_api_key,
            "base_url": settings.ai_base_url,
            "temperature": settings.ai_temperature,
            "max_iterations": 10,
            "enabled": True,
        }

    return {"enabled": False}


def build_llm(config: dict, streaming: bool = True) -> ChatLiteLLM:
    kwargs: dict = {
        "model": config["model"],
        "temperature": config["temperature"],
        "streaming": streaming,
    }
    if config.get("api_key"):
        kwargs["api_key"] = config["api_key"]
    if config.get("base_url"):
        kwargs["api_base"] = config["base_url"]
    return ChatLiteLLM(**kwargs)
