"""
Task endpoints.

Tasks live under a project (/projects/:id/tasks) for creation and listing.
Update and delete use /tasks/:id directly.

Delete authorization: project owner OR task creator (spec requirement).
"""

import structlog
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncConnection

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse, TaskListResponse
from app.repositories import task_repo, project_repo
from app.exceptions import NotFoundError, ForbiddenError

log = structlog.get_logger()
router = APIRouter(tags=["tasks"])


@router.get("/projects/{project_id}/tasks", response_model=TaskListResponse)
async def list_tasks(
    project_id: str,
    status: Optional[str] = Query(None, description="Filter by status: todo, in_progress, done"),
    assignee: Optional[str] = Query(None, description="Filter by assignee UUID"),
    user=Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    project = await project_repo.get_by_id(conn, project_id)
    if not project:
        raise NotFoundError()

    assignee_uuid = UUID(assignee) if assignee else None
    rows = await task_repo.list_by_project(conn, project_id, status=status, assignee_id=assignee_uuid)
    return TaskListResponse(tasks=[TaskResponse(**r._mapping) for r in rows])


@router.post("/projects/{project_id}/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    project_id: str,
    body: TaskCreate,
    user=Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    project = await project_repo.get_by_id(conn, project_id)
    if not project:
        raise NotFoundError()

    row = await task_repo.create(
        conn,
        title=body.title,
        description=body.description,
        priority=body.priority.value,
        project_id=project_id,
        assignee_id=body.assignee_id,
        created_by=user.id,
        due_date=body.due_date,
    )
    log.info("task_created", task_id=str(row.id), project_id=project_id)
    return TaskResponse(**row._mapping)


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    body: TaskUpdate,
    user=Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    task = await task_repo.get_by_id(conn, task_id)
    if not task:
        raise NotFoundError()

    # Build update kwargs, converting enums to their string values
    update_fields = {}
    if body.title is not None:
        update_fields["title"] = body.title
    if body.description is not None:
        update_fields["description"] = body.description
    if body.status is not None:
        update_fields["status"] = body.status.value
    if body.priority is not None:
        update_fields["priority"] = body.priority.value
    if body.assignee_id is not None:
        update_fields["assignee_id"] = body.assignee_id
    if body.due_date is not None:
        update_fields["due_date"] = body.due_date

    updated = await task_repo.update(conn, task_id, **update_fields)
    log.info("task_updated", task_id=str(task_id))
    return TaskResponse(**updated._mapping)


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    user=Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    task = await task_repo.get_by_id(conn, task_id)
    if not task:
        raise NotFoundError()

    # Authorization: project owner OR task creator
    project = await project_repo.get_by_id(conn, task.project_id)
    is_owner = project and project.owner_id == user.id
    is_creator = task.created_by == user.id

    if not (is_owner or is_creator):
        raise ForbiddenError()

    await task_repo.delete(conn, task_id)
    log.info("task_deleted", task_id=str(task_id), user_id=str(user.id))
