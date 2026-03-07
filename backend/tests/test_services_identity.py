"""Unit tests for app.services.identity (mocked DB)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.identity import resolve_contributor

pytestmark = pytest.mark.asyncio


def _mock_session(scalar_result=None):
    """Return an AsyncSession mock that yields scalar_result from execute()."""
    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.scalar_one_or_none.return_value = scalar_result
    session.execute.return_value = result_obj
    return session


async def test_resolve_contributor_creates_new_when_not_found():
    db = _mock_session(scalar_result=None)
    contributor = await resolve_contributor(db, "Alice", "alice@example.com")
    assert contributor.canonical_name == "Alice"
    assert contributor.canonical_email == "alice@example.com"
    db.add.assert_called_once()
    db.flush.assert_awaited_once()


async def test_resolve_contributor_returns_existing():
    existing = MagicMock()
    existing.canonical_name = "Bob"
    existing.canonical_email = "bob@test.com"
    db = _mock_session(scalar_result=existing)

    result = await resolve_contributor(db, "Bob", "bob@test.com")
    assert result is existing
    db.add.assert_not_called()


async def test_resolve_contributor_sets_platform_username():
    existing = MagicMock()
    existing.canonical_name = "Carol"
    existing.azure_username = None
    db = _mock_session(scalar_result=existing)

    result = await resolve_contributor(db, "CarolAzure", "carol@test.com", platform="azure")
    assert result.azure_username == "CarolAzure"


async def test_resolve_contributor_skips_platform_if_already_set():
    existing = MagicMock()
    existing.canonical_name = "Dave"
    existing.github_username = "davegit"
    db = _mock_session(scalar_result=existing)

    await resolve_contributor(db, "DaveNew", "dave@test.com", platform="github")
    assert existing.github_username == "davegit"
