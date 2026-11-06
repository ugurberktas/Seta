"""
backend.tests.test_frontend_assets
----------------------------------
Tests ensuring the static frontend assets exist, have valid structure,
and integrate seamlessly with the FastAPI backend.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def test_frontend_structure_exists():
    """Verify all required frontend files and directories exist."""
    assert FRONTEND_DIR.is_dir()
    assert (FRONTEND_DIR / "index.html").is_file()
    assert (FRONTEND_DIR / "css" / "tokens.css").is_file()
    assert (FRONTEND_DIR / "css" / "base.css").is_file()
    assert (FRONTEND_DIR / "css" / "layout.css").is_file()
    assert (FRONTEND_DIR / "css" / "components.css").is_file()
    assert (FRONTEND_DIR / "js" / "api.js").is_file()
    assert (FRONTEND_DIR / "js" / "auth.js").is_file()
    assert (FRONTEND_DIR / "js" / "state.js").is_file()
    assert (FRONTEND_DIR / "js" / "documents.js").is_file()
    assert (FRONTEND_DIR / "js" / "passages.js").is_file()
    assert (FRONTEND_DIR / "js" / "charts.js").is_file()
    assert (FRONTEND_DIR / "js" / "app.js").is_file()
    assert (FRONTEND_DIR / "assets").is_dir()
    assert (PROJECT_ROOT / "netlify.toml").is_file()


def test_index_html_contains_critical_elements():
    """Verify index.html contains essential DOM elements for auth and main app."""
    content = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    assert 'id="auth-view"' in content
    assert 'id="app-view"' in content
    assert 'id="login-form"' in content
    assert 'id="login-username"' in content
    assert 'id="login-password"' in content
    assert 'id="login-submit-btn"' in content
    assert 'id="document-select"' in content
    assert 'id="category-select"' in content
    assert 'id="language-select"' in content
    assert 'id="filter-review-only"' in content
    assert 'id="filter-include-baseline"' in content
    assert 'id="source-passages-container"' in content
    assert 'id="document-overview-container"' in content
    assert 'id="category-metrics-container"' in content
    assert 'id="category-chart-container"' in content
    assert 'id="cross-doc-chart-container"' in content
    assert 'type="module"' in content
    assert 'src="./js/app.js"' in content


def test_static_files_served_by_fastapi():
    """Verify FastAPI serves index.html and static assets correctly."""
    client = TestClient(app)

    # 1. Root index.html
    res_index = client.get("/")
    assert res_index.status_code == 200
    assert "Security Research Assistant" in res_index.text

    # 2. CSS assets
    res_css = client.get("/css/tokens.css")
    assert res_css.status_code == 200
    assert "--color-primary" in res_css.text

    # 3. JS assets
    res_js = client.get("/js/passages.js")
    assert res_js.status_code == 200
    assert "executeReviewDecision" in res_js.text


from backend.app.core.config import settings
from backend.app.core.security import create_session_token


def test_japan_russia_passage_semantics_in_api(monkeypatch):
    """Verify exact analytical values for Japan / Russia with authenticated session."""
    monkeypatch.setenv("SESSION_SECRET", "test-secret-12345")
    token = create_session_token("test_user")
    client = TestClient(app, cookies={settings.COOKIE_NAME: token})

    res = client.get("/api/documents/japan_doj_2026/categories/Russia/passages")
    assert res.status_code == 200
    data = res.json()

    assert data["document_id"] == "japan_doj_2026"
    assert data["category"] == "Russia"
    assert data["total_raw_mentions"] == 890
    assert data["total_passages"] == 269
    assert len(data["passages"]) == 269

    # Each item in passages is 1 unique segment
    segment_ids = [p["segment_id"] for p in data["passages"]]
    assert len(segment_ids) == len(set(segment_ids)) == 269

