"""
backend.app.api.auth
--------------------
Authentication endpoints: login, logout, current user inspection.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from backend.app.core.config import settings
from backend.app.core.rate_limit import rate_limiter
from backend.app.core.security import (
    CurrentUser,
    create_session_token,
    verify_login_credentials,
)
from backend.app.schemas.auth import LoginRequest, MessageResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=UserResponse, summary="Sign in")
def login(request: Request, response: Response, payload: LoginRequest) -> UserResponse:
    """Authenticate with username and password, setting an HttpOnly session cookie."""
    client_ip = request.client.host if request.client else "unknown"

    # 1. Enforce rate limit (5 failed attempts per 15 minutes)
    rate_limiter.check_login_rate(client_ip)

    # 2. Check if server credentials are configured (fail closed)
    if not settings.APP_USERNAME or not settings.APP_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: Authentication credentials are not configured.",
        )

    # 3. Constant-time verification
    if not verify_login_credentials(payload.username, payload.password):
        rate_limiter.record_login_failure(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    # 4. Success: reset failed attempts & issue session token
    rate_limiter.reset_login_failures(client_ip)
    clean_username = payload.username.strip()
    session_token = create_session_token(clean_username)

    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=session_token,
        max_age=settings.COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )

    return UserResponse(username=clean_username, authenticated=True)


@router.post("/logout", response_model=MessageResponse, summary="Sign out")
def logout(response: Response) -> MessageResponse:
    """Clear the session cookie to log out."""
    response.delete_cookie(
        key=settings.COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )
    return MessageResponse(message="Logged out successfully.")


@router.get("/me", response_model=UserResponse, summary="Current user")
def get_me(user: CurrentUser) -> UserResponse:
    """Return currently authenticated user information."""
    return UserResponse(username=user, authenticated=True)

