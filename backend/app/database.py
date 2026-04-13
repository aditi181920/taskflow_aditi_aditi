"""
Async database engine and session management.

Creates a single connection pool at startup. Route handlers obtain
connections via the `get_db` dependency (see dependencies.py).
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
)


async def get_db() -> AsyncGenerator[AsyncConnection, None]:
    """Yield an async connection, then return it to the pool."""
    async with engine.connect() as conn:
        try:
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise


async def dispose_engine() -> None:
    """Drain the connection pool — called during graceful shutdown."""
    await engine.dispose()
