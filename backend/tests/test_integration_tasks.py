"""Integration tests for task endpoints."""

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


async def _setup(client):
    """Register user + create project. Returns (token, project_id, user_id)."""
    uid = _uid()
    data = await register_user(client, f"T {uid}", f"t{uid}@example.com", "pass123")
    token, user_id = data["token"], data["user"]["id"]
    proj = await client.post("/projects", json={"name": f"P {uid}"}, headers=auth_header(token))
    return token, proj.json()["id"], user_id


# ── Create ────────────────────────────────────────────────

async def test_create_task_defaults(client):
    token, pid, uid = await _setup(client)
    resp = await client.post(
        f"/projects/{pid}/tasks",
        json={"title": "Simple"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Simple"
    assert data["status"] == "todo"
    assert data["priority"] == "medium"
    assert data["assignee_id"] is None
    assert data["due_date"] is None
    assert data["created_by"] == uid
    assert data["project_id"] == pid


async def test_create_task_all_fields(client):
    token, pid, uid = await _setup(client)
    resp = await client.post(
        f"/projects/{pid}/tasks",
        json={"title": "Full", "description": "Desc", "priority": "high",
              "assignee_id": uid, "due_date": "2026-06-01"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["priority"] == "high"
    assert data["assignee_id"] == uid
    assert data["due_date"] == "2026-06-01"
    assert data["description"] == "Desc"


async def test_create_task_empty_title(client):
    token, pid, _ = await _setup(client)
    resp = await client.post(
        f"/projects/{pid}/tasks",
        json={"title": ""},
        headers=auth_header(token),
    )
    assert resp.status_code == 400


async def test_create_task_whitespace_title(client):
    token, pid, _ = await _setup(client)
    resp = await client.post(
        f"/projects/{pid}/tasks",
        json={"title": "   "},
        headers=auth_header(token),
    )
    assert resp.status_code == 400


async def test_create_task_title_stripped(client):
    token, pid, _ = await _setup(client)
    resp = await client.post(
        f"/projects/{pid}/tasks",
        json={"title": "  Padded Title  "},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Padded Title"


async def test_create_task_invalid_priority(client):
    token, pid, _ = await _setup(client)
    resp = await client.post(
        f"/projects/{pid}/tasks",
        json={"title": "X", "priority": "critical"},
        headers=auth_header(token),
    )
    assert resp.status_code == 400


async def test_create_task_nonexistent_project(client):
    token, _, _ = await _setup(client)
    resp = await client.post(
        "/projects/00000000-0000-0000-0000-000000000000/tasks",
        json={"title": "Orphan"},
        headers=auth_header(token),
    )
    assert resp.status_code == 404


async def test_create_task_nonexistent_assignee(client):
    token, pid, _ = await _setup(client)
    resp = await client.post(
        f"/projects/{pid}/tasks",
        json={"title": "Bad assign", "assignee_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth_header(token),
    )
    assert resp.status_code == 400
    assert "assignee_id" in resp.json().get("fields", {})


# ── List + Filter ─────────────────────────────────────────

async def test_list_tasks(client):
    token, pid, _ = await _setup(client)
    h = auth_header(token)
    await client.post(f"/projects/{pid}/tasks", json={"title": "A"}, headers=h)
    await client.post(f"/projects/{pid}/tasks", json={"title": "B"}, headers=h)

    resp = await client.get(f"/projects/{pid}/tasks", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert "tasks" in data
    assert len(data["tasks"]) == 2
    assert data["total"] == 2


async def test_list_tasks_filter_status(client):
    token, pid, _ = await _setup(client)
    h = auth_header(token)
    await client.post(f"/projects/{pid}/tasks", json={"title": "A"}, headers=h)
    r2 = await client.post(f"/projects/{pid}/tasks", json={"title": "B"}, headers=h)
    await client.patch(f"/tasks/{r2.json()['id']}", json={"status": "done"}, headers=h)

    resp = await client.get(f"/projects/{pid}/tasks?status=todo", headers=h)
    assert len(resp.json()["tasks"]) == 1
    assert all(t["status"] == "todo" for t in resp.json()["tasks"])

    resp2 = await client.get(f"/projects/{pid}/tasks?status=done", headers=h)
    assert len(resp2.json()["tasks"]) == 1


async def test_list_tasks_filter_assignee(client):
    token, pid, uid = await _setup(client)
    h = auth_header(token)
    await client.post(f"/projects/{pid}/tasks", json={"title": "Assigned", "assignee_id": uid}, headers=h)
    await client.post(f"/projects/{pid}/tasks", json={"title": "Unassigned"}, headers=h)

    resp = await client.get(f"/projects/{pid}/tasks?assignee={uid}", headers=h)
    assert len(resp.json()["tasks"]) == 1
    assert resp.json()["tasks"][0]["assignee_id"] == uid


async def test_list_tasks_filter_both(client):
    token, pid, uid = await _setup(client)
    h = auth_header(token)
    r1 = await client.post(f"/projects/{pid}/tasks", json={"title": "A", "assignee_id": uid}, headers=h)
    await client.post(f"/projects/{pid}/tasks", json={"title": "B", "assignee_id": uid}, headers=h)
    await client.patch(f"/tasks/{r1.json()['id']}", json={"status": "done"}, headers=h)

    resp = await client.get(f"/projects/{pid}/tasks?status=done&assignee={uid}", headers=h)
    assert len(resp.json()["tasks"]) == 1


async def test_list_tasks_invalid_status(client):
    token, pid, _ = await _setup(client)
    resp = await client.get(
        f"/projects/{pid}/tasks?status=garbage",
        headers=auth_header(token),
    )
    assert resp.status_code == 400
    assert "status" in resp.json().get("fields", {})


async def test_list_tasks_pagination(client):
    token, pid, _ = await _setup(client)
    h = auth_header(token)
    for i in range(5):
        await client.post(f"/projects/{pid}/tasks", json={"title": f"T{i}"}, headers=h)

    resp = await client.get(f"/projects/{pid}/tasks?page=1&limit=2", headers=h)
    data = resp.json()
    assert len(data["tasks"]) == 2
    assert data["total"] == 5

    resp2 = await client.get(f"/projects/{pid}/tasks?page=3&limit=2", headers=h)
    assert len(resp2.json()["tasks"]) == 1


async def test_list_tasks_nonexistent_project(client):
    token, _, _ = await _setup(client)
    resp = await client.get(
        "/projects/00000000-0000-0000-0000-000000000000/tasks",
        headers=auth_header(token),
    )
    assert resp.status_code == 404


# ── Update ────────────────────────────────────────────────

async def test_update_task_status(client):
    token, pid, _ = await _setup(client)
    h = auth_header(token)
    task = await client.post(f"/projects/{pid}/tasks", json={"title": "X"}, headers=h)
    tid = task.json()["id"]
    created_at = task.json()["updated_at"]

    resp = await client.patch(f"/tasks/{tid}", json={"status": "in_progress"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"
    assert resp.json()["updated_at"] != created_at


async def test_update_task_multiple_fields(client):
    token, pid, uid = await _setup(client)
    h = auth_header(token)
    task = await client.post(f"/projects/{pid}/tasks", json={"title": "X"}, headers=h)
    tid = task.json()["id"]

    resp = await client.patch(
        f"/tasks/{tid}",
        json={"title": "New Title", "status": "done", "priority": "high",
              "assignee_id": uid, "due_date": "2026-12-31"},
        headers=h,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "New Title"
    assert data["status"] == "done"
    assert data["priority"] == "high"
    assert data["assignee_id"] == uid
    assert data["due_date"] == "2026-12-31"


async def test_update_task_set_assignee_null(client):
    token, pid, uid = await _setup(client)
    h = auth_header(token)
    task = await client.post(
        f"/projects/{pid}/tasks",
        json={"title": "Assigned", "assignee_id": uid},
        headers=h,
    )
    tid = task.json()["id"]
    assert task.json()["assignee_id"] == uid

    resp = await client.patch(f"/tasks/{tid}", json={"assignee_id": None}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["assignee_id"] is None


async def test_update_task_empty_body(client):
    token, pid, _ = await _setup(client)
    h = auth_header(token)
    task = await client.post(f"/projects/{pid}/tasks", json={"title": "X"}, headers=h)
    tid = task.json()["id"]

    resp = await client.patch(f"/tasks/{tid}", json={}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["title"] == "X"


async def test_update_task_invalid_status(client):
    token, pid, _ = await _setup(client)
    h = auth_header(token)
    task = await client.post(f"/projects/{pid}/tasks", json={"title": "X"}, headers=h)
    tid = task.json()["id"]

    resp = await client.patch(f"/tasks/{tid}", json={"status": "cancelled"}, headers=h)
    assert resp.status_code == 400


async def test_update_task_nonexistent_assignee(client):
    token, pid, _ = await _setup(client)
    h = auth_header(token)
    task = await client.post(f"/projects/{pid}/tasks", json={"title": "X"}, headers=h)
    tid = task.json()["id"]

    resp = await client.patch(
        f"/tasks/{tid}",
        json={"assignee_id": "00000000-0000-0000-0000-000000000000"},
        headers=h,
    )
    assert resp.status_code == 400


async def test_update_task_not_found(client):
    token, _, _ = await _setup(client)
    resp = await client.patch(
        "/tasks/00000000-0000-0000-0000-000000000000",
        json={"title": "X"},
        headers=auth_header(token),
    )
    assert resp.status_code == 404


# ── Delete ────────────────────────────────────────────────

async def test_delete_task_by_creator(client):
    token, pid, _ = await _setup(client)
    h = auth_header(token)
    task = await client.post(f"/projects/{pid}/tasks", json={"title": "X"}, headers=h)
    tid = task.json()["id"]

    resp = await client.delete(f"/tasks/{tid}", headers=h)
    assert resp.status_code == 204


async def test_delete_task_by_project_owner(client):
    """Project owner can delete any task, even if created by another user."""
    owner_token, pid, _ = await _setup(client)

    uid2 = _uid()
    other = await register_user(client, f"O {uid2}", f"o{uid2}@example.com", "pass123")
    other_token = other["token"]

    task = await client.post(
        f"/projects/{pid}/tasks", json={"title": "Owner's task"}, headers=auth_header(owner_token),
    )
    tid = task.json()["id"]

    resp_other = await client.delete(f"/tasks/{tid}", headers=auth_header(other_token))
    assert resp_other.status_code == 403

    resp_owner = await client.delete(f"/tasks/{tid}", headers=auth_header(owner_token))
    assert resp_owner.status_code == 204


async def test_delete_task_forbidden(client):
    token_a, pid, _ = await _setup(client)
    h_a = auth_header(token_a)
    task = await client.post(f"/projects/{pid}/tasks", json={"title": "X"}, headers=h_a)
    tid = task.json()["id"]

    uid = _uid()
    other = await register_user(client, f"F {uid}", f"f{uid}@example.com", "pass123")
    resp = await client.delete(f"/tasks/{tid}", headers=auth_header(other["token"]))
    assert resp.status_code == 403
    assert resp.json()["error"] == "forbidden"


async def test_delete_task_not_found(client):
    token, _, _ = await _setup(client)
    resp = await client.delete(
        "/tasks/00000000-0000-0000-0000-000000000000",
        headers=auth_header(token),
    )
    assert resp.status_code == 404


# ── Stats ─────────────────────────────────────────────────

async def test_project_stats(client):
    token, pid, uid = await _setup(client)
    h = auth_header(token)

    await client.post(f"/projects/{pid}/tasks", json={"title": "A", "assignee_id": uid}, headers=h)
    r2 = await client.post(f"/projects/{pid}/tasks", json={"title": "B"}, headers=h)
    await client.patch(f"/tasks/{r2.json()['id']}", json={"status": "done"}, headers=h)

    resp = await client.get(f"/projects/{pid}/stats", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["by_status"]["todo"] == 1
    assert data["by_status"]["done"] == 1
    assert data["by_assignee"][uid] == 1
    assert data["by_assignee"]["unassigned"] == 1


async def test_project_stats_empty(client):
    token, pid, _ = await _setup(client)
    resp = await client.get(f"/projects/{pid}/stats", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_project_stats_not_found(client):
    token, _, _ = await _setup(client)
    resp = await client.get(
        "/projects/00000000-0000-0000-0000-000000000000/stats",
        headers=auth_header(token),
    )
    assert resp.status_code == 404
