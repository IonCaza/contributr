"""Contributors API tests."""
import pytest

pytestmark = pytest.mark.asyncio


async def test_list_contributors_returns_200(client, auth_headers):
    response = await client.get("/api/contributors", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_list_contributors_filter_by_project(client, auth_headers, project_id):
    response = await client.get(
        "/api/contributors",
        headers=auth_headers,
        params={"project_id": project_id},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_duplicates_returns_200(client, auth_headers):
    response = await client.get("/api/contributors/duplicates", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_get_nonexistent_contributor_returns_404(client, auth_headers):
    response = await client.get(
        "/api/contributors/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_contributors_without_auth_returns_401(client):
    response = await client.get("/api/contributors")
    assert response.status_code == 401
