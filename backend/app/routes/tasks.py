"""
Task endpoints.

Tasks live under a project (/projects/:id/tasks) for creation and listing.
Update and delete use /tasks/:id directly.

Delete authorization: project owner OR task creator (spec requirement).
"""

from uuid import UUID
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncConnection

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse, TaskListResponse, TaskStatus
from app.repositories import task_repo, project_repo, user_repo
from app.exceptions import NotFoundError, ForbiddenError, BadRequestError

log = structlog.get_logger()
router = APIRouter(tags=["tasks"])

VALID_STATUSES = {s.value for s in TaskStatus}


@router.get("/projects/{project_id}/tasks", response_model=TaskListResponse)
async def list_tasks(
    project_id: UUID,
    status: Optional[str] = Query(None, description="Filter by status: todo, in_progress, done"),
    assignee: Optional[UUID] = Query(None, description="Filter by assignee UUID"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    user=Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    project = await project_repo.get_by_id(conn, project_id)
    if not project:
        raise NotFoundError()

    if status and status not in VALID_STATUSES:
        raise BadRequestError("validation failed", {"status": f"must be one of: {', '.join(sorted(VALID_STATUSES))}"})

    rows, total = await task_repo.list_by_project(
        conn, project_id, status=status, assignee_id=assignee, page=page, limit=limit
    )
    return TaskListResponse(tasks=[TaskResponse(**r._mapping) for r in rows], page=page, limit=limit, total=total)


@router.post("/projects/{project_id}/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    project_id: UUID,
    body: TaskCreate,
    user=Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    project = await project_repo.get_by_id(conn, project_id)
    if not project:
        raise NotFoundError()

    if body.assignee_id:
        assignee = await user_repo.get_by_id(conn, body.assignee_id)
        if not assignee:
            raise BadRequestError("validation failed", {"assignee_id": "user not found"})

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
    log.info("task_created", task_id=str(row.id), project_id=str(project_id))
    return TaskResponse(**row._mapping)


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    body: TaskUpdate,
    user=Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    task = await task_repo.get_by_id(conn, task_id)
    if not task:
        raise NotFoundError()

    # Validate assignee exists if being changed to a non-null value
    if "assignee_id" in body.model_fields_set and body.assignee_id is not None:
        assignee = await user_repo.get_by_id(conn, body.assignee_id)
        if not assignee:
            raise BadRequestError("validation failed", {"assignee_id": "user not found"})

    update_fields = {}
    for field_name in body.model_fields_set:
        value = getattr(body, field_name)
        if field_name in ("status", "priority") and value is not None:
            value = value.value
        update_fields[field_name] = value

    updated = await task_repo.update(conn, task_id, **update_fields)
    log.info("task_updated", task_id=str(task_id))
    return TaskResponse(**updated._mapping)


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: UUID,
    user=Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    task = await task_repo.get_by_id(conn, task_id)
    if not task:
        raise NotFoundError()

    project = await project_repo.get_by_id(conn, task.project_id)
    is_owner = project and project.owner_id == user.id
    is_creator = task.created_by == user.id

    if not (is_owner or is_creator):
        raise ForbiddenError()

    await task_repo.delete(conn, task_id)
    log.info("task_deleted", task_id=str(task_id), user_id=str(user.id))
