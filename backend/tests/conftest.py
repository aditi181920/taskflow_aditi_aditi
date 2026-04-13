"""
Shared fixtures for integration tests.

Creates a fresh database engine per test to avoid asyncpg event loop conflicts.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings

BASE_URL = "http://test"


@pytest.fixture
async def client():
    """Async HTTP client with a fresh DB engine per test."""
    # Create a fresh engine bound to this test's event loop
    test_engine = create_async_engine(settings.DATABASE_URL, pool_size=5, pool_pre_ping=True)

    # Patch the app's database module to use our test engine
    import app.database as db_module
    original_engine = db_module.engine
    db_module.engine = test_engine

    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as c:
        yield c

    # Cleanup
    await test_engine.dispose()
    db_module.engine = original_engine


async def register_user(client: AsyncClient, name: str, email: str, password: str) -> dict:
    """Helper: register a user and return the full response body."""
    resp = await client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    return resp.json()


async def login_user(client: AsyncClient, email: str, password: str) -> str:
    """Helper: login and return the JWT token."""
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    return resp.json()["token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
