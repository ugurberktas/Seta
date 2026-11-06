"""
backend.tests.test_auth
-----------------------
Tests for authentication endpoints and session management.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.config import settings
from backend.app.core.rate_limit import rate_limiter
from backend.app.core.security import create_session_token
from backend.app.main import app


@pytest.fixture(autouse=True)
def configure_auth_env(monkeypatch):
    """Set standard test credentials and reset rate limits."""
    monkeypatch.setenv("APP_USERNAME", "test_researcher")
    monkeypatch.setenv("APP_PASSWORD", "SecretPassword456!")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-key-12345")
    rate_limiter._login_failures.clear()
    rate_limiter._review_mutations.clear()


@pytest.mark.anyio
async def test_unauthenticated_protected_route_returns_401():
    """Accessing protected endpoint without session must return 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401
        assert "Authentication required" in resp.json()["detail"]


@pytest.mark.anyio
async def test_valid_login_sets_cookie_and_returns_user():
    """Valid login credentials must issue an HttpOnly cookie and return user payload."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/login",
            json={"username": "test_researcher", "password": "SecretPassword456!"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "test_researcher"
        assert data["authenticated"] is True
        assert "password" not in str(data)

        # Check HttpOnly cookie
        cookie_header = resp.headers.get("set-cookie")
        assert cookie_header is not None
        assert settings.COOKIE_NAME in cookie_header
        assert "HttpOnly" in cookie_header


@pytest.mark.anyio
async def test_invalid_login_returns_401():
    """Invalid credentials must return 401 with generic error."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/login",
            json={"username": "test_researcher", "password": "wrong_password"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid username or password."


@pytest.mark.anyio
async def test_auth_me_returns_current_user():
    """Authenticated request to /api/auth/me must return current user identity."""
    token = create_session_token("test_researcher")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Pass session cookie
        client.cookies.set(settings.COOKIE_NAME, token)
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 200
        assert resp.json() == {"username": "test_researcher", "authenticated": True}


@pytest.mark.anyio
async def test_logout_clears_cookie():
    """POST /api/auth/logout must clear session cookie."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/auth/logout")
        assert resp.status_code == 200
        cookie_header = resp.headers.get("set-cookie")
        assert cookie_header is not None
        # Deleted cookie has max-age=0 or expires in past
        assert 'max-age=0' in cookie_header.lower() or 'expires=' in cookie_header.lower()


@pytest.mark.anyio
async def test_login_rate_limiting_triggers_429():
    """5 consecutive failed logins must trigger HTTP 429 rate limit."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for i in range(5):
            resp = await client.post(
                "/api/auth/login",
                json={"username": "test_researcher", "password": f"wrong_{i}"},
            )
            assert resp.status_code == 401

        # 6th attempt: blocked by rate limiter
        blocked_resp = await client.post(
            "/api/auth/login",
            json={"username": "test_researcher", "password": "wrong_6"},
        )
        assert blocked_resp.status_code == 429
        assert "Too many failed login attempts" in blocked_resp.json()["detail"]

