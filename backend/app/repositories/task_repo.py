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
    page: int = 1,
    limit: int = 20,
) -> tuple[list[sa.Row], int]:
    """List tasks for a project with optional filters. Returns (rows, total_count)."""
    base = sa.select(tasks).where(tasks.c.project_id == project_id)
    if status:
        base = base.where(tasks.c.status == status)
    if assignee_id:
        base = base.where(tasks.c.assignee_id == assignee_id)

    count_result = await conn.execute(sa.select(sa.func.count()).select_from(base.subquery()))
    total = count_result.scalar() or 0

    offset = (page - 1) * limit
    query = base.order_by(tasks.c.created_at.desc()).offset(offset).limit(limit)
    result = await conn.execute(query)
    return list(result.fetchall()), total


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
    """Partial update — writes all provided fields, including explicit nulls."""
    if not fields:
        return await get_by_id(conn, task_id)
    result = await conn.execute(
        sa.update(tasks)
        .where(tasks.c.id == task_id)
        .values(**fields)
        .returning(tasks)
    )
    return result.first()


async def delete(conn: AsyncConnection, task_id: UUID) -> None:
    await conn.execute(sa.delete(tasks).where(tasks.c.id == task_id))
