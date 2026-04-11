"""
Data access for the projects table.

Key query: list_for_user returns projects where the user is owner
OR has at least one task assigned — implemented with a UNION.
"""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models import projects, tasks


async def list_for_user(conn: AsyncConnection, user_id: UUID) -> list[sa.Row]:
    """Projects the user owns or has tasks in."""
    owned = sa.select(projects.c.id).where(projects.c.owner_id == user_id)
    assigned = sa.select(tasks.c.project_id.label("id")).where(tasks.c.assignee_id == user_id).distinct()
    combined = sa.union(owned, assigned).subquery()
    query = sa.select(projects).where(projects.c.id.in_(sa.select(combined.c.id)))
    result = await conn.execute(query)
    return list(result.fetchall())


async def get_by_id(conn: AsyncConnection, project_id: UUID) -> sa.Row | None:
    result = await conn.execute(sa.select(projects).where(projects.c.id == project_id))
    return result.first()


async def create(conn: AsyncConnection, *, name: str, description: str | None, owner_id: UUID) -> sa.Row:
    result = await conn.execute(
        sa.insert(projects)
        .values(name=name, description=description, owner_id=owner_id)
        .returning(projects)
    )
    return result.first()


async def update(conn: AsyncConnection, project_id: UUID, **fields) -> sa.Row | None:
    """Partial update — only non-None fields are written."""
    update_data = {k: v for k, v in fields.items() if v is not None}
    if not update_data:
        return await get_by_id(conn, project_id)
    result = await conn.execute(
        sa.update(projects)
        .where(projects.c.id == project_id)
        .values(**update_data)
        .returning(projects)
    )
    return result.first()


async def delete(conn: AsyncConnection, project_id: UUID) -> None:
    """Delete project — tasks cascade via FK ON DELETE CASCADE."""
    await conn.execute(sa.delete(projects).where(projects.c.id == project_id))
