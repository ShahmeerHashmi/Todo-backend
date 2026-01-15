"""JWT authentication utilities for token creation, verification, and user extraction."""

from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from fastapi import Cookie, HTTPException, status
from uuid import UUID

from src.config.settings import settings
from src.config.logging import get_logger

logger = get_logger(__name__)


def create_token(user_id: UUID, email: str) -> str:
    """
    Create a JWT token for authenticated user.

    Args:
        user_id: User's unique identifier
        email: User's email address

    Returns:
        Signed JWT token string

    Usage:
        token = create_token(user.id, user.email)
    """
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRATION_HOURS)

    payload = {
        "user_id": str(user_id),
        "email": email,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }

    token = jwt.encode(payload, settings.BETTER_AUTH_SECRET, algorithm=settings.JWT_ALGORITHM)

    logger.info("jwt_created", user_id=str(user_id), expires_at=expires_at.isoformat())

    return token


def verify_token(token: str) -> dict:
    """
    Verify JWT token signature and extract payload.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload containing user_id and email

    Raises:
        HTTPException: 401 if token is invalid, expired, or malformed
    """
    try:
        payload = jwt.decode(
            token,
            settings.BETTER_AUTH_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )

        logger.debug("jwt_verified", user_id=payload.get("user_id"))

        return payload

    except jwt.ExpiredSignatureError:
        logger.warn("jwt_expired", token_preview=token[:20])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )

    except jwt.InvalidTokenError as e:
        logger.warn("jwt_invalid", error=str(e), token_preview=token[:20])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )


def get_current_user(token: Optional[str] = Cookie(None, alias=settings.COOKIE_NAME)) -> dict:
    """
    FastAPI dependency to extract and verify JWT token from httpOnly cookie.

    Args:
        token: JWT token from httpOnly cookie (automatically extracted by FastAPI)

    Returns:
        Decoded token payload with user_id and email

    Raises:
        HTTPException: 401 if token is missing or invalid

    Usage:
        @app.get("/protected")
        async def protected_route(user: dict = Depends(get_current_user)):
            user_id = user["user_id"]
            ...
    """
    if not token:
        logger.warn("auth_missing_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    payload = verify_token(token)

    return payload


def get_user_id(user: dict) -> UUID:
    """
    Extract user_id from verified token payload.

    Args:
        user: Decoded token payload from get_current_user

    Returns:
        User's UUID

    Usage:
        @app.get("/tasks")
        async def get_tasks(user: dict = Depends(get_current_user)):
            user_id = get_user_id(user)
            # Query tasks filtered by user_id
    """
    return UUID(user["user_id"])
