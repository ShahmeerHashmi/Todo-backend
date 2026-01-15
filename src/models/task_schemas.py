"""Task request and response schemas per tasks-api.yaml."""

from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


class TaskCreateRequest(BaseModel):
    """Request schema for creating a new task."""
    title: str = Field(..., min_length=1, max_length=100, description="Task title")
    description: Optional[str] = Field(None, max_length=500, description="Optional task description")


class TaskUpdateRequest(BaseModel):
    """Request schema for updating an existing task."""
    title: Optional[str] = Field(None, min_length=1, max_length=100, description="Task title")
    description: Optional[str] = Field(None, max_length=500, description="Task description")
    updated_at: Optional[datetime] = Field(None, description="Client's last known updated_at timestamp for optimistic concurrency")


class TaskCompleteRequest(BaseModel):
    """Request schema for toggling task completion."""
    updated_at: Optional[datetime] = Field(None, description="Client's last known updated_at timestamp for optimistic concurrency")


class TaskResponse(BaseModel):
    """Response schema for task data."""
    id: UUID
    user_id: UUID
    title: str
    description: Optional[str]
    completed: bool
    created_at: datetime
    updated_at: datetime
