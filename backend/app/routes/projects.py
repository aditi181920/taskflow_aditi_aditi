"""
Project CRUD endpoints.

Authorization model:
  - List/Get: user must own the project or have tasks assigned in it.
  - Create: any authenticated user (owner = current user).
  - Update/Delete: project owner only (→ 403 otherwise).
"""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncConnection

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse, ProjectDetailResponse
from app.schemas.task import TaskResponse
from app.repositories import project_repo, task_repo
from app.exceptions import NotFoundError, ForbiddenError

log = structlog.get_logger()
router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    user=Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    rows = await project_repo.list_for_user(conn, user.id)
    return ProjectListResponse(projects=[ProjectResponse(**row._mapping) for row in rows])


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    user=Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    row = await project_repo.create(conn, name=body.name, description=body.description, owner_id=user.id)
    log.info("project_created", project_id=str(row.id), user_id=str(user.id))
    return ProjectResponse(**row._mapping)


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: str,
    user=Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    project = await project_repo.get_by_id(conn, project_id)
    if not project:
        raise NotFoundError()

    task_rows = await task_repo.list_by_project(conn, project_id)
    return ProjectDetailResponse(
        **project._mapping,
        tasks=[TaskResponse(**t._mapping) for t in task_rows],
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    user=Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    project = await project_repo.get_by_id(conn, project_id)
    if not project:
        raise NotFoundError()
    if project.owner_id != user.id:
        raise ForbiddenError()

    updated = await project_repo.update(conn, project_id, name=body.name, description=body.description)
    log.info("project_updated", project_id=str(project_id), user_id=str(user.id))
    return ProjectResponse(**updated._mapping)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    user=Depends(get_current_user),
    conn: AsyncConnection = Depends(get_db),
):
    project = await project_repo.get_by_id(conn, project_id)
    if not project:
        raise NotFoundError()
    if project.owner_id != user.id:
        raise ForbiddenError()

    await project_repo.delete(conn, project_id)
    log.info("project_deleted", project_id=str(project_id), user_id=str(user.id))
