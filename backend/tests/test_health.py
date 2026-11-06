"""
backend.tests.test_health
-------------------------
Tests for health check endpoint.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app


@pytest.mark.anyio
async def test_health_endpoint():
    """GET /api/health must return 200 and {'status': 'ok'} without authentication."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

