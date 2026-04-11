"""
Data access for the tasks table.

Supports filtered listing by status and assignee, partial updates,
and ownership-aware deletion.
"""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models import tasks


async def list_by_project(
    conn: AsyncConnection,
    project_id: UUID,
    *,
    status: str | None = None,
    assignee_id: UUID | None = None,
) -> list[sa.Row]:
    """List tasks for a project, optionally filtered by status and/or assignee."""
    query = sa.select(tasks).where(tasks.c.project_id == project_id)
    if status:
        query = query.where(tasks.c.status == status)
    if assignee_id:
        query = query.where(tasks.c.assignee_id == assignee_id)
    query = query.order_by(tasks.c.created_at.desc())
    result = await conn.execute(query)
    return list(result.fetchall())


async def get_by_id(conn: AsyncConnection, task_id: UUID) -> sa.Row | None:
    result = await conn.execute(sa.select(tasks).where(tasks.c.id == task_id))
    return result.first()


async def create(
    conn: AsyncConnection,
    *,
    title: str,
    description: str | None,
    priority: str,
    project_id: UUID,
    assignee_id: UUID | None,
    created_by: UUID,
    due_date=None,
) -> sa.Row:
    result = await conn.execute(
        sa.insert(tasks)
        .values(
            title=title,
            description=description,
            priority=priority,
            project_id=project_id,
            assignee_id=assignee_id,
            created_by=created_by,
            due_date=due_date,
        )
        .returning(tasks)
    )
    return result.first()


async def update(conn: AsyncConnection, task_id: UUID, **fields) -> sa.Row | None:
    """Partial update — only provided fields are written."""
    update_data = {k: v for k, v in fields.items() if v is not None}
    if not update_data:
        return await get_by_id(conn, task_id)
    result = await conn.execute(
        sa.update(tasks)
        .where(tasks.c.id == task_id)
        .values(**update_data)
        .returning(tasks)
    )
    return result.first()


async def delete(conn: AsyncConnection, task_id: UUID) -> None:
    await conn.execute(sa.delete(tasks).where(tasks.c.id == task_id))
