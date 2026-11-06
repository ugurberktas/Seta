"""
backend.tests.test_reviews
--------------------------
Tests for review decision endpoints with mocked database adapter.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.config import settings
from backend.app.core.rate_limit import rate_limiter
from backend.app.core.security import create_session_token
from backend.app.main import app
from db_review_store import DatabaseStorageError


@pytest.fixture(autouse=True)
def setup_review_env(monkeypatch):
    """Configure test environment for reviews."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://mock_user:mock_pass@mock_host:5432/mock_db")
    monkeypatch.setenv("SESSION_SECRET", "test-secret-12345")
    rate_limiter._review_mutations.clear()


@pytest.fixture
def auth_headers():
    """Provide authentication headers for review operations."""
    token = create_session_token("reviewer_1")
    return {"Cookie": f"{settings.COOKIE_NAME}={token}"}


@pytest.mark.anyio
async def test_get_document_reviews(auth_headers):
    """GET /api/reviews/{document_id} returns reviews snapshot from PostgreSQL."""
    mock_reviews = {
        "version": 1,
        "document_id": "japan_doj_2026",
        "backend": "postgres",
        "reviews": {
            "Russia::seg_1": {"status": "relevant", "category": "Russia", "segment_id": "seg_1"},
        },
    }

    with patch(
        "backend.app.services.review_service.db_review_store.load_reviews",
        return_value=mock_reviews,
    ) as mock_load:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/reviews/japan_doj_2026", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["document_id"] == "japan_doj_2026"
            assert data["total_reviews"] == 1
            assert "Russia::seg_1" in data["reviews"]
            mock_load.assert_called_once()


@pytest.mark.anyio
async def test_set_passage_review_valid(auth_headers):
    """PUT /api/reviews/... persists 'relevant' status."""
    with patch(
        "backend.app.services.review_service.db_review_store.set_passage_review_status"
    ) as mock_set:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                "/api/reviews/japan_doj_2026/Russia/japan_doj_2026_p080_s001",
                json={"status": "relevant"},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "relevant"
            assert data["document_id"] == "japan_doj_2026"
            assert data["category"] == "Russia"
            assert data["segment_id"] == "japan_doj_2026_p080_s001"
            mock_set.assert_called_once()


@pytest.mark.anyio
async def test_set_passage_review_invalid_status(auth_headers):
    """PUT /api/reviews/... with invalid status returns 422 or 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(
            "/api/reviews/japan_doj_2026/Russia/japan_doj_2026_p080_s001",
            json={"status": "maybe_relevant"},
            headers=auth_headers,
        )
        assert resp.status_code == 422  # Pydantic schema validation rejection


@pytest.mark.anyio
async def test_clear_passage_review(auth_headers):
    """DELETE /api/reviews/... deletes review decision."""
    with patch(
        "backend.app.services.review_service.db_review_store.clear_passage_review"
    ) as mock_clear:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete(
                "/api/reviews/japan_doj_2026/Russia/japan_doj_2026_p080_s001",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "unreviewed"
            mock_clear.assert_called_once()


@pytest.mark.anyio
async def test_database_connection_failure_returns_503(auth_headers):
    """Database failure returns 503 without leaking credentials or database URL."""
    with patch(
        "backend.app.services.review_service.db_review_store.load_reviews",
        side_effect=DatabaseStorageError("Connection to neon server timed out"),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/reviews/japan_doj_2026", headers=auth_headers)
            assert resp.status_code == 503
            err_msg = resp.json()["detail"]
            assert "unavailable" in err_msg.lower()
            assert "mock_pass" not in err_msg
            assert "postgresql://" not in err_msg


@pytest.mark.anyio
async def test_review_mutation_rate_limiting(auth_headers):
    """30 review mutations are permitted within 60s; the 31st returns 429."""
    with patch(
        "backend.app.services.review_service.db_review_store.set_passage_review_status"
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for i in range(30):
                resp = await client.put(
                    f"/api/reviews/japan_doj_2026/Russia/seg_{i}",
                    json={"status": "relevant"},
                    headers=auth_headers,
                )
                assert resp.status_code == 200

            # 31st mutation triggers rate limit
            blocked = await client.put(
                "/api/reviews/japan_doj_2026/Russia/seg_31",
                json={"status": "relevant"},
                headers=auth_headers,
            )
            assert blocked.status_code == 429
            assert "Rate limit exceeded" in blocked.json()["detail"]


@pytest.mark.anyio
async def test_review_unknown_document_returns_404(auth_headers):
    """Review operations for unknown document IDs must return 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET reviews
        get_resp = await client.get("/api/reviews/invalid_doc_id", headers=auth_headers)
        assert get_resp.status_code == 404
        assert "not found" in get_resp.json()["detail"].lower()

        # PUT review
        put_resp = await client.put(
            "/api/reviews/invalid_doc_id/Russia/seg_1",
            json={"status": "relevant"},
            headers=auth_headers,
        )
        assert put_resp.status_code == 404
        assert "not found" in put_resp.json()["detail"].lower()

        # DELETE review
        del_resp = await client.delete(
            "/api/reviews/invalid_doc_id/Russia/seg_1",
            headers=auth_headers,
        )
        assert del_resp.status_code == 404
        assert "not found" in del_resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_review_unknown_category_returns_404(auth_headers):
    """Review operations for unknown categories must return 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        put_resp = await client.put(
            "/api/reviews/japan_doj_2026/NonExistentCategory/seg_1",
            json={"status": "relevant"},
            headers=auth_headers,
        )
        assert put_resp.status_code == 404
        assert "not found" in put_resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_review_empty_segment_id_returns_400(auth_headers):
    """PUT /api/reviews/... with empty segment_id returns 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        put_resp = await client.put(
            "/api/reviews/japan_doj_2026/Russia/%20",
            json={"status": "relevant"},
            headers=auth_headers,
        )
        assert put_resp.status_code == 400
        assert "cannot be empty" in put_resp.json()["detail"].lower()

