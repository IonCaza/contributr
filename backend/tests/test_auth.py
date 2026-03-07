"""Auth API tests."""
import pytest

pytestmark = pytest.mark.asyncio


async def test_login_invalid_credentials_returns_401(client):
    response = await client.post(
        "/api/auth/login",
        json={"username": "nonexistent", "password": "wrong"},
    )
    assert response.status_code == 401
    assert "detail" in response.json()


async def test_register_first_user_returns_201_or_registration_closed(client):
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "first@example.com",
            "username": "firstuser",
            "password": "firstpass123",
            "full_name": "First User",
        },
    )
    assert response.status_code in (201, 403)
    if response.status_code == 201:
        data = response.json()
        assert data["username"] == "firstuser"
        assert data["email"] == "first@example.com"
        assert "id" in data


async def test_login_success_returns_tokens(client, auth_headers):
    """Login with the testuser created by auth_headers fixture."""
    response = await client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"].lower() == "bearer"


async def test_me_returns_user(client, auth_headers):
    response = await client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert "id" in data
    assert "email" in data


async def test_protected_route_without_token_returns_401(client):
    response = await client.get("/api/projects")
    assert response.status_code == 401


async def test_refresh_returns_new_tokens(client, auth_headers):
    """Login to get a refresh token, then use it."""
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "testpass123"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    response = await client.post(
        f"/api/auth/refresh?refresh_token={refresh_token}",
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
