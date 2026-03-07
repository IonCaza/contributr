"""AI Settings API tests (admin-only)."""
import pytest

pytestmark = pytest.mark.asyncio


async def test_get_ai_settings_returns_200(client, auth_headers):
    response = await client.get("/api/ai/settings", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "enabled" in data


async def test_update_ai_settings_returns_200(client, auth_headers):
    response = await client.put(
        "/api/ai/settings",
        headers=auth_headers,
        json={"enabled": True},
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is True


async def test_ai_status_returns_200(client, auth_headers):
    response = await client.get("/api/ai/settings/status", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "enabled" in data
    assert "configured" in data


async def test_ai_settings_without_auth_returns_401(client):
    response = await client.get("/api/ai/settings")
    assert response.status_code == 401
