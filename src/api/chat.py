"""Chat API endpoints for conversational AI task management.

Per constitution mandate, all conversational state is persisted in the database.
Backend servers remain stateless. AI actions are performed through MCP tools.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from openai import OpenAIError

from src.models.chat_schemas import (
    ChatRequest,
    ChatResponse,
    MessageHistoryResponse,
    MessageResponse,
)
from src.services.chat_service import ChatService
from src.database.connection import get_session
from src.middleware.auth import get_current_user
from src.api.errors import raise_ai_service_error
from src.config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def send_chat_message(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    """
    Send a message to the AI assistant and receive a response.

    The AI assistant can invoke task management tools (create, list, update,
    complete, delete) based on the message content. All messages and responses
    are persisted for conversation continuity.

    Args:
        request: ChatRequest with natural language message
        current_user: Authenticated user from JWT cookie
        session: Database session (injected)

    Returns:
        ChatResponse with AI response, conversation_id, message_id, and tool_calls

    Raises:
        400: Validation error (empty message, message > 10,000 chars)
        401: Authentication required or invalid token
        503: AI service unavailable
    """
    user_id = UUID(current_user["user_id"])

    logger.info(
        "chat_message_request",
        user_id=str(user_id),
        message_length=len(request.message)
    )

    try:
        result = await ChatService.process_chat_message(
            session,
            user_id,
            request.message
        )

        return ChatResponse(
            response=result["response"],
            conversation_id=result["conversation_id"],
            message_id=result["message_id"],
            tool_calls=result.get("tool_calls", [])
        )

    except OpenAIError as e:
        logger.error(
            "openai_service_error",
            user_id=str(user_id),
            error=str(e)
        )
        raise_ai_service_error()


@router.get("/messages", response_model=MessageHistoryResponse)
async def get_message_history(
    limit: int = 50,
    before: Optional[datetime] = None,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MessageHistoryResponse:
    """
    Get conversation message history for the authenticated user.

    Messages are returned in chronological order (oldest first).
    Supports pagination via the 'before' timestamp parameter.

    Args:
        limit: Maximum messages to return (1-100, default 50)
        before: Return messages created before this timestamp (ISO 8601)
        current_user: Authenticated user from JWT cookie
        session: Database session (injected)

    Returns:
        MessageHistoryResponse with conversation_id, messages list, has_more flag

    Raises:
        401: Authentication required or invalid token
    """
    user_id = UUID(current_user["user_id"])

    # Clamp limit to valid range
    limit = max(1, min(100, limit))

    logger.info(
        "message_history_request",
        user_id=str(user_id),
        limit=limit,
        before=str(before) if before else None
    )

    result = await ChatService.get_message_history(
        session,
        user_id,
        limit=limit,
        before=before
    )

    return MessageHistoryResponse(
        conversation_id=result["conversation_id"],
        messages=[
            MessageResponse(
                id=msg["id"],
                role=msg["role"],
                content=msg["content"],
                created_at=msg["created_at"]
            )
            for msg in result["messages"]
        ],
        has_more=result["has_more"]
    )


@router.delete("/messages", status_code=status.HTTP_204_NO_CONTENT)
async def clear_chat_history(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """
    Clear all messages from the user's conversation.

    This permanently removes all message history. The conversation
    itself is preserved, only messages are deleted.

    Args:
        current_user: Authenticated user from JWT cookie
        session: Database session (injected)

    Returns:
        204 No Content on success

    Raises:
        401: Authentication required or invalid token
    """
    user_id = UUID(current_user["user_id"])

    logger.info(
        "clear_chat_history_request",
        user_id=str(user_id)
    )

    await ChatService.clear_conversation(session, user_id)

    logger.info(
        "clear_chat_history_complete",
        user_id=str(user_id)
    )
