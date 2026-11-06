"""
backend.tests.test_documents
----------------------------
Tests for document metadata, category metrics, and grouped passage endpoints.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.config import settings
from backend.app.core.security import create_session_token
from backend.app.main import app


@pytest.fixture
def auth_headers(monkeypatch):
    """Provide authentication headers for protected document endpoints."""
    monkeypatch.setenv("SESSION_SECRET", "test-secret-12345")
    token = create_session_token("test_user")
    return {"Cookie": f"{settings.COOKIE_NAME}={token}"}


@pytest.mark.anyio
async def test_list_documents(auth_headers):
    """GET /api/documents must return all 4 canonical documents."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/documents", headers=auth_headers)
        assert resp.status_code == 200
        docs = resp.json()
        assert len(docs) == 4

        doc_ids = {d["id"] for d in docs}
        assert doc_ids == {
            "latvia_sdc_2023",
            "uk_sdr_2025",
            "netherlands_dwp_2024",
            "japan_doj_2026",
        }


@pytest.mark.anyio
async def test_get_document_details(auth_headers):
    """GET /api/documents/japan_doj_2026 must return full canonical metrics."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/documents/japan_doj_2026", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["id"] == "japan_doj_2026"
        assert data["country"] == "Japan"
        assert data["title"] == "Defense of Japan 2026"
        assert data["total_words"] == 324705
        assert data["total_segments"] == 3746
        assert data["detected_matches"] == 2956
        assert data["raw_baseline_total"] == 2943


@pytest.mark.anyio
async def test_get_document_not_found(auth_headers):
    """GET /api/documents/unknown_doc must return 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/documents/non_existent_doc", headers=auth_headers)
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_get_category_metrics(auth_headers):
    """GET /api/documents/japan_doj_2026/categories/Russia must return exact canonical metrics."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/documents/japan_doj_2026/categories/Russia", headers=auth_headers
        )
        assert resp.status_code == 200
        cat = resp.json()

        assert cat["category"] == "Russia"
        assert cat["raw_baseline_mentions"] == 890
        assert cat["segment_hits"] == 269
        assert abs(cat["frequency_per_1000_words"] - 2.740949) < 1e-6
        assert cat["detected_mentions"] == 903
        assert cat["review_required_mentions"] == 13


@pytest.mark.anyio
async def test_category_not_found(auth_headers):
    """GET /api/documents/japan_doj_2026/categories/Unknown must return 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/documents/japan_doj_2026/categories/NonExistent", headers=auth_headers
        )
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_japan_russia_passages_grouping(auth_headers):
    """GET /api/documents/japan_doj_2026/categories/Russia/passages grouping semantics."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/documents/japan_doj_2026/categories/Russia/passages",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        # Semantic rules:
        # - raw mentions remain 890
        # - unique passage items = 269
        assert data["total_raw_mentions"] == 890
        assert data["total_passages"] == 269
        assert len(data["passages"]) == 269

        # Check multi-match segment traceability: p080_s001
        p080 = next(
            (p for p in data["passages"] if p["segment_id"] == "japan_doj_2026_p080_s001"),
            None,
        )
        assert p080 is not None
        assert p080["match_count"] == 16
        assert len(p080["matches"]) == 16

        term_map = {item["term"]: item["count"] for item in p080["matched_terms"]}
        assert term_map.get("Russia") == 9
        assert term_map.get("Russia’s") == 2
        assert term_map.get("Russian") == 4
        assert term_map.get("Russian Federation") == 1


@pytest.mark.anyio
async def test_canonical_regression_all_documents(auth_headers):
    """Verify non-negotiable canonical numbers across all documents via API."""
    expected = {
        "latvia_sdc_2023": {"words": 7108, "segments": 151, "detected": 71},
        "uk_sdr_2025": {"words": 41923, "segments": 822, "detected": 162},
        "netherlands_dwp_2024": {"words": 18465, "segments": 148, "detected": 130},
        "japan_doj_2026": {"words": 324705, "segments": 3746, "detected": 2956},
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for doc_id, exp in expected.items():
            resp = await client.get(f"/api/documents/{doc_id}", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_words"] == exp["words"]
            assert data["total_segments"] == exp["segments"]
            assert data["detected_matches"] == exp["detected"]

        # Japan / China
        resp_china = await client.get(
            "/api/documents/japan_doj_2026/categories/China", headers=auth_headers
        )
        assert resp_china.status_code == 200
        china = resp_china.json()
        assert china["raw_baseline_mentions"] == 1441
        assert china["segment_hits"] == 384

        # Japan / Cyber
        resp_cyber = await client.get(
            "/api/documents/japan_doj_2026/categories/Cyber", headers=auth_headers
        )
        assert resp_cyber.status_code == 200
        cyber = resp_cyber.json()
        assert cyber["raw_baseline_mentions"] == 582
        assert cyber["segment_hits"] == 205

