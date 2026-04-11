"""
Authentication endpoints: register and login.

Returns generic error messages on failed login to prevent
account enumeration (security best practice).
"""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncConnection

from app.database import get_db
from app.schemas.auth import RegisterRequest, LoginRequest, AuthResponse, UserResponse
from app.security import hash_password, verify_password, create_access_token
from app.repositories import user_repo
from app.exceptions import ConflictError, UnauthorizedError

log = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(body: RegisterRequest, conn: AsyncConnection = Depends(get_db)):
    existing = await user_repo.get_by_email(conn, body.email)
    if existing:
        raise ConflictError("email already registered")

    hashed = hash_password(body.password)
    user = await user_repo.create(conn, name=body.name, email=body.email, password_hash=hashed)
    token = create_access_token(user.id, user.email)

    log.info("user_registered", user_id=str(user.id))
    return AuthResponse(
        token=token,
        user=UserResponse(id=user.id, name=user.name, email=user.email, created_at=user.created_at),
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, conn: AsyncConnection = Depends(get_db)):
    # Generic message prevents account enumeration
    user = await user_repo.get_by_email(conn, body.email)
    if not user or not verify_password(body.password, user.password_hash):
        raise UnauthorizedError()

    token = create_access_token(user.id, user.email)

    log.info("user_logged_in", user_id=str(user.id))
    return AuthResponse(
        token=token,
        user=UserResponse(id=user.id, name=user.name, email=user.email, created_at=user.created_at),
    )
