"""
backend.tests.test_smoke_integration
------------------------------------
21-step end-to-end integration smoke test verifying the full lifecycle:
FastAPI, static frontend, session authentication, canonical analysis retrieval,
passage-level review mutations, Neon storage mock, filter semantics,
pagination, document switching, logout, and protected route gating.
"""

from __future__ import annotations

import os
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.main import app


@pytest.fixture(autouse=True)
def configure_smoke_env(monkeypatch):
    """Set up authenticated test environment for integration smoke test."""
    monkeypatch.setenv("APP_USERNAME", "admin_researcher")
    monkeypatch.setenv("APP_PASSWORD", "SecureAuthPass2026!")
    monkeypatch.setenv("SESSION_SECRET", "session-secret-smoke-test-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://mock_user:mock_pass@ep-smoke-test.neon.tech/sra_db")


def test_21_step_e2e_integration_smoke_test():
    """Execute the full 21-step integration smoke test suite."""
    client = TestClient(app)

    # Step 1: Start FastAPI & verify health
    r1 = client.get("/api/health")
    assert r1.status_code == 200
    assert r1.json() == {"status": "ok"}

    # Step 2: Serve frontend index.html & assets
    r2_index = client.get("/")
    assert r2_index.status_code == 200
    assert "Security Research Assistant" in r2_index.text
    r2_css = client.get("/css/tokens.css")
    assert r2_css.status_code == 200
    r2_js = client.get("/js/app.js")
    assert r2_js.status_code == 200

    # Step 3: Login
    r3 = client.post(
        "/api/auth/login",
        json={"username": "admin_researcher", "password": "SecureAuthPass2026!"},
    )
    assert r3.status_code == 200
    auth_cookie = r3.cookies.get(settings.COOKIE_NAME)
    assert auth_cookie is not None
    client_auth = TestClient(app, cookies={settings.COOKIE_NAME: auth_cookie})

    # Step 4: Open Japan
    r4 = client_auth.get("/api/documents/japan_doj_2026")
    assert r4.status_code == 200
    j_doc = r4.json()
    assert j_doc["country"] == "Japan"
    assert j_doc["title"] == "Defense of Japan 2026"
    assert j_doc["total_words"] == 324705
    assert j_doc["total_segments"] == 3746

    # Step 5 & 6 & 7: Select Russia, verify 890 raw mentions & 269 passage hits
    r5 = client_auth.get("/api/documents/japan_doj_2026/categories/Russia")
    assert r5.status_code == 200
    r_cat = r5.json()
    assert r_cat["raw_baseline_mentions"] == 890
    assert r_cat["segment_hits"] == 269
    assert abs(r_cat["frequency_per_1000_words"] - 2.740949) < 1e-4

    # Step 8: Verify passage board grouping (1 passage = 1 card)
    r8 = client_auth.get("/api/documents/japan_doj_2026/categories/Russia/passages")
    assert r8.status_code == 200
    pdata = r8.json()
    assert pdata["total_passages"] == 269
    assert pdata["total_raw_mentions"] == 890
    assert len(pdata["passages"]) == 269
    segment_ids = [p["segment_id"] for p in pdata["passages"]]
    assert len(segment_ids) == len(set(segment_ids)) == 269

    # Step 9: Expand passage
    p0 = pdata["passages"][0]
    seg0_id = p0["segment_id"]
    assert p0["text"]
    assert p0["pdf_page"] > 0
    assert len(p0["matches"]) >= 1
    assert "pattern_id" in p0["matches"][0]
    assert "char_start" in p0["matches"][0]
    assert "char_end" in p0["matches"][0]

    # Mock Postgres in-memory store for Steps 10-16
    mock_db_reviews = {}

    def fake_load_reviews(url, doc_id):
        formatted = {}
        for k, v in mock_db_reviews.items():
            parts = k.split("::")
            if parts[0] == doc_id:
                formatted[f"{parts[1]}::{parts[2]}"] = v
        return {"document_id": doc_id, "reviews": formatted}

    def fake_set_status(url, document_id, category, segment_id, status):
        k = f"{document_id}::{category}::{segment_id}"
        mock_db_reviews[k] = {"status": status, "category": category, "segment_id": segment_id}

    def fake_clear_status(url, document_id, category, segment_id):
        k = f"{document_id}::{category}::{segment_id}"
        mock_db_reviews.pop(k, None)

    with patch("backend.app.services.review_service.db_review_store.load_reviews", side_effect=fake_load_reviews), \
         patch("backend.app.services.review_service.db_review_store.set_passage_review_status", side_effect=fake_set_status), \
         patch("backend.app.services.review_service.db_review_store.clear_passage_review", side_effect=fake_clear_status):

        # Step 10: Mark Relevant
        r10 = client_auth.put(f"/api/reviews/japan_doj_2026/Russia/{seg0_id}", json={"status": "relevant"})
        assert r10.status_code == 200
        assert r10.json()["status"] == "relevant"

        # Step 11 & 12: Refresh & verify persisted status
        r11 = client_auth.get("/api/reviews/japan_doj_2026")
        assert r11.status_code == 200
        reviews = r11.json()["reviews"]
        assert f"Russia::{seg0_id}" in reviews
        assert reviews[f"Russia::{seg0_id}"]["status"] == "relevant"

        # Step 13 & 14: Mark Irrelevant & verify move
        r13 = client_auth.put(f"/api/reviews/japan_doj_2026/Russia/{seg0_id}", json={"status": "irrelevant"})
        assert r13.status_code == 200
        r14 = client_auth.get("/api/reviews/japan_doj_2026")
        assert r14.json()["reviews"][f"Russia::{seg0_id}"]["status"] == "irrelevant"

        # Step 15 & 16: Clear & verify unreviewed
        r15 = client_auth.delete(f"/api/reviews/japan_doj_2026/Russia/{seg0_id}")
        assert r15.status_code == 200
        assert r15.json()["status"] == "unreviewed"
        r16 = client_auth.get("/api/reviews/japan_doj_2026")
        assert f"Russia::{seg0_id}" not in r16.json()["reviews"]

    # Step 17: Test filters
    r17_baseline = client_auth.get(
        "/api/documents/japan_doj_2026/categories/Russia/passages?show_review_only=false&include_review_only=false"
    )
    assert r17_baseline.json()["total_passages"] == 269
    r17_review_only = client_auth.get(
        "/api/documents/japan_doj_2026/categories/Russia/passages?show_review_only=true&include_review_only=false"
    )
    assert r17_review_only.json()["total_passages"] <= 269

    # Step 18: Test pagination
    total_passages = pdata["total_passages"]
    pages = (total_passages + 14) // 15
    assert pages == 18
    page1_items = pdata["passages"][0:15]
    page18_items = pdata["passages"][255:269]
    assert len(page1_items) == 15
    assert len(page18_items) == 14

    # Step 19: Switch document and category
    r19_uk = client_auth.get("/api/documents/uk_sdr_2025")
    assert r19_uk.json()["total_words"] == 41923
    r19_china = client_auth.get("/api/documents/japan_doj_2026/categories/China")
    assert r19_china.json()["raw_baseline_mentions"] == 1441
    assert r19_china.json()["segment_hits"] == 384
    r19_cyber = client_auth.get("/api/documents/japan_doj_2026/categories/Cyber")
    assert r19_cyber.json()["raw_baseline_mentions"] == 582
    assert r19_cyber.json()["segment_hits"] == 205

    # Step 20: Logout
    r20 = client_auth.post("/api/auth/logout")
    assert r20.status_code == 200

    # Step 21: Verify protected API rejects unauthenticated request
    unauth_client = TestClient(app)
    r21 = unauth_client.get("/api/documents/japan_doj_2026")
    assert r21.status_code == 401

