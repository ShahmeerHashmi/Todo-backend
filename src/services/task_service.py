"""Task service for CRUD operations with user-scoped isolation and optimistic concurrency."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import datetime
from typing import Optional

from src.models.task import Task
from src.models.task_schemas import TaskCreateRequest, TaskUpdateRequest
from src.services.todo_manager_wrapper import TodoManagerWrapper
from src.api.errors import (
    raise_task_not_found_error,
    raise_forbidden_access_error,
    raise_optimistic_concurrency_error,
)
from src.config.logging import get_logger

logger = get_logger(__name__)


class TaskService:
    """Service for task management operations with user-scoped data isolation."""

    @staticmethod
    async def create_task(
        session: AsyncSession,
        user_id: UUID,
        request: TaskCreateRequest
    ) -> Task:
        """
        Create a new task for the authenticated user.

        Args:
            session: Database session
            user_id: Authenticated user's UUID
            request: Task creation request with title and optional description

        Returns:
            Created Task entity

        Raises:
            ValidationError: If title or description validation fails (400)
        """
        # Delegate validation to Phase 1 TodoManager wrapper per FR-012
        validated_data = TodoManagerWrapper.validate_task_data(
            request.title,
            request.description or ""
        )

        # Create task entity
        task = Task(
            user_id=user_id,
            title=validated_data["title"],
            description=validated_data["description"] if validated_data["description"] else None,
            completed=False,
        )

        session.add(task)
        await session.commit()
        await session.refresh(task)

        logger.info(
            "task_created",
            user_id=str(user_id),
            task_id=str(task.id),
            title=task.title,
        )

        return task

    @staticmethod
    async def get_all_tasks(session: AsyncSession, user_id: UUID) -> list[Task]:
        """
        Get all tasks for the authenticated user, ordered by created_at DESC.

        Args:
            session: Database session
            user_id: Authenticated user's UUID

        Returns:
            List of Task entities (empty list if no tasks)
        """
        statement = (
            select(Task)
            .where(Task.user_id == user_id)
            .order_by(Task.created_at.desc())
        )

        result = await session.execute(statement)
        tasks = result.scalars().all()

        logger.info(
            "tasks_retrieved",
            user_id=str(user_id),
            count=len(tasks),
        )

        return list(tasks)

    @staticmethod
    async def get_task_by_id(
        session: AsyncSession,
        user_id: UUID,
        task_id: UUID
    ) -> Task:
        """
        Get a specific task by ID with user ownership verification.

        Args:
            session: Database session
            user_id: Authenticated user's UUID
            task_id: Task UUID

        Returns:
            Task entity

        Raises:
            NotFoundError: If task not found (404)
            ForbiddenError: If task belongs to another user (403)
        """
        statement = select(Task).where(Task.id == task_id)
        result = await session.execute(statement)
        task = result.scalar_one_or_none()

        if not task:
            logger.warn(
                "task_not_found",
                user_id=str(user_id),
                task_id=str(task_id),
            )
            raise_task_not_found_error()

        # Check ownership
        if task.user_id != user_id:
            logger.warn(
                "task_access_forbidden",
                user_id=str(user_id),
                task_id=str(task_id),
                owner_id=str(task.user_id),
            )
            raise_forbidden_access_error()

        logger.info(
            "task_retrieved",
            user_id=str(user_id),
            task_id=str(task_id),
        )

        return task

    @staticmethod
    async def update_task(
        session: AsyncSession,
        user_id: UUID,
        task_id: UUID,
        request: TaskUpdateRequest
    ) -> Task:
        """
        Update a task with optimistic concurrency control.

        Args:
            session: Database session
            user_id: Authenticated user's UUID
            task_id: Task UUID
            request: Task update request with optional title, description, updated_at

        Returns:
            Updated Task entity

        Raises:
            NotFoundError: If task not found (404)
            ForbiddenError: If task belongs to another user (403)
            ConflictError: If optimistic concurrency check fails (409)
            ValidationError: If title or description validation fails (400)
        """
        # Get task with ownership verification
        task = await TaskService.get_task_by_id(session, user_id, task_id)

        # Optimistic concurrency check
        if request.updated_at:
            # Compare timestamps (allowing small precision differences)
            db_timestamp = task.updated_at.replace(microsecond=0)
            client_timestamp = request.updated_at.replace(microsecond=0)

            if db_timestamp != client_timestamp:
                logger.warn(
                    "optimistic_concurrency_conflict",
                    user_id=str(user_id),
                    task_id=str(task_id),
                    expected=client_timestamp.isoformat(),
                    actual=db_timestamp.isoformat(),
                )
                raise_optimistic_concurrency_error(
                    client_timestamp.isoformat(),
                    db_timestamp.isoformat()
                )

        # Validate updates using Phase 1 wrapper
        if request.title is not None or request.description is not None:
            validated_data = TodoManagerWrapper.validate_task_update(
                request.title,
                request.description
            )

            # Apply validated updates
            if validated_data["title"] is not None:
                task.title = validated_data["title"]
            if validated_data["description"] is not None:
                task.description = validated_data["description"]

        # Update timestamp (database trigger will also update this)
        task.updated_at = datetime.utcnow()

        await session.commit()
        await session.refresh(task)

        logger.info(
            "task_updated",
            user_id=str(user_id),
            task_id=str(task_id),
            title=task.title,
        )

        return task

    @staticmethod
    async def delete_task(
        session: AsyncSession,
        user_id: UUID,
        task_id: UUID
    ) -> None:
        """
        Delete a task with user ownership verification.

        Args:
            session: Database session
            user_id: Authenticated user's UUID
            task_id: Task UUID

        Raises:
            NotFoundError: If task not found (404)
            ForbiddenError: If task belongs to another user (403)
        """
        # Get task with ownership verification
        task = await TaskService.get_task_by_id(session, user_id, task_id)

        await session.delete(task)
        await session.commit()

        logger.info(
            "task_deleted",
            user_id=str(user_id),
            task_id=str(task_id),
        )

    @staticmethod
    async def toggle_completion(
        session: AsyncSession,
        user_id: UUID,
        task_id: UUID,
        updated_at: Optional[datetime] = None
    ) -> Task:
        """
        Toggle task completion status with optimistic concurrency control.

        Args:
            session: Database session
            user_id: Authenticated user's UUID
            task_id: Task UUID
            updated_at: Client's last known updated_at timestamp (optional)

        Returns:
            Updated Task entity with toggled completion status

        Raises:
            NotFoundError: If task not found (404)
            ForbiddenError: If task belongs to another user (403)
            ConflictError: If optimistic concurrency check fails (409)
        """
        # Get task with ownership verification
        task = await TaskService.get_task_by_id(session, user_id, task_id)

        # Optimistic concurrency check
        if updated_at:
            db_timestamp = task.updated_at.replace(microsecond=0)
            client_timestamp = updated_at.replace(microsecond=0)

            if db_timestamp != client_timestamp:
                logger.warn(
                    "optimistic_concurrency_conflict_toggle",
                    user_id=str(user_id),
                    task_id=str(task_id),
                    expected=client_timestamp.isoformat(),
                    actual=db_timestamp.isoformat(),
                )
                raise_optimistic_concurrency_error(
                    client_timestamp.isoformat(),
                    db_timestamp.isoformat()
                )

        # Toggle completion
        task.completed = not task.completed
        task.updated_at = datetime.utcnow()

        await session.commit()
        await session.refresh(task)

        logger.info(
            "task_completion_toggled",
            user_id=str(user_id),
            task_id=str(task_id),
            completed=task.completed,
        )

        return task
