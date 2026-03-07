"""Pytest fixtures for API tests."""
import os

if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.main import app
from app.config import settings
from app.db.base import get_db
from app.db.models import User
from app.auth.security import hash_password, create_access_token

# NullPool avoids asyncpg connection-reuse across different event loops.
_test_engine = create_async_engine(
    settings.database_url, echo=False, poolclass=NullPool
)
_TestSession = async_sessionmaker(
    _test_engine, class_=AsyncSession, expire_on_commit=False
)


async def _override_get_db():
    async with _TestSession() as session:
        yield session


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture
async def client():
    """Async HTTP client bound to the FastAPI app (no live server)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_headers():
    """Create a test user in the DB and return Authorization headers."""
    async with _TestSession() as db:
        result = await db.execute(select(User).where(User.username == "testuser"))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                email="test@example.com",
                username="testuser",
                hashed_password=hash_password("testpass123"),
                full_name="Test User",
                is_admin=True,
            )
            db.add(user)
            try:
                await db.commit()
                await db.refresh(user)
            except IntegrityError:
                await db.rollback()
                result = await db.execute(
                    select(User).where(User.username == "testuser")
                )
                user = result.scalar_one()
        user_id = str(user.id)
    token = create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def project_id(client, auth_headers):
    """Create a project and return its ID (unique per test)."""
    import uuid

    resp = await client.post(
        "/api/projects",
        headers=auth_headers,
        json={"name": f"fixture-project-{uuid.uuid4().hex[:8]}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]
