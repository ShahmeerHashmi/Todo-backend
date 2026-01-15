"""Conversation SQLModel entity for database persistence."""

from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.message import Message


class Conversation(SQLModel, table=True):
    """Single ongoing chat session for a user.

    Per spec clarification, each user has exactly one conversation.
    New messages append to this thread. The conversation is
    automatically created on first chat interaction.
    """

    __tablename__ = "conversations"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
        unique=True,  # One conversation per user
        index=True
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    # Relationships
    messages: List["Message"] = Relationship(back_populates="conversation")
