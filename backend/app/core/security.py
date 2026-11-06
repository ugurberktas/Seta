"""
backend.app.core.security
-------------------------
Authentication, constant-time credential verification, and signed session tokens.
"""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from backend.app.core.config import settings


def verify_login_credentials(input_user: str, input_pass: str) -> bool:
    """Validate credentials using constant-time comparison against environment settings.

    Fails closed if server credentials are not configured.
    """
    expected_user = settings.APP_USERNAME
    expected_pass = settings.APP_PASSWORD

    if not expected_user or not expected_pass:
        return False

    if not input_user or not input_pass:
        return False

    user_ok = hmac.compare_digest(
        input_user.strip().encode("utf-8"),
        expected_user.strip().encode("utf-8"),
    )
    pass_ok = hmac.compare_digest(
        input_pass.encode("utf-8"),
        expected_pass.encode("utf-8"),
    )
    return user_ok and pass_ok


def create_session_token(username: str) -> str:
    """Generate a signed, timed session token using SESSION_SECRET."""
    secret = settings.SESSION_SECRET
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server authentication configuration error: SESSION_SECRET is not configured.",
        )
    serializer = URLSafeTimedSerializer(secret, salt="sra-session-token")
    return serializer.dumps({"sub": username})


def verify_session_token(token: str) -> str | None:
    """Verify signed session token and return authenticated username, or None."""
    secret = settings.SESSION_SECRET
    if not secret or not token:
        return None
    serializer = URLSafeTimedSerializer(secret, salt="sra-session-token")
    try:
        data = serializer.loads(token, max_age=settings.COOKIE_MAX_AGE)
        return data.get("sub")
    except (BadSignature, SignatureExpired, Exception):
        return None


def get_current_user(request: Request) -> str:
    """FastAPI dependency: require an authenticated user from HttpOnly session cookie or Bearer token."""
    token = request.cookies.get(settings.COOKIE_NAME)
    if not token:
        # Also check Authorization: Bearer <token>
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    username = verify_session_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token.",
        )

    return username


CurrentUser = Annotated[str, Depends(get_current_user)]

