"""Unit tests for auth security (no DB, no app)."""
import pytest
from app.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


def test_hash_password_returns_different_each_time():
    """hash_password produces different hashes for the same password (salt)."""
    a = hash_password("secret")
    b = hash_password("secret")
    assert a != b
    assert len(a) > 0


def test_verify_password_accepts_correct_password():
    """verify_password returns True for correct plain text vs hash."""
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True


def test_verify_password_rejects_wrong_password():
    """verify_password returns False for wrong plain text."""
    hashed = hash_password("mypassword")
    assert verify_password("wrong", hashed) is False


def test_create_access_token_decode_roundtrip():
    """create_access_token produces a token that decode_token decodes (as access)."""
    token = create_access_token("user-id-123")
    assert isinstance(token, str)
    payload = decode_token(token)
    assert payload is not None
    assert payload.get("sub") == "user-id-123"
    assert payload.get("type") == "access"
    assert "exp" in payload


def test_create_refresh_token_decode_roundtrip():
    """create_refresh_token produces a token that decode_token decodes (as refresh)."""
    token = create_refresh_token("user-id-456")
    assert isinstance(token, str)
    payload = decode_token(token)
    assert payload is not None
    assert payload.get("sub") == "user-id-456"
    assert payload.get("type") == "refresh"


def test_decode_token_invalid_returns_none():
    """decode_token returns None for invalid or tampered token."""
    assert decode_token("invalid") is None
    assert decode_token("") is None
    # Valid shape but wrong signature
    assert decode_token("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ4In0.fake") is None
