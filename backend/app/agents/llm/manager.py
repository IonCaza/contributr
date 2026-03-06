from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from langchain_community.chat_models import ChatLiteLLM

from app.config import settings as app_settings
from app.db.models.llm_provider import LlmProvider


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(app_settings.secret_key.encode()).digest())
    return Fernet(key)


def decrypt_key(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return ""


def encrypt_key(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def build_llm_from_provider(provider: LlmProvider, *, streaming: bool = True) -> ChatLiteLLM:
    kwargs: dict = {
        "model": provider.model,
        "temperature": provider.temperature,
        "streaming": streaming,
    }
    if provider.api_key_encrypted:
        api_key = decrypt_key(provider.api_key_encrypted)
        if api_key:
            kwargs["api_key"] = api_key
    if provider.base_url:
        kwargs["api_base"] = provider.base_url
    return ChatLiteLLM(**kwargs)
