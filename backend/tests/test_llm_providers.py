"""LLM Providers API tests (admin-only)."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio

_u = lambda: uuid.uuid4().hex[:8]


async def test_list_llm_providers_returns_200(client, auth_headers):
    response = await client.get("/api/ai/llm-providers", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_create_llm_provider_returns_201(client, auth_headers):
    response = await client.post(
        "/api/ai/llm-providers",
        headers=auth_headers,
        json={
            "name": f"provider-{_u()}",
            "provider_type": "openai",
            "model": "gpt-4o-mini",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["model"] == "gpt-4o-mini"
    assert "id" in data


async def test_update_llm_provider(client, auth_headers):
    create = await client.post(
        "/api/ai/llm-providers",
        headers=auth_headers,
        json={"name": f"prov-{_u()}", "provider_type": "openai", "model": "gpt-4o"},
    )
    provider_id = create.json()["id"]

    new_name = f"updated-{_u()}"
    response = await client.put(
        f"/api/ai/llm-providers/{provider_id}",
        headers=auth_headers,
        json={"name": new_name},
    )
    assert response.status_code == 200
    assert response.json()["name"] == new_name


async def test_delete_llm_provider_returns_204(client, auth_headers):
    create = await client.post(
        "/api/ai/llm-providers",
        headers=auth_headers,
        json={"name": f"del-{_u()}", "provider_type": "openai", "model": "gpt-3.5"},
    )
    provider_id = create.json()["id"]

    response = await client.delete(
        f"/api/ai/llm-providers/{provider_id}", headers=auth_headers
    )
    assert response.status_code == 204


async def test_llm_providers_without_auth_returns_401(client):
    response = await client.get("/api/ai/llm-providers")
    assert response.status_code == 401
