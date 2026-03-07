"""SSH Keys API tests."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio

_u = lambda: uuid.uuid4().hex[:8]


async def test_list_ssh_keys_returns_200(client, auth_headers):
    response = await client.get("/api/ssh-keys", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_create_ssh_key_returns_201(client, auth_headers):
    response = await client.post(
        "/api/ssh-keys",
        headers=auth_headers,
        json={"name": f"key-{_u()}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "public_key" in data
    assert "fingerprint" in data


async def test_create_ssh_key_with_rsa_type(client, auth_headers):
    response = await client.post(
        "/api/ssh-keys",
        headers=auth_headers,
        json={"name": f"rsa-{_u()}", "key_type": "rsa", "rsa_bits": 2048},
    )
    assert response.status_code == 201
    assert response.json()["key_type"] == "rsa"


async def test_delete_ssh_key_returns_204(client, auth_headers):
    create = await client.post(
        "/api/ssh-keys",
        headers=auth_headers,
        json={"name": f"del-{_u()}"},
    )
    key_id = create.json()["id"]

    response = await client.delete(f"/api/ssh-keys/{key_id}", headers=auth_headers)
    assert response.status_code == 204


async def test_delete_nonexistent_ssh_key_returns_404(client, auth_headers):
    response = await client.delete(
        "/api/ssh-keys/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_ssh_keys_without_auth_returns_401(client):
    response = await client.get("/api/ssh-keys")
    assert response.status_code == 401
