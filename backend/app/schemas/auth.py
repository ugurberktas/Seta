"""
backend.app.schemas.auth
------------------------
Request and response schemas for authentication.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., description="Application login username")
    password: str = Field(..., description="Application login password")


class UserResponse(BaseModel):
    username: str
    authenticated: bool = True


class MessageResponse(BaseModel):
    message: str

