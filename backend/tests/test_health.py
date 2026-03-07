"""Health endpoint API tests."""
import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    """GET /api/health returns 200 and status ok."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok"}
