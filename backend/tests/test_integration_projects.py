"""Integration tests for project endpoints."""

import time
import pytest
from tests.conftest import register_user, auth_header

pytestmark = pytest.mark.anyio

TS = str(int(time.time() * 1000))[-8:]
_counter = 0


def _uid():
    global _counter
    _counter += 1
    return f"{TS}_{_counter}"


async def _create_user(client):
    uid = _uid()
    data = await register_user(client, f"User {uid}", f"user{uid}@example.com", "pass123")
    return data["token"], data["user"]["id"]


async def _create_project(client, token, name="Test Project", description=None):
    body = {"name": name}
    if description is not None:
        body["description"] = description
    resp = await client.post("/projects", json=body, headers=auth_header(token))
    return resp.json()


# ── Create ────────────────────────────────────────────────

async def test_create_project(client):
    token, user_id = await _create_user(client)
    resp = await client.post(
        "/projects",
        json={"name": "My Project", "description": "A test"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Project"
    assert data["description"] == "A test"
    assert data["owner_id"] == user_id
    assert "id" in data
    assert "created_at" in data


async def test_create_project_without_description(client):
    token, _ = await _create_user(client)
    resp = await client.post(
        "/projects", json={"name": "No desc"}, headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["description"] is None


async def test_create_project_empty_name(client):
    token, _ = await _create_user(client)
    resp = await client.post(
        "/projects", json={"name": ""}, headers=auth_header(token),
    )
    assert resp.status_code == 400


async def test_create_project_whitespace_name(client):
    token, _ = await _create_user(client)
    resp = await client.post(
        "/projects", json={"name": "   "}, headers=auth_header(token),
    )
    assert resp.status_code == 400


async def test_create_project_name_stripped(client):
    token, _ = await _create_user(client)
    resp = await client.post(
        "/projects", json={"name": "  Padded  "}, headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Padded"


# ── List ──────────────────────────────────────────────────

async def test_list_projects_returns_owned(client):
    token, _ = await _create_user(client)
    h = auth_header(token)
    await _create_project(client, token, "P1")
    await _create_project(client, token, "P2")

    resp = await client.get("/projects", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert "projects" in data
    assert len(data["projects"]) == 2
    assert "page" in data
    assert "total" in data
    assert data["total"] == 2


async def test_list_projects_pagination(client):
    token, _ = await _create_user(client)
    h = auth_header(token)
    for i in range(5):
        await _create_project(client, token, f"Page Test {i}")

    resp = await client.get("/projects?page=1&limit=2", headers=h)
    data = resp.json()
    assert len(data["projects"]) == 2
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["limit"] == 2

    resp2 = await client.get("/projects?page=3&limit=2", headers=h)
    data2 = resp2.json()
    assert len(data2["projects"]) == 1


async def test_list_projects_empty_for_new_user(client):
    token, _ = await _create_user(client)
    resp = await client.get("/projects", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["projects"] == []
    assert resp.json()["total"] == 0


# ── Get detail ────────────────────────────────────────────

async def test_get_project_with_tasks(client):
    token, _ = await _create_user(client)
    h = auth_header(token)
    project = await _create_project(client, token, "Detail Test")
    pid = project["id"]

    await client.post(f"/projects/{pid}/tasks", json={"title": "T1"}, headers=h)
    await client.post(f"/projects/{pid}/tasks", json={"title": "T2"}, headers=h)

    resp = await client.get(f"/projects/{pid}", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Detail Test"
    assert len(data["tasks"]) == 2


async def test_get_project_not_found(client):
    token, _ = await _create_user(client)
    resp = await client.get(
        "/projects/00000000-0000-0000-0000-000000000000",
        headers=auth_header(token),
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "not found"


async def test_get_project_invalid_uuid(client):
    token, _ = await _create_user(client)
    resp = await client.get("/projects/not-a-uuid", headers=auth_header(token))
    assert resp.status_code == 400


async def test_get_project_access_control(client):
    """User without ownership or tasks should not see the project."""
    token_a, _ = await _create_user(client)
    token_b, _ = await _create_user(client)

    project = await _create_project(client, token_a, "Private")
    pid = project["id"]

    resp = await client.get(f"/projects/{pid}", headers=auth_header(token_b))
    assert resp.status_code == 404


# ── Update ────────────────────────────────────────────────

async def test_update_project_owner(client):
    token, _ = await _create_user(client)
    project = await _create_project(client, token, "Original", "Old desc")
    pid = project["id"]

    resp = await client.patch(
        f"/projects/{pid}",
        json={"name": "Updated"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"
    assert resp.json()["description"] == "Old desc"


async def test_update_project_clear_description(client):
    token, _ = await _create_user(client)
    project = await _create_project(client, token, "Has Desc", "Will clear")
    pid = project["id"]

    resp = await client.patch(
        f"/projects/{pid}",
        json={"description": None},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["description"] is None


async def test_update_project_non_owner_forbidden(client):
    token_a, _ = await _create_user(client)
    token_b, _ = await _create_user(client)
    project = await _create_project(client, token_a, "Owner A's")
    pid = project["id"]

    resp = await client.patch(
        f"/projects/{pid}",
        json={"name": "Hacked"},
        headers=auth_header(token_b),
    )
    assert resp.status_code == 403


async def test_update_project_empty_body(client):
    token, _ = await _create_user(client)
    project = await _create_project(client, token, "No Change")
    pid = project["id"]

    resp = await client.patch(f"/projects/{pid}", json={}, headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["name"] == "No Change"


async def test_update_project_not_found(client):
    token, _ = await _create_user(client)
    resp = await client.patch(
        "/projects/00000000-0000-0000-0000-000000000000",
        json={"name": "X"},
        headers=auth_header(token),
    )
    assert resp.status_code == 404


# ── Delete ────────────────────────────────────────────────

async def test_delete_project_owner(client):
    token, _ = await _create_user(client)
    project = await _create_project(client, token, "To Delete")
    pid = project["id"]

    resp = await client.delete(f"/projects/{pid}", headers=auth_header(token))
    assert resp.status_code == 204

    verify = await client.get(f"/projects/{pid}", headers=auth_header(token))
    assert verify.status_code == 404


async def test_delete_project_cascades_tasks(client):
    token, _ = await _create_user(client)
    h = auth_header(token)
    project = await _create_project(client, token, "Cascade")
    pid = project["id"]

    task_resp = await client.post(
        f"/projects/{pid}/tasks", json={"title": "Will die"}, headers=h,
    )
    task_id = task_resp.json()["id"]

    await client.delete(f"/projects/{pid}", headers=h)

    verify = await client.get(f"/tasks/{task_id}", headers=h)
    assert verify.status_code in (404, 405)


async def test_delete_project_non_owner_forbidden(client):
    token_a, _ = await _create_user(client)
    token_b, _ = await _create_user(client)
    project = await _create_project(client, token_a, "Protected")
    pid = project["id"]

    resp = await client.delete(f"/projects/{pid}", headers=auth_header(token_b))
    assert resp.status_code == 403


async def test_delete_project_not_found(client):
    token, _ = await _create_user(client)
    resp = await client.delete(
        "/projects/00000000-0000-0000-0000-000000000000",
        headers=auth_header(token),
    )
    assert resp.status_code == 404
