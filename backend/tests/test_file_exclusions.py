"""File Exclusions API tests."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio

_u = lambda: uuid.uuid4().hex[:8]


async def test_list_file_exclusions_returns_200(client, auth_headers):
    response = await client.get("/api/file-exclusions", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_create_file_exclusion_returns_201(client, auth_headers):
    pattern = f"*.{_u()}"
    response = await client.post(
        "/api/file-exclusions",
        headers=auth_headers,
        json={"pattern": pattern, "description": "Test exclusion"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["pattern"] == pattern
    assert data["enabled"] is True
    assert "id" in data


async def test_update_file_exclusion(client, auth_headers):
    pattern = f"*.{_u()}"
    create = await client.post(
        "/api/file-exclusions",
        headers=auth_headers,
        json={"pattern": pattern},
    )
    assert create.status_code == 201
    pattern_id = create.json()["id"]

    response = await client.put(
        f"/api/file-exclusions/{pattern_id}",
        headers=auth_headers,
        json={"enabled": False, "description": "Disabled"},
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is False


async def test_delete_file_exclusion_returns_204(client, auth_headers):
    pattern = f"*.{_u()}"
    create = await client.post(
        "/api/file-exclusions",
        headers=auth_headers,
        json={"pattern": pattern},
    )
    assert create.status_code == 201
    pattern_id = create.json()["id"]

    response = await client.delete(
        f"/api/file-exclusions/{pattern_id}", headers=auth_headers
    )
    assert response.status_code == 204


async def test_load_defaults_returns_count(client, auth_headers):
    response = await client.post(
        "/api/file-exclusions/load-defaults", headers=auth_headers
    )
    assert response.status_code == 200
    assert "added" in response.json()


async def test_active_patterns_no_auth_required(client):
    response = await client.get("/api/file-exclusions/active-patterns")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
