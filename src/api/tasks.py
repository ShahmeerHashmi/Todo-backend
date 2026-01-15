"""Task management API endpoints (CRUD operations with user-scoped isolation)."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from src.models.task_schemas import (
    TaskCreateRequest,
    TaskUpdateRequest,
    TaskCompleteRequest,
    TaskResponse,
)
from src.services.task_service import TaskService
from src.database.connection import get_session
from src.middleware.auth import get_current_user
from src.config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/", response_model=list[TaskResponse])
async def get_all_tasks(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[TaskResponse]:
    """
    Get all tasks for authenticated user (sorted by created_at DESC).

    Args:
        current_user: Authenticated user from JWT token
        session: Database session (injected)

    Returns:
        List of TaskResponse objects (empty list if no tasks)

    Raises:
        401: Authentication required or invalid token
    """
    user_id = UUID(current_user["user_id"])

    logger.info("get_all_tasks_request", user_id=str(user_id))

    tasks = await TaskService.get_all_tasks(session, user_id)

    # Convert Task entities to TaskResponse models
    return [
        TaskResponse(
            id=task.id,
            user_id=task.user_id,
            title=task.title,
            description=task.description,
            completed=task.completed,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
        for task in tasks
    ]


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=TaskResponse)
async def create_task(
    request: TaskCreateRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    """
    Create a new task for authenticated user.

    Args:
        request: Task creation request with title and optional description
        current_user: Authenticated user from JWT token
        session: Database session (injected)

    Returns:
        TaskResponse with created task data

    Raises:
        400: Validation error (title empty, title > 100 chars, description > 500 chars)
        401: Authentication required or invalid token
    """
    user_id = UUID(current_user["user_id"])

    logger.info("create_task_request", user_id=str(user_id), title=request.title)

    task = await TaskService.create_task(session, user_id, request)

    return TaskResponse(
        id=task.id,
        user_id=task.user_id,
        title=task.title,
        description=task.description,
        completed=task.completed,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_by_id(
    task_id: UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    """
    Get a specific task by ID (user-scoped).

    Args:
        task_id: UUID of the task
        current_user: Authenticated user from JWT token
        session: Database session (injected)

    Returns:
        TaskResponse with task data

    Raises:
        401: Authentication required or invalid token
        403: Task belongs to another user
        404: Task not found
    """
    user_id = UUID(current_user["user_id"])

    logger.info("get_task_request", user_id=str(user_id), task_id=str(task_id))

    task = await TaskService.get_task_by_id(session, user_id, task_id)

    return TaskResponse(
        id=task.id,
        user_id=task.user_id,
        title=task.title,
        description=task.description,
        completed=task.completed,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    request: TaskUpdateRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    """
    Update a task with optimistic concurrency control.

    Args:
        task_id: UUID of the task
        request: Task update request with optional title, description, updated_at
        current_user: Authenticated user from JWT token
        session: Database session (injected)

    Returns:
        TaskResponse with updated task data

    Raises:
        400: Validation error (title empty, title > 100 chars, description > 500 chars)
        401: Authentication required or invalid token
        403: Task belongs to another user
        404: Task not found
        409: Optimistic concurrency conflict (task modified by another client)
    """
    user_id = UUID(current_user["user_id"])

    logger.info("update_task_request", user_id=str(user_id), task_id=str(task_id))

    task = await TaskService.update_task(session, user_id, task_id, request)

    return TaskResponse(
        id=task.id,
        user_id=task.user_id,
        title=task.title,
        description=task.description,
        completed=task.completed,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """
    Delete a task.

    Args:
        task_id: UUID of the task
        current_user: Authenticated user from JWT token
        session: Database session (injected)

    Returns:
        No content (204)

    Raises:
        401: Authentication required or invalid token
        403: Task belongs to another user
        404: Task not found
    """
    user_id = UUID(current_user["user_id"])

    logger.info("delete_task_request", user_id=str(user_id), task_id=str(task_id))

    await TaskService.delete_task(session, user_id, task_id)


@router.patch("/{task_id}/complete", response_model=TaskResponse)
async def toggle_task_completion(
    task_id: UUID,
    request: TaskCompleteRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    """
    Toggle task completion status with optimistic concurrency control.

    Args:
        task_id: UUID of the task
        request: Task complete request with optional updated_at
        current_user: Authenticated user from JWT token
        session: Database session (injected)

    Returns:
        TaskResponse with updated task data (completion toggled)

    Raises:
        401: Authentication required or invalid token
        403: Task belongs to another user
        404: Task not found
        409: Optimistic concurrency conflict (task modified by another client)
    """
    user_id = UUID(current_user["user_id"])

    logger.info("toggle_completion_request", user_id=str(user_id), task_id=str(task_id))

    task = await TaskService.toggle_completion(
        session,
        user_id,
        task_id,
        request.updated_at
    )

    return TaskResponse(
        id=task.id,
        user_id=task.user_id,
        title=task.title,
        description=task.description,
        completed=task.completed,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
