"""Teams API tests."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio

_u = lambda: uuid.uuid4().hex[:8]


async def test_list_teams_returns_200(client, auth_headers):
    response = await client.get("/api/teams/", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_list_teams_filter_by_project(client, auth_headers, project_id):
    response = await client.get(
        "/api/teams/", headers=auth_headers, params={"project_id": project_id}
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_create_team_returns_201(client, auth_headers, project_id):
    response = await client.post(
        "/api/teams/",
        headers=auth_headers,
        json={"project_id": project_id, "name": f"team-{_u()}", "description": "First team"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["project_id"] == project_id
    assert "id" in data


async def test_get_team_returns_200(client, auth_headers, project_id):
    create = await client.post(
        "/api/teams/",
        headers=auth_headers,
        json={"project_id": project_id, "name": f"team-{_u()}"},
    )
    team_id = create.json()["id"]

    response = await client.get(f"/api/teams/{team_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == team_id


async def test_update_team_returns_200(client, auth_headers, project_id):
    create = await client.post(
        "/api/teams/",
        headers=auth_headers,
        json={"project_id": project_id, "name": f"team-{_u()}"},
    )
    team_id = create.json()["id"]

    new_name = f"updated-{_u()}"
    response = await client.put(
        f"/api/teams/{team_id}",
        headers=auth_headers,
        json={"name": new_name},
    )
    assert response.status_code == 200
    assert response.json()["name"] == new_name


async def test_delete_team_returns_204(client, auth_headers, project_id):
    create = await client.post(
        "/api/teams/",
        headers=auth_headers,
        json={"project_id": project_id, "name": f"team-{_u()}"},
    )
    team_id = create.json()["id"]

    response = await client.delete(f"/api/teams/{team_id}", headers=auth_headers)
    assert response.status_code == 204


async def test_get_team_members_returns_200(client, auth_headers, project_id):
    create = await client.post(
        "/api/teams/",
        headers=auth_headers,
        json={"project_id": project_id, "name": f"team-{_u()}"},
    )
    team_id = create.json()["id"]

    response = await client.get(f"/api/teams/{team_id}/members", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_get_nonexistent_team_returns_404(client, auth_headers):
    response = await client.get(
        "/api/teams/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert response.status_code == 404
