"""
src/auth.py
-----------
Authentication gate, constant-time credential verification,
session-level login rate limiting (lockout), and review action throttling.
"""

from __future__ import annotations

import hmac
import os
import time
from typing import Any

# ---------------------------------------------------------------------------
# Rate Limiting & Lockout Constants
# ---------------------------------------------------------------------------

LOGIN_MAX_FAILURES = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60  # 15 minutes = 900 seconds

REVIEW_MAX_ACTIONS_PER_WINDOW = 30
REVIEW_WINDOW_SECONDS = 60  # 60 seconds


# ---------------------------------------------------------------------------
# Credentials Access (Fail Closed)
# ---------------------------------------------------------------------------

def get_auth_credentials() -> tuple[str | None, str | None]:
    """Retrieve APP_USERNAME and APP_PASSWORD from Streamlit secrets or environment.

    Returns (username, password) or (None, None) if either is missing/empty.
    """
    # 1. Try Streamlit secrets
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            user = st.secrets.get("APP_USERNAME")
            pw = st.secrets.get("APP_PASSWORD")
            if user and pw and str(user).strip() and str(pw):
                return str(user).strip(), str(pw)
    except Exception:
        pass

    # 2. Try os.environ
    env_user = os.environ.get("APP_USERNAME")
    env_pw = os.environ.get("APP_PASSWORD")
    if env_user and env_pw and env_user.strip() and env_pw:
        return env_user.strip(), env_pw

    return None, None


def are_credentials_configured() -> bool:
    """Return True if both APP_USERNAME and APP_PASSWORD are validly configured."""
    user, pw = get_auth_credentials()
    return bool(user and pw)


# ---------------------------------------------------------------------------
# Constant-Time Verification
# ---------------------------------------------------------------------------

def verify_credentials(
    input_username: str | None,
    input_password: str | None,
    expected_username: str | None = None,
    expected_password: str | None = None,
) -> bool:
    """Verify credentials using constant-time comparison (hmac.compare_digest).

    Fails closed if credentials are not configured or input is missing.
    """
    if expected_username is None or expected_password is None:
        expected_username, expected_password = get_auth_credentials()

    if not expected_username or not expected_password:
        return False

    if not input_username or not input_password:
        return False

    # Constant-time comparison
    user_match = hmac.compare_digest(
        input_username.strip().encode("utf-8"),
        expected_username.strip().encode("utf-8"),
    )
    pw_match = hmac.compare_digest(
        input_password.encode("utf-8"),
        expected_password.encode("utf-8"),
    )
    return user_match and pw_match


# ---------------------------------------------------------------------------
# Login Rate Limiting (Session-Level)
# ---------------------------------------------------------------------------

def check_login_lockout(
    session_state: dict | Any,
    now: float | None = None,
) -> tuple[bool, int]:
    """Check if session is currently locked out from login attempts.

    Returns:
        (is_locked, remaining_seconds)
    """
    current_time = time.time() if now is None else now
    lockout_until = session_state.get("_login_lockout_until", 0)

    if lockout_until > current_time:
        remaining = int(lockout_until - current_time)
        return True, max(1, remaining)

    # Lockout expired
    if "_login_lockout_until" in session_state:
        session_state.pop("_login_lockout_until", None)
        session_state["_login_failures"] = []

    return False, 0


def record_login_failure(
    session_state: dict | Any,
    now: float | None = None,
) -> tuple[bool, int]:
    """Record a failed login attempt. Locks out if threshold reached.

    Returns:
        (is_now_locked, remaining_seconds)
    """
    current_time = time.time() if now is None else now

    # Check if already locked
    is_locked, remaining = check_login_lockout(session_state, current_time)
    if is_locked:
        return True, remaining

    failures: list[float] = session_state.get("_login_failures", [])
    # Prune failures outside the sliding window
    failures = [t for t in failures if current_time - t <= LOGIN_LOCKOUT_SECONDS]
    failures.append(current_time)
    session_state["_login_failures"] = failures

    if len(failures) >= LOGIN_MAX_FAILURES:
        lockout_until = current_time + LOGIN_LOCKOUT_SECONDS
        session_state["_login_lockout_until"] = lockout_until
        return True, LOGIN_LOCKOUT_SECONDS

    return False, 0


def record_login_success(
    session_state: dict | Any,
    username: str = "",
) -> None:
    """Reset failed attempts and set authenticated = True."""
    session_state["authenticated"] = True
    session_state["auth_user"] = username
    session_state["_login_failures"] = []
    session_state.pop("_login_lockout_until", None)


def logout(session_state: dict | Any) -> None:
    """Clear authentication and login-related session state."""
    session_state["authenticated"] = False
    session_state.pop("auth_user", None)
    session_state.pop("_login_failures", None)
    session_state.pop("_login_lockout_until", None)
    session_state.pop("login_username", None)
    session_state.pop("login_password", None)


def is_authenticated(session_state: dict | Any) -> bool:
    """Check if the current session is authenticated."""
    return bool(session_state.get("authenticated", False))


def format_remaining_time(seconds: int, language: str = "en") -> str:
    """Format remaining lockout seconds into human-readable duration."""
    minutes = seconds // 60
    rem_seconds = seconds % 60
    if language == "tr":
        if minutes > 0:
            return f"{minutes} dakika {rem_seconds} saniye"
        return f"{rem_seconds} saniye"
    else:
        if minutes > 0:
            return f"{minutes}m {rem_seconds}s"
        return f"{rem_seconds}s"


# ---------------------------------------------------------------------------
# Review Action Throttling (30 mutations per 60 seconds)
# ---------------------------------------------------------------------------

def check_review_throttle(
    session_state: dict | Any,
    now: float | None = None,
) -> tuple[bool, int]:
    """Check whether a review mutation action is permitted under the rate limit.

    Limit: 30 review mutations per 60 seconds per authenticated session.

    Returns:
        (allowed, retry_after_seconds)
    """
    current_time = time.time() if now is None else now
    timestamps: list[float] = session_state.get("_review_action_timestamps", [])

    # Prune timestamps older than 60 seconds
    valid_timestamps = [t for t in timestamps if current_time - t <= REVIEW_WINDOW_SECONDS]
    session_state["_review_action_timestamps"] = valid_timestamps

    if len(valid_timestamps) >= REVIEW_MAX_ACTIONS_PER_WINDOW:
        oldest = valid_timestamps[0]
        retry_after = max(1, int(oldest + REVIEW_WINDOW_SECONDS - current_time))
        return False, retry_after

    return True, 0


def record_review_action(
    session_state: dict | Any,
    now: float | None = None,
) -> tuple[bool, int]:
    """Record a review action mutation if permitted.

    Returns:
        (allowed, retry_after_seconds)
    """
    current_time = time.time() if now is None else now
    allowed, retry_after = check_review_throttle(session_state, current_time)

    if not allowed:
        return False, retry_after

    timestamps: list[float] = session_state.get("_review_action_timestamps", [])
    timestamps.append(current_time)
    session_state["_review_action_timestamps"] = timestamps
    return True, 0

