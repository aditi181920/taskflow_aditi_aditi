"""Request/response schemas for project endpoints."""

from uuid import UUID
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    owner_id: UUID
    created_at: datetime


class ProjectListResponse(BaseModel):
    """Wraps list of projects per spec: {"projects": [...]}"""
    projects: list[ProjectResponse]


class ProjectDetailResponse(ProjectResponse):
    """Project with its tasks — used by GET /projects/:id."""
    tasks: list = []
