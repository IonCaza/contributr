"""Unit tests for app.auth.dependencies (mocked DB + token)."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.dependencies import get_current_user, require_admin

pytestmark = pytest.mark.asyncio


def _creds(token: str = "tok") -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _mock_db(user=None):
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db.execute.return_value = result
    return db


@patch("app.auth.dependencies.decode_token", return_value=None)
async def test_expired_token_raises_401(mock_decode):
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_creds(), _mock_db())
    assert exc.value.status_code == 401


@patch("app.auth.dependencies.decode_token", return_value={"type": "refresh", "sub": "123"})
async def test_non_access_token_raises_401(mock_decode):
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_creds(), _mock_db())
    assert exc.value.status_code == 401


@patch("app.auth.dependencies.decode_token", return_value={"type": "access"})
async def test_missing_sub_raises_401(mock_decode):
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_creds(), _mock_db())
    assert exc.value.status_code == 401


@patch("app.auth.dependencies.decode_token")
async def test_user_not_found_raises_401(mock_decode):
    uid = str(uuid.uuid4())
    mock_decode.return_value = {"type": "access", "sub": uid}
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_creds(), _mock_db(user=None))
    assert exc.value.status_code == 401


@patch("app.auth.dependencies.decode_token")
async def test_inactive_user_raises_401(mock_decode):
    uid = str(uuid.uuid4())
    mock_decode.return_value = {"type": "access", "sub": uid}
    user = MagicMock()
    user.is_active = False
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_creds(), _mock_db(user=user))
    assert exc.value.status_code == 401


@patch("app.auth.dependencies.decode_token")
async def test_valid_token_returns_user(mock_decode):
    uid = str(uuid.uuid4())
    mock_decode.return_value = {"type": "access", "sub": uid}
    user = MagicMock()
    user.is_active = True
    result = await get_current_user(_creds(), _mock_db(user=user))
    assert result is user


async def test_require_admin_passes_for_admin():
    user = MagicMock()
    user.is_admin = True
    result = await require_admin(user)
    assert result is user


async def test_require_admin_rejects_non_admin():
    user = MagicMock()
    user.is_admin = False
    with pytest.raises(HTTPException) as exc:
        await require_admin(user)
    assert exc.value.status_code == 403
