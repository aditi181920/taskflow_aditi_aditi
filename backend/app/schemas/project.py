"""Request/response schemas for project endpoints."""

from uuid import UUID
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("must not be blank")
            return stripped
        return v


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    owner_id: UUID
    created_at: datetime


class ProjectListResponse(BaseModel):
    """Wraps list of projects per spec: {"projects": [...]}"""
    projects: list[ProjectResponse]
    page: int = 1
    limit: int = 20
    total: int = 0


class ProjectDetailResponse(ProjectResponse):
    """Project with its tasks — used by GET /projects/:id."""
    tasks: list = Field(default_factory=list)
