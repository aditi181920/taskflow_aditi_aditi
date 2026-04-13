"""Integration tests for authentication endpoints."""

import time
import pytest
from tests.conftest import register_user, auth_header

pytestmark = pytest.mark.anyio

TS = str(int(time.time() * 1000))[-8:]


# ── Register ──────────────────────────────────────────────

async def test_register_success(client):
    resp = await client.post(
        "/auth/register",
        json={"name": "Auth Test", "email": f"authtest{TS}@example.com", "password": "testpass123"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "token" in data
    assert data["user"]["email"] == f"authtest{TS}@example.com"
    assert data["user"]["name"] == "Auth Test"
    assert "id" in data["user"]
    assert "created_at" in data["user"]
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]


async def test_register_duplicate_email(client):
    email = f"dup{TS}@example.com"
    await register_user(client, "First", email, "pass123")
    resp = await client.post(
        "/auth/register",
        json={"name": "Second", "email": email, "password": "pass123"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "email already registered"


async def test_register_missing_fields(client):
    resp = await client.post("/auth/register", json={})
    assert resp.status_code == 400
    data = resp.json()
    assert data["error"] == "validation failed"
    assert "name" in data["fields"]
    assert "email" in data["fields"]
    assert "password" in data["fields"]


async def test_register_empty_name(client):
    resp = await client.post(
        "/auth/register",
        json={"name": "", "email": f"empty{TS}@example.com", "password": "pass123"},
    )
    assert resp.status_code == 400


async def test_register_whitespace_name(client):
    resp = await client.post(
        "/auth/register",
        json={"name": "   ", "email": f"ws{TS}@example.com", "password": "pass123"},
    )
    assert resp.status_code == 400


async def test_register_invalid_email(client):
    resp = await client.post(
        "/auth/register",
        json={"name": "Test", "email": "not-an-email", "password": "pass123"},
    )
    assert resp.status_code == 400
    assert "email" in resp.json()["fields"]


async def test_register_short_password(client):
    resp = await client.post(
        "/auth/register",
        json={"name": "Test", "email": f"short{TS}@example.com", "password": "12345"},
    )
    assert resp.status_code == 400
    assert "password" in resp.json()["fields"]


async def test_register_name_is_stripped(client):
    resp = await client.post(
        "/auth/register",
        json={"name": "  Padded Name  ", "email": f"pad{TS}@example.com", "password": "pass123"},
    )
    assert resp.status_code == 201
    assert resp.json()["user"]["name"] == "Padded Name"


# ── Login ─────────────────────────────────────────────────

async def test_login_success(client):
    email = f"logintest{TS}@example.com"
    await register_user(client, "Login Test", email, "mypassword")
    resp = await client.post("/auth/login", json={"email": email, "password": "mypassword"})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["user"]["email"] == email


async def test_login_wrong_password(client):
    email = f"wrongpw{TS}@example.com"
    await register_user(client, "Wrong PW", email, "correct")
    resp = await client.post("/auth/login", json={"email": email, "password": "incorrect"})
    assert resp.status_code == 401
    assert resp.json()["error"] == "unauthorized"


async def test_login_nonexistent_user(client):
    resp = await client.post(
        "/auth/login",
        json={"email": f"nobody{TS}@example.com", "password": "anything"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "unauthorized"


async def test_login_missing_fields(client):
    resp = await client.post("/auth/login", json={})
    assert resp.status_code == 400


# ── Auth middleware ───────────────────────────────────────

async def test_protected_route_no_token(client):
    resp = await client.get("/projects")
    assert resp.status_code == 401


async def test_protected_route_invalid_token(client):
    resp = await client.get("/projects", headers={"Authorization": "Bearer garbage.token.here"})
    assert resp.status_code == 401


async def test_protected_route_malformed_header(client):
    resp = await client.get("/projects", headers={"Authorization": "NotBearer token"})
    assert resp.status_code == 401
