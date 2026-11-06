"""
backend.app.core.rate_limit
---------------------------
In-memory rate limiting for login attempts and review mutations.
"""

from __future__ import annotations

import time
from collections import defaultdict
from fastapi import HTTPException, status

LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 15 * 60  # 15 minutes = 900 seconds

REVIEW_MAX_MUTATIONS = 30
REVIEW_WINDOW_SECONDS = 60  # 60 seconds


class RateLimiter:
    """In-memory rate limiter for login failures and review mutations."""

    def __init__(self) -> None:
        self._login_failures: dict[str, list[float]] = defaultdict(list)
        self._review_mutations: dict[str, list[float]] = defaultdict(list)

    def check_login_rate(self, client_key: str, now: float | None = None) -> None:
        """Check if client has exceeded the failed login attempt limit."""
        current_time = time.time() if now is None else now
        failures = self._login_failures[client_key]
        failures = [t for t in failures if current_time - t <= LOGIN_WINDOW_SECONDS]
        self._login_failures[client_key] = failures

        if len(failures) >= LOGIN_MAX_FAILURES:
            oldest = failures[0]
            remaining = int(oldest + LOGIN_WINDOW_SECONDS - current_time)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed login attempts. Please try again in {max(1, remaining)} seconds.",
            )

    def record_login_failure(self, client_key: str, now: float | None = None) -> None:
        """Record a failed login attempt for the client."""
        current_time = time.time() if now is None else now
        self._login_failures[client_key].append(current_time)

    def reset_login_failures(self, client_key: str) -> None:
        """Clear failed login attempts upon successful login."""
        self._login_failures.pop(client_key, None)

    def check_review_mutation_rate(self, session_key: str, now: float | None = None) -> None:
        """Enforce maximum of 30 review mutations per 60 seconds per authenticated session."""
        current_time = time.time() if now is None else now
        actions = self._review_mutations[session_key]
        actions = [t for t in actions if current_time - t <= REVIEW_WINDOW_SECONDS]
        self._review_mutations[session_key] = actions

        if len(actions) >= REVIEW_MAX_MUTATIONS:
            oldest = actions[0]
            remaining = int(oldest + REVIEW_WINDOW_SECONDS - current_time)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many review actions. Rate limit exceeded, please wait {max(1, remaining)} seconds.",
            )

        actions.append(current_time)


rate_limiter = RateLimiter()

