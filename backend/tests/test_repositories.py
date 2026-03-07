"""Repositories API tests."""
import pytest

pytestmark = pytest.mark.asyncio


async def test_list_repositories_for_project_returns_200(client, auth_headers, project_id):
    response = await client.get(
        f"/api/projects/{project_id}/repositories",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0
