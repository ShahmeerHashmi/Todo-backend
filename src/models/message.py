"""Message SQLModel entity for database persistence."""

from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.conversation import Conversation


class Message(SQLModel, table=True):
    """Single message within a conversation.

    Represents a message from either the user or the AI assistant.
    Messages are ordered chronologically within their conversation.
    """

    __tablename__ = "messages"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    conversation_id: UUID = Field(
        foreign_key="conversations.id",
        nullable=False,
        index=True
    )
    role: str = Field(
        max_length=20,
        nullable=False,
        description="Message sender: 'user' or 'assistant'"
    )
    content: str = Field(
        max_length=10000,  # FR-012: Maximum message length
        nullable=False,
        description="Message text content"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    # Relationships
    conversation: Optional["Conversation"] = Relationship(back_populates="messages")
