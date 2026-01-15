"""Structured JSON logging configuration using structlog."""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor


def add_app_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add application context fields to every log entry."""
    event_dict["app"] = "phase2-todo-backend"
    event_dict["env"] = "development"  # Could be loaded from environment variable
    return event_dict


def setup_logging() -> None:
    """Configure structured JSON logging with contextual fields."""

    # Define processors for structlog
    processors: list[Processor] = [
        # Add log level
        structlog.stdlib.add_log_level,
        # Add logger name
        structlog.stdlib.add_logger_name,
        # Add timestamp in ISO format
        structlog.processors.TimeStamper(fmt="iso"),
        # Add application context
        add_app_context,
        # Stack traces for exceptions
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        # Format as JSON for production
        structlog.processors.JSONRenderer(),
    ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a configured logger instance with the given name.

    Usage:
        logger = get_logger(__name__)
        logger.info("user_registered", user_id=user_id, email=email)
        logger.warn("auth_failed", email=email, reason="invalid_password")
    """
    return structlog.get_logger(name)


# Context managers for request-scoped logging
def bind_context(**kwargs: Any) -> None:
    """Bind contextual data to all subsequent log entries in current context."""
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """Remove contextual data from logging context."""
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """Clear all contextual data from logging context."""
    structlog.contextvars.clear_contextvars()
