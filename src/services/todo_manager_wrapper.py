"""Phase 1 TodoManager wrapper for delegating validation to Phase 1 code per FR-012."""

import sys
from pathlib import Path

# Add todobackend to sys.path to import Phase 1 modules
todobackend_path = Path(__file__).parent.parent.parent.parent / "todobackend"
if str(todobackend_path) not in sys.path:
    sys.path.insert(0, str(todobackend_path))

from src.models.task import Task as Phase1Task
from src.api.errors import raise_validation_error
from src.config.logging import get_logger

logger = get_logger(__name__)


class TodoManagerWrapper:
    """
    Wrapper around Phase 1 TodoManager for validation delegation.

    Delegates title and description validation to Phase 1 Task model
    to ensure consistency across Phase 1 (CLI) and Phase 2 (Web) per FR-012.
    """

    @staticmethod
    def validate_task_data(title: str, description: str = "") -> dict[str, str]:
        """
        Validate task title and description using Phase 1 Task validation logic.

        Args:
            title: Task title to validate
            description: Task description to validate (optional)

        Returns:
            Dictionary with validated 'title' and 'description' keys

        Raises:
            ValidationError: If title or description validation fails (400)
                - Title cannot be empty or whitespace-only
                - Title cannot exceed 100 characters
                - Description cannot exceed 500 characters
        """
        try:
            # Create a temporary Phase 1 Task instance to leverage its validation
            # We use task_id=0 as it's not relevant for validation
            phase1_task = Phase1Task(task_id=0, title=title, description=description)

            logger.debug(
                "task_validation_success",
                title_length=len(phase1_task.title),
                description_length=len(phase1_task.description),
            )

            # Return validated and stripped values
            return {
                "title": phase1_task.title,
                "description": phase1_task.description,
            }

        except ValueError as e:
            # Phase 1 Task raises ValueError for validation errors
            error_msg = str(e)

            # Determine which field failed
            if "title" in error_msg.lower():
                field = "title"
            elif "description" in error_msg.lower():
                field = "description"
            else:
                field = "task"

            logger.warn(
                "task_validation_failed",
                field=field,
                error=error_msg,
            )

            # Re-raise as ValidationError with proper field and message
            raise_validation_error(field, error_msg)

    @staticmethod
    def validate_task_update(
        title: str | None = None,
        description: str | None = None
    ) -> dict[str, str | None]:
        """
        Validate task update data (partial updates allowed).

        Args:
            title: New task title (optional)
            description: New task description (optional)

        Returns:
            Dictionary with validated 'title' and 'description' keys

        Raises:
            ValidationError: If provided title or description validation fails
        """
        result = {}

        # If title provided, validate it
        if title is not None:
            validated = TodoManagerWrapper.validate_task_data(title, "")
            result["title"] = validated["title"]
        else:
            result["title"] = None

        # If description provided, validate it separately
        if description is not None:
            # For description-only validation, use a dummy valid title
            validated = TodoManagerWrapper.validate_task_data("Valid Title", description)
            result["description"] = validated["description"]
        else:
            result["description"] = None

        return result
