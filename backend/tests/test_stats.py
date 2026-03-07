"""Stats API tests."""
import pytest

pytestmark = pytest.mark.asyncio


async def test_daily_stats_returns_200(client, auth_headers):
    response = await client.get("/api/stats/daily", headers=auth_headers)
    assert response.status_code == 200


async def test_weekly_stats_returns_200(client, auth_headers):
    response = await client.get("/api/stats/weekly", headers=auth_headers)
    assert response.status_code == 200


async def test_monthly_stats_returns_200(client, auth_headers):
    response = await client.get("/api/stats/monthly", headers=auth_headers)
    assert response.status_code == 200


async def test_delivery_summary_returns_200(client, auth_headers):
    response = await client.get("/api/stats/delivery-summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "active_contributors_30d" in data
    assert "total_contributors" in data


async def test_trends_returns_200(client, auth_headers):
    response = await client.get("/api/stats/trends", headers=auth_headers)
    assert response.status_code == 200


async def test_daily_stats_with_filters(client, auth_headers, project_id):
    response = await client.get(
        "/api/stats/daily",
        headers=auth_headers,
        params={"project_id": project_id},
    )
    assert response.status_code == 200


async def test_stats_without_auth_returns_401(client):
    response = await client.get("/api/stats/daily")
    assert response.status_code == 401
