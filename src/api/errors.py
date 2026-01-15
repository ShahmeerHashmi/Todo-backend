"""Standardized error responses and exception classes per API contracts."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from fastapi import HTTPException, status


class ErrorDetail(BaseModel):
    """Field-specific error detail."""
    field: str
    message: str


class ErrorResponse(BaseModel):
    """Standardized error response schema matching contracts/auth-api.yaml and contracts/tasks-api.yaml."""
    message: str
    errors: list[ErrorDetail]
    statusCode: int
    timestamp: str


def create_error_response(
    message: str,
    status_code: int,
    errors: Optional[list[ErrorDetail]] = None,
) -> dict:
    """
    Create standardized error response dictionary.

    Args:
        message: High-level error message
        status_code: HTTP status code
        errors: List of field-specific errors (optional)

    Returns:
        Error response dictionary matching ErrorResponse schema
    """
    return {
        "message": message,
        "errors": [e.model_dump() for e in errors] if errors else [],
        "statusCode": status_code,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# Custom Exception Classes
class ValidationError(HTTPException):
    """Validation error with field-specific details."""

    def __init__(self, message: str, errors: list[ErrorDetail]):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(message, 400, errors),
        )


class UnauthorizedError(HTTPException):
    """Authentication required or invalid token."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=create_error_response(message, 401),
        )


class ForbiddenError(HTTPException):
    """User attempting to access another user's resource."""

    def __init__(self, message: str = "Access denied: resource belongs to another user"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(message, 403),
        )


class NotFoundError(HTTPException):
    """Resource not found or not accessible."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(message, 404),
        )


class ConflictError(HTTPException):
    """Resource conflict (duplicate, optimistic concurrency, etc.)."""

    def __init__(self, message: str, errors: Optional[list[ErrorDetail]] = None):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=create_error_response(message, 409, errors),
        )


class RateLimitError(HTTPException):
    """Too many requests (rate limit exceeded)."""

    def __init__(self, message: str = "You're sending messages too quickly. Please wait a moment."):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=create_error_response(message, 429),
        )


class ServiceUnavailableError(HTTPException):
    """External service unavailable (AI service, etc.)."""

    def __init__(self, message: str = "I'm having trouble connecting. Please try again in a moment."):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_error_response(message, 503),
        )


# Helper functions for common error scenarios
def raise_duplicate_email_error(email: str) -> None:
    """Raise error for duplicate email registration."""
    raise ConflictError(
        message="Email already registered",
        errors=[ErrorDetail(field="email", message=f"Email '{email}' is already in use")],
    )


def raise_invalid_credentials_error() -> None:
    """Raise error for invalid login credentials."""
    raise UnauthorizedError(message="Invalid email or password")


def raise_task_not_found_error() -> None:
    """Raise error when task is not found."""
    raise NotFoundError(message="Task not found")


def raise_forbidden_access_error() -> None:
    """Raise error when user attempts to access another user's resource."""
    raise ForbiddenError()


def raise_optimistic_concurrency_error(expected: str, actual: str) -> None:
    """Raise error for optimistic concurrency conflict."""
    raise ConflictError(
        message="Task was modified by another client. Please refresh and try again.",
        errors=[
            ErrorDetail(
                field="updated_at",
                message=f"Version mismatch: expected {expected}, got {actual}",
            )
        ],
    )


def raise_validation_error(field: str, message: str) -> None:
    """Raise validation error for a single field."""
    raise ValidationError(
        message="Validation failed",
        errors=[ErrorDetail(field=field, message=message)],
    )


def raise_ai_service_error() -> None:
    """Raise error when AI service is unavailable."""
    raise ServiceUnavailableError()
