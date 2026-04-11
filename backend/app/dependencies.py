"""
FastAPI dependency injection providers.

get_current_user: Extracts the JWT from the Authorization header,
validates it, loads the user from the DB, and returns the row.
Any failure raises UnauthorizedError (→ 401).
"""

from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncConnection

from app.database import get_db
from app.security import decode_access_token
from app.exceptions import UnauthorizedError
from app.repositories import user_repo


async def get_current_user(
    request: Request,
    conn: AsyncConnection = Depends(get_db),
):
    """Extract and validate JWT, return the authenticated user row."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise UnauthorizedError()

    token = auth_header.split(" ", 1)[1]
    claims = decode_access_token(token)
    if claims is None:
        raise UnauthorizedError()

    user = await user_repo.get_by_id(conn, UUID(claims["sub"]))
    if user is None:
        raise UnauthorizedError()

    return user
