"""Request/response schemas for task endpoints."""

from uuid import UUID
from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"


class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.medium
    assignee_id: Optional[UUID] = None
    due_date: Optional[date] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    assignee_id: Optional[UUID] = None
    due_date: Optional[date] = None


class TaskResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    status: str
    priority: str
    project_id: UUID
    assignee_id: Optional[UUID]
    created_by: UUID
    due_date: Optional[date]
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    """Wraps list of tasks per spec: {"tasks": [...]}"""
    tasks: list[TaskResponse]
