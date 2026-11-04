"""
tests/test_postgres_storage.py
------------------------------
Unit and integration tests for PostgreSQL persistent review storage adapter.

Verifies:
1. Backend selection (Postgres when DATABASE_URL is set, JSON when absent)
2. JSON fallback and file isolation when DATABASE_URL is absent
3. Fail-safe behavior (DatabaseStorageError raised on connection/query failure; no silent fallback)
4. Parameterized SQL queries for load, upsert, clear
5. Absence = unreviewed semantics (unreviewed deletes row)
6. Upsert and clear semantics with mock adapter
7. No accidental migration or mutation of local JSON reviews in Postgres mode
8. Passage status resolution and summary consistency when backed by Postgres
"""

from __future__ import annotations

import datetime
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

import db_review_store
from db_review_store import DatabaseStorageError
import review_store


@pytest.fixture(autouse=True)
def reset_store_state(tmp_path, monkeypatch):
    """Ensure clean review store state for every test."""
    temp_reviews = tmp_path / "reviews"
    temp_reviews.mkdir(parents=True, exist_ok=True)
    review_store.set_reviews_dir(temp_reviews)
    review_store.set_database_url(None)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield temp_reviews
    review_store.set_reviews_dir(None)
    review_store.set_database_url(None)


class MockCursor:
    """Mock database cursor capturing executed SQL and parameters."""

    def __init__(self, fetchall_data=None):
        self.fetchall_data = fetchall_data or []
        self.executed_statements: list[tuple[str, tuple | None]] = []

    def execute(self, query: str, params: tuple | None = None):
        self.executed_statements.append((query.strip(), params))

    def fetchall(self):
        return self.fetchall_data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class MockConnection:
    """Mock database connection managing mock cursor lifecycle."""

    def __init__(self, cursor: MockCursor | None = None):
        self.cursor_obj = cursor or MockCursor()
        self.is_closed = False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.is_closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


# ===========================================================================
# 1. Backend Selection Tests
# ===========================================================================

def test_backend_selection_json_when_no_database_url():
    """When DATABASE_URL is not configured anywhere, backend must be 'json'."""
    assert review_store.get_database_url() is None
    assert review_store.get_storage_backend() == "json"


def test_backend_selection_postgres_when_env_set(monkeypatch):
    """When DATABASE_URL is set in environment, backend must be 'postgres'."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@ep-cool-db.aws.neon.tech/neondb")
    assert review_store.get_database_url() == "postgresql://user:pass@ep-cool-db.aws.neon.tech/neondb"
    assert review_store.get_storage_backend() == "postgres"


def test_backend_selection_custom_override():
    """Custom database URL override takes precedence."""
    review_store.set_database_url("postgresql://override:secret@remote.host:5432/db")
    assert review_store.get_storage_backend() == "postgres"
    assert review_store.get_database_url() == "postgresql://override:secret@remote.host:5432/db"


# ===========================================================================
# 2. JSON Fallback Tests
# ===========================================================================

def test_json_fallback_stores_locally(reset_store_state):
    """When no DATABASE_URL is set, operations create and update local JSON files."""
    doc_id = "test_doc"
    review_store.set_passage_review_status(doc_id, "Russia", "seg_001", "relevant")

    data = review_store.load_reviews(doc_id)
    assert data.get("backend") != "postgres"
    assert "Russia::seg_001" in data.get("reviews", {})
    assert data["reviews"]["Russia::seg_001"]["status"] == "relevant"

    # Verify JSON file exists on disk in isolated test directory
    json_path = reset_store_state / f"{doc_id}_reviews.json"
    assert json_path.exists()


# ===========================================================================
# 3. Fail-Safe Behavior Tests
# ===========================================================================

def test_fail_safe_raises_error_on_connection_failure():
    """If DATABASE_URL is set but DB cannot connect, raise DatabaseStorageError and DO NOT fallback."""
    fake_url = "postgresql://user:wrongpassword@nonexistent.domain.xyz:5432/db"
    review_store.set_database_url(fake_url)

    with pytest.raises(DatabaseStorageError) as exc_info:
        review_store.load_reviews("test_doc")
    assert "Failed to connect" in str(exc_info.value) or "Failed to load" in str(exc_info.value)

    # Must also raise on write
    with pytest.raises(DatabaseStorageError):
        review_store.set_passage_review_status("test_doc", "Russia", "seg_001", "relevant")

    # Must also raise on clear
    with pytest.raises(DatabaseStorageError):
        review_store.clear_passage_review("test_doc", "Russia", "seg_001")


def test_fail_safe_raises_when_psycopg2_missing(monkeypatch):
    """If psycopg2 is not installed, raise clear DatabaseStorageError."""
    monkeypatch.setattr(db_review_store, "psycopg2", None)
    with pytest.raises(DatabaseStorageError) as exc:
        db_review_store.get_connection("postgresql://localhost:5432/db")
    assert "psycopg2 is not installed" in str(exc.value)


# ===========================================================================
# 4. SQL Parameterization & Query Syntax Tests
# ===========================================================================

def test_load_reviews_parameterized_query():
    """db_review_store.load_reviews must use %s parameterization."""
    mock_cursor = MockCursor(
        fetchall_data=[
            ("Russia", "seg_001", "relevant", datetime.datetime(2026, 11, 4, 12, 0, 0, tzinfo=datetime.timezone.utc)),
            ("China", "seg_002", "irrelevant", datetime.datetime(2026, 11, 4, 12, 5, 0, tzinfo=datetime.timezone.utc)),
        ]
    )
    mock_conn = MockConnection(mock_cursor)

    with patch("db_review_store.get_connection", return_value=mock_conn):
        result = db_review_store.load_reviews("dummy_url", "japan_doj_2026")

    assert mock_conn.is_closed is True
    assert len(mock_cursor.executed_statements) == 1
    query, params = mock_cursor.executed_statements[0]

    # Verify parameterized placeholder and params
    assert "%s" in query
    assert params == ("japan_doj_2026",)
    assert "SELECT category, segment_id, status, updated_at" in query
    assert "WHERE document_id = %s" in query

    # Verify returned structure
    assert result["version"] == 1
    assert result["document_id"] == "japan_doj_2026"
    assert result["backend"] == "postgres"
    assert len(result["reviews"]) == 2
    assert result["reviews"]["Russia::seg_001"]["status"] == "relevant"
    assert result["reviews"]["China::seg_002"]["status"] == "irrelevant"


def test_set_passage_review_status_upsert():
    """db_review_store.set_passage_review_status must use parameterized INSERT ... ON CONFLICT."""
    mock_cursor = MockCursor()
    mock_conn = MockConnection(mock_cursor)

    with patch("db_review_store.get_connection", return_value=mock_conn):
        db_review_store.set_passage_review_status(
            "dummy_url", "japan_doj_2026", "Russia", "p080_s001", "relevant"
        )

    assert mock_conn.is_closed is True
    assert len(mock_cursor.executed_statements) == 1
    query, params = mock_cursor.executed_statements[0]

    assert "INSERT INTO review_decisions" in query
    assert "ON CONFLICT (document_id, category, segment_id)" in query
    assert "DO UPDATE SET status = EXCLUDED.status, updated_at = NOW()" in query
    assert params == ("japan_doj_2026", "Russia", "p080_s001", "relevant")


def test_clear_passage_review_delete():
    """db_review_store.clear_passage_review must use parameterized DELETE."""
    mock_cursor = MockCursor()
    mock_conn = MockConnection(mock_cursor)

    with patch("db_review_store.get_connection", return_value=mock_conn):
        db_review_store.clear_passage_review(
            "dummy_url", "japan_doj_2026", "Russia", "p080_s001"
        )

    assert mock_conn.is_closed is True
    assert len(mock_cursor.executed_statements) == 1
    query, params = mock_cursor.executed_statements[0]

    assert "DELETE FROM review_decisions" in query
    assert "WHERE document_id = %s AND category = %s AND segment_id = %s" in query
    assert params == ("japan_doj_2026", "Russia", "p080_s001")


def test_unreviewed_status_triggers_delete():
    """Setting status='unreviewed' in Postgres mode must DELETE the row (absence = unreviewed)."""
    mock_cursor = MockCursor()
    mock_conn = MockConnection(mock_cursor)

    with patch("db_review_store.get_connection", return_value=mock_conn):
        db_review_store.set_passage_review_status(
            "dummy_url", "japan_doj_2026", "Russia", "p080_s001", "unreviewed"
        )

    assert len(mock_cursor.executed_statements) == 1
    query, params = mock_cursor.executed_statements[0]
    assert "DELETE FROM review_decisions" in query
    assert params == ("japan_doj_2026", "Russia", "p080_s001")


def test_invalid_status_raises_value_error():
    """Invalid review status must raise ValueError before touching database."""
    with pytest.raises(ValueError):
        db_review_store.set_passage_review_status(
            "dummy_url", "doc1", "Russia", "s1", "maybe"
        )


# ===========================================================================
# 5. Isolation: No Local JSON Mutation in Postgres Mode
# ===========================================================================

def test_no_local_json_mutation_in_postgres_mode(reset_store_state):
    """When running in Postgres mode, local JSON files must NOT be touched or created."""
    review_store.set_database_url("postgresql://mock:secret@cloud.neon.tech/db")

    mock_cursor = MockCursor()
    mock_conn = MockConnection(mock_cursor)

    with patch("db_review_store.get_connection", return_value=mock_conn):
        review_store.set_passage_review_status("japan_doj_2026", "Russia", "p080_s001", "relevant")

    # Local review dir must remain completely empty of json files
    json_files = list(reset_store_state.glob("*.json"))
    assert len(json_files) == 0


# ===========================================================================
# 6. End-to-End Review Store Delegation in Postgres Mode
# ===========================================================================

def test_review_store_delegation_to_postgres():
    """review_store.load_reviews and set_passage_review_status delegate cleanly to postgres."""
    review_store.set_database_url("postgresql://mock:secret@cloud.neon.tech/db")

    in_memory_db: dict[tuple[str, str, str], str] = {}

    def fake_get_connection(url):
        class MemoryCursor:
            def __init__(self):
                self.data = []

            def execute(self, query, params=None):
                q = query.strip()
                if "SELECT category, segment_id, status" in q:
                    doc_id = params[0]
                    self.data = [
                        (cat, seg, st, datetime.datetime.now(datetime.timezone.utc))
                        for (d, cat, seg), st in in_memory_db.items()
                        if d == doc_id
                    ]
                elif "INSERT INTO review_decisions" in q:
                    doc_id, cat, seg, st = params
                    in_memory_db[(doc_id, cat, seg)] = st
                elif "DELETE FROM review_decisions" in q:
                    doc_id, cat, seg = params
                    in_memory_db.pop((doc_id, cat, seg), None)

            def fetchall(self):
                return self.data

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

        return MockConnection(MemoryCursor())

    with patch("db_review_store.get_connection", side_effect=fake_get_connection):
        # 1. Initially empty
        data = review_store.load_reviews("doc_cloud")
        assert len(data["reviews"]) == 0

        # 2. Set Relevant
        review_store.set_passage_review_status("doc_cloud", "Russia", "s10", "relevant")
        data = review_store.load_reviews("doc_cloud")
        assert "Russia::s10" in data["reviews"]
        assert data["reviews"]["Russia::s10"]["status"] == "relevant"

        # 3. Update to Irrelevant (UPSERT)
        review_store.set_passage_review_status("doc_cloud", "Russia", "s10", "irrelevant")
        data = review_store.load_reviews("doc_cloud")
        assert data["reviews"]["Russia::s10"]["status"] == "irrelevant"

        # 4. Set another passage
        review_store.set_passage_review_status("doc_cloud", "China", "s20", "relevant")
        data = review_store.load_reviews("doc_cloud")
        assert len(data["reviews"]) == 2

        # 5. Clear first passage (DELETE)
        review_store.clear_passage_review("doc_cloud", "Russia", "s10")
        data = review_store.load_reviews("doc_cloud")
        assert "Russia::s10" not in data["reviews"]
        assert "China::s20" in data["reviews"]


# ===========================================================================
# 7. SSL Configuration Test
# ===========================================================================

def test_ssl_applied_for_remote_hosts():
    """Remote PostgreSQL URLs must receive sslmode='require' by default."""
    mock_connect = MagicMock()
    with patch("db_review_store.psycopg2.connect", mock_connect):
        remote_url = "postgresql://user:pass@ep-cool-db.aws.neon.tech:5432/neondb"
        db_review_store.get_connection(remote_url)
        mock_connect.assert_called_once_with(remote_url, sslmode="require")


def test_ssl_not_forced_for_localhost():
    """Localhost PostgreSQL URLs do not get sslmode forced."""
    mock_connect = MagicMock()
    with patch("db_review_store.psycopg2.connect", mock_connect):
        local_url = "postgresql://user:pass@localhost:5432/neondb"
        db_review_store.get_connection(local_url)
        mock_connect.assert_called_once_with(local_url)

