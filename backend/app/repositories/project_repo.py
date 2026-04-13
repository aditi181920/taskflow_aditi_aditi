"""
Data access for the projects table.

Key query: list_for_user returns projects where the user is owner
OR has at least one task assigned — implemented with a UNION.
"""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models import projects, tasks


async def list_for_user(
    conn: AsyncConnection, user_id: UUID, *, page: int = 1, limit: int = 20
) -> tuple[list[sa.Row], int]:
    """Projects the user owns or has tasks in. Returns (rows, total_count)."""
    owned = sa.select(projects.c.id).where(projects.c.owner_id == user_id)
    assigned = sa.select(tasks.c.project_id.label("id")).where(tasks.c.assignee_id == user_id).distinct()
    combined = sa.union(owned, assigned).subquery()
    base = sa.select(projects).where(projects.c.id.in_(sa.select(combined.c.id)))

    count_result = await conn.execute(sa.select(sa.func.count()).select_from(base.subquery()))
    total = count_result.scalar() or 0

    offset = (page - 1) * limit
    query = base.order_by(projects.c.created_at.desc()).offset(offset).limit(limit)
    result = await conn.execute(query)
    return list(result.fetchall()), total


async def user_has_access(conn: AsyncConnection, project_id: UUID, user_id: UUID) -> bool:
    """Check if user owns the project or has tasks assigned in it."""
    is_owner = await conn.execute(
        sa.select(sa.literal(1)).where(
            sa.and_(projects.c.id == project_id, projects.c.owner_id == user_id)
        )
    )
    if is_owner.first():
        return True
    has_tasks = await conn.execute(
        sa.select(sa.literal(1)).where(
            sa.and_(tasks.c.project_id == project_id, tasks.c.assignee_id == user_id)
        ).limit(1)
    )
    return has_tasks.first() is not None


async def get_stats(conn: AsyncConnection, project_id: UUID) -> dict:
    """Task counts by status and by assignee for a project."""
    # Count by status
    status_q = await conn.execute(
        sa.select(tasks.c.status, sa.func.count().label("count"))
        .where(tasks.c.project_id == project_id)
        .group_by(tasks.c.status)
    )
    by_status = {row.status: row.count for row in status_q.fetchall()}

    # Count by assignee (null assignee grouped as "unassigned")
    assignee_q = await conn.execute(
        sa.select(tasks.c.assignee_id, sa.func.count().label("count"))
        .where(tasks.c.project_id == project_id)
        .group_by(tasks.c.assignee_id)
    )
    by_assignee = {}
    for row in assignee_q.fetchall():
        key = str(row.assignee_id) if row.assignee_id else "unassigned"
        by_assignee[key] = row.count

    total = sum(by_status.values())
    return {"total": total, "by_status": by_status, "by_assignee": by_assignee}


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
    """Partial update — writes all provided fields, including explicit nulls."""
    if not fields:
        return await get_by_id(conn, project_id)
    result = await conn.execute(
        sa.update(projects)
        .where(projects.c.id == project_id)
        .values(**fields)
        .returning(projects)
    )
    return result.first()


async def delete(conn: AsyncConnection, project_id: UUID) -> None:
    """Delete project — tasks cascade via FK ON DELETE CASCADE."""
    await conn.execute(sa.delete(projects).where(projects.c.id == project_id))
