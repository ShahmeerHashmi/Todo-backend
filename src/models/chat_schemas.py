"""Chat request/response schemas for the conversational AI interface."""

from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


class ChatRequest(BaseModel):
    """Request schema for sending a chat message."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Natural language message from user"
    )


class ToolCall(BaseModel):
    """Schema for tool invocation details."""

    tool: str = Field(..., description="Name of the MCP tool invoked")
    params: dict = Field(default_factory=dict, description="Parameters passed to the tool")
    result: str = Field(..., description="Outcome of tool execution (success/error)")


class ChatResponse(BaseModel):
    """Response schema for chat message processing."""

    response: str = Field(..., description="AI assistant's natural language response")
    conversation_id: UUID = Field(..., description="UUID of the conversation")
    message_id: UUID = Field(..., description="UUID of the assistant's response message")
    tool_calls: list[ToolCall] = Field(
        default_factory=list,
        description="List of tool invocations made during processing"
    )


class MessageResponse(BaseModel):
    """Schema for a single message in history."""

    id: UUID = Field(..., description="Unique message identifier")
    role: str = Field(..., description="Message sender (user/assistant)")
    content: str = Field(..., description="Message content")
    created_at: datetime = Field(..., description="When the message was created")


class MessageHistoryResponse(BaseModel):
    """Response schema for message history retrieval."""

    conversation_id: UUID = Field(..., description="UUID of the conversation")
    messages: list[MessageResponse] = Field(
        default_factory=list,
        description="List of messages in chronological order"
    )
    has_more: bool = Field(
        default=False,
        description="Whether more messages exist before the returned set"
    )


class ChatErrorResponse(BaseModel):
    """Error response schema for chat API."""

    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict] = Field(default=None, description="Additional error details")
