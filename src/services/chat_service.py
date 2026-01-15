"""Chat service for conversation management and AI orchestration.

Per constitution mandate, all conversational state MUST be persisted
in the database. Backend servers MUST remain stateless.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation
from src.models.message import Message
from src.agents.todo_agent import TodoAgent
from src.config.logging import get_logger

logger = get_logger(__name__)


class ChatService:
    """Service for chat conversation management and AI message processing.

    This service handles:
    - Conversation creation/retrieval (one per user)
    - Message persistence (both user and assistant)
    - AI agent orchestration
    - Context window management (last 50 messages)
    """

    @staticmethod
    async def get_or_create_conversation(
        session: AsyncSession,
        user_id: UUID
    ) -> Conversation:
        """Get existing conversation or create new one for user.

        Per spec clarification, each user has exactly one conversation.

        Args:
            session: Database session
            user_id: Authenticated user's UUID

        Returns:
            Conversation entity (existing or newly created)
        """
        statement = select(Conversation).where(Conversation.user_id == user_id)
        result = await session.execute(statement)
        conversation = result.scalar_one_or_none()

        if not conversation:
            conversation = Conversation(user_id=user_id)
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)

            logger.info(
                "conversation_created",
                user_id=str(user_id),
                conversation_id=str(conversation.id)
            )

        return conversation

    @staticmethod
    async def get_recent_messages(
        session: AsyncSession,
        conversation_id: UUID,
        limit: int = 50
    ) -> list[Message]:
        """Get recent messages for AI context window.

        Messages are returned in chronological order (oldest first)
        to maintain conversation flow for the AI agent.

        Args:
            session: Database session
            conversation_id: Conversation UUID
            limit: Maximum messages to return (default 50)

        Returns:
            List of Message entities in chronological order
        """
        # Fetch all messages for the conversation and select the most
        # recent `limit` messages in-memory. This avoids relying on
        # database ordering semantics when timestamps are close and
        # ensures stable, chronological output (oldest first).
        statement = select(Message).where(Message.conversation_id == conversation_id)
        result = await session.execute(statement)
        messages = result.scalars().all()

        # Sort chronologically and take the last `limit` items
        messages_sorted = sorted(messages, key=lambda m: m.created_at)
        recent = messages_sorted[-limit:]

        return recent

    @staticmethod
    async def add_message(
        session: AsyncSession,
        conversation_id: UUID,
        role: str,
        content: str
    ) -> Message:
        """Add a message to the conversation.

        Also updates the conversation's updated_at timestamp.

        Args:
            session: Database session
            conversation_id: Conversation UUID
            role: Message sender ('user' or 'assistant')
            content: Message text content

        Returns:
            Created Message entity
        """
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content
        )
        session.add(message)

        # Update conversation timestamp
        statement = (
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=datetime.utcnow())
        )
        await session.execute(statement)

        await session.commit()
        await session.refresh(message)

        logger.info(
            "message_added",
            conversation_id=str(conversation_id),
            role=role,
            message_id=str(message.id)
        )

        return message

    @staticmethod
    async def process_chat_message(
        session: AsyncSession,
        user_id: UUID,
        user_message: str
    ) -> dict:
        """Process a chat message and return AI response.

        This is the main orchestration method that:
        1. Gets or creates the user's conversation
        2. Persists the user message
        3. Loads conversation history for context
        4. Invokes the AI agent
        5. Persists the assistant response
        6. Returns the response with metadata

        Args:
            session: Database session
            user_id: Authenticated user's UUID
            user_message: Natural language message from user

        Returns:
            Dict with response, conversation_id, message_id, tool_calls
        """
        logger.info(
            "process_chat_message_start",
            user_id=str(user_id),
            message_length=len(user_message)
        )

        # Get or create conversation
        conversation = await ChatService.get_or_create_conversation(session, user_id)

        # Persist user message
        await ChatService.add_message(
            session,
            conversation.id,
            role="user",
            content=user_message
        )

        # Load conversation history for AI context
        recent_messages = await ChatService.get_recent_messages(
            session,
            conversation.id,
            limit=50
        )

        # Convert to format expected by agent (excluding current message)
        conversation_history = [
            {"role": msg.role, "content": msg.content}
            for msg in recent_messages[:-1]  # Exclude the message we just added
        ]

        # Invoke AI agent
        agent = TodoAgent(session, user_id)
        agent_response = await agent.process_message(user_message, conversation_history)

        # Persist assistant response
        assistant_message = await ChatService.add_message(
            session,
            conversation.id,
            role="assistant",
            content=agent_response["response"]
        )

        # Log tool invocations per FR-011
        if agent_response.get("tool_calls"):
            for tool_call in agent_response["tool_calls"]:
                logger.info(
                    "tool_invocation",
                    user_id=str(user_id),
                    conversation_id=str(conversation.id),
                    tool=tool_call["tool"],
                    params=tool_call["params"],
                    result=tool_call["result"]
                )

        logger.info(
            "process_chat_message_complete",
            user_id=str(user_id),
            conversation_id=str(conversation.id),
            message_id=str(assistant_message.id),
            tool_calls_count=len(agent_response.get("tool_calls", []))
        )

        return {
            "response": agent_response["response"],
            "conversation_id": conversation.id,
            "message_id": assistant_message.id,
            "tool_calls": agent_response.get("tool_calls", [])
        }

    @staticmethod
    async def clear_conversation(
        session: AsyncSession,
        user_id: UUID
    ) -> bool:
        """Clear all messages from a user's conversation.

        Args:
            session: Database session
            user_id: Authenticated user's UUID

        Returns:
            True if messages were cleared, False if no conversation exists
        """
        conversation = await ChatService.get_or_create_conversation(session, user_id)

        # Delete all messages for this conversation
        from sqlalchemy import delete
        statement = delete(Message).where(Message.conversation_id == conversation.id)
        await session.execute(statement)
        await session.commit()

        logger.info(
            "conversation_cleared",
            user_id=str(user_id),
            conversation_id=str(conversation.id)
        )

        return True

    @staticmethod
    async def get_message_history(
        session: AsyncSession,
        user_id: UUID,
        limit: int = 50,
        before: Optional[datetime] = None
    ) -> dict:
        """Get message history for a user's conversation.

        Supports pagination via 'before' timestamp parameter.

        Args:
            session: Database session
            user_id: Authenticated user's UUID
            limit: Maximum messages to return
            before: Return messages created before this timestamp

        Returns:
            Dict with conversation_id, messages list, has_more flag
        """
        conversation = await ChatService.get_or_create_conversation(session, user_id)

        # Retrieve messages and perform stable, timestamp-based pagination
        query = select(Message).where(Message.conversation_id == conversation.id)

        if before:
            query = query.where(Message.created_at < before)

        result = await session.execute(query)
        messages = result.scalars().all()

        # Sort chronologically (oldest first) and apply pagination
        messages_sorted = sorted(messages, key=lambda m: m.created_at)
        # Determine if there are more messages beyond the requested limit
        has_more = len(messages_sorted) > limit
        paged = messages_sorted[-limit:]

        messages = paged

        return {
            "conversation_id": conversation.id,
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at
                }
                for msg in messages
            ],
            "has_more": has_more
        }
