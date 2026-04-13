"""
FastAPI dependency injection providers.

get_current_user: Extracts the JWT from the Authorization header,
validates it, loads the user from the DB, and returns the row.
Any failure raises UnauthorizedError (-> 401).

Uses FastAPI's HTTPBearer scheme so Swagger UI shows an "Authorize"
button where you can paste your JWT token.
"""

from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncConnection

from app.database import get_db
from app.security import decode_access_token
from app.exceptions import UnauthorizedError
from app.repositories import user_repo

# This adds the lock icon and "Authorize" button to Swagger UI
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    conn: AsyncConnection = Depends(get_db),
):
    """Extract and validate JWT, return the authenticated user row."""
    if credentials is None:
        raise UnauthorizedError()

    claims = decode_access_token(credentials.credentials)
    if claims is None:
        raise UnauthorizedError()

    user = await user_repo.get_by_id(conn, UUID(claims["sub"]))
    if user is None:
        raise UnauthorizedError()

    return user
