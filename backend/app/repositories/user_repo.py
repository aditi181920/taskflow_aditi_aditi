"""
Data access for the users table.

All queries use SQLAlchemy Core expressions — no ORM session, no magic.
"""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models import users


async def get_by_id(conn: AsyncConnection, user_id: UUID) -> sa.Row | None:
    result = await conn.execute(sa.select(users).where(users.c.id == user_id))
    return result.first()


async def get_by_email(conn: AsyncConnection, email: str) -> sa.Row | None:
    result = await conn.execute(sa.select(users).where(users.c.email == email))
    return result.first()


async def create(conn: AsyncConnection, *, name: str, email: str, password_hash: str) -> sa.Row:
    result = await conn.execute(
        sa.insert(users)
        .values(name=name, email=email, password_hash=password_hash)
        .returning(users)
    )
    return result.first()
