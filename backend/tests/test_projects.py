"""Projects API tests."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio

_u = lambda: uuid.uuid4().hex[:8]


async def test_list_projects_returns_200(client, auth_headers):
    response = await client.get("/api/projects", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_create_project_returns_201(client, auth_headers):
    name = f"project-{_u()}"
    response = await client.post(
        "/api/projects",
        headers=auth_headers,
        json={"name": name, "description": "A test project"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == name
    assert data["description"] == "A test project"
    assert "id" in data


async def test_get_project_returns_200(client, auth_headers):
    name = f"project-{_u()}"
    create_resp = await client.post(
        "/api/projects",
        headers=auth_headers,
        json={"name": name},
    )
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    response = await client.get(f"/api/projects/{project_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == project_id
    assert data["name"] == name
    assert "repositories" in data
    assert "contributors" in data
