"""Authentication request and response schemas per auth-api.yaml."""

from pydantic import BaseModel, EmailStr, Field
from uuid import UUID


class RegisterRequest(BaseModel):
    """Request schema for user registration."""
    email: EmailStr = Field(..., max_length=254, description="User email address")
    password: str = Field(..., min_length=8, description="User password (minimum 8 characters)")


class LoginRequest(BaseModel):
    """Request schema for user login."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class AuthResponse(BaseModel):
    """Response schema for successful authentication."""
    message: str
    user: "UserResponse"


class UserResponse(BaseModel):
    """User information in auth response."""
    id: UUID
    email: str


class RegisterResponse(BaseModel):
    """Response schema for successful registration."""
    message: str
    user_id: UUID
