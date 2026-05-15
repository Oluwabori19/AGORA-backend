"""Schemas for user authentication and JWT token handling."""

from typing_extensions import Annotated
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional
from pydantic.types import conint


class UserCreate(BaseModel):
    """Schema for user registration requests."""
    email: EmailStr
    password: str


class UserOut(BaseModel):
    """Schema for user profile responses (password excluded)."""
    id: int
    email: EmailStr
    created_at: datetime

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """Schema for user login authentication requests."""
    email: EmailStr
    password: str


class Token(BaseModel):
    """Schema for JWT token pair responses."""
    access_token: str  # Short-lived access token for API requests
    refresh_token: str  # Long-lived token for refreshing access tokens
    token_type: str


class TokenData(BaseModel):
    """Schema for decoded token payload."""
    id: Optional[str] = None
