"""
db_review_store.py
------------------
PostgreSQL storage adapter for passage-level review decisions.
Used in cloud deployment (e.g. Streamlit Community Cloud) when DATABASE_URL is configured.

Review unit: (document_id, category, segment_id)
Table: review_decisions
"""

from __future__ import annotations

import os
from typing import Any

try:
    import psycopg2
except ImportError:
    psycopg2 = None  # type: ignore[assignment]


TABLE_NAME = "review_decisions"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS review_decisions (
    document_id TEXT NOT NULL,
    category TEXT NOT NULL,
    segment_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('relevant', 'irrelevant')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (document_id, category, segment_id)
);
CREATE INDEX IF NOT EXISTS idx_review_decisions_doc
    ON review_decisions (document_id);
"""


class DatabaseStorageError(RuntimeError):
    """Raised when PostgreSQL storage operation fails."""
    pass


def get_connection(db_url: str):
    """Open a psycopg2 connection with SSL configuration as appropriate."""
    if psycopg2 is None:
        raise DatabaseStorageError(
            "psycopg2 is not installed. Install psycopg2-binary to use PostgreSQL backend."
        )

    conn_kwargs: dict[str, Any] = {}
    lower_url = db_url.lower()
    # Apply sslmode=require for remote hosts unless already specified or localhost
    if (
        "sslmode" not in lower_url
        and "localhost" not in lower_url
        and "127.0.0.1" not in lower_url
    ):
        conn_kwargs["sslmode"] = "require"

    try:
        return psycopg2.connect(db_url, **conn_kwargs)
    except Exception as exc:
        raise DatabaseStorageError(
            f"Failed to connect to PostgreSQL database: {exc}"
        ) from exc


def init_table_if_needed(db_url: str) -> None:
    """Safely and idempotently ensure review_decisions table exists."""
    conn = get_connection(db_url)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_TABLE_SQL)
    except Exception as exc:
        raise DatabaseStorageError(
            f"Failed to initialize review_decisions table: {exc}"
        ) from exc
    finally:
        conn.close()


def load_reviews(db_url: str, document_id: str) -> dict:
    """Load all review decisions for *document_id* from PostgreSQL.

    Returns the canonical reviews snapshot dictionary:
        {
            "version": 1,
            "document_id": document_id,
            "backend": "postgres",
            "reviews": {
                "<category>::<segment_id>": {
                    "status": "relevant" | "irrelevant",
                    "category": ...,
                    "segment_id": ...,
                    "updated_at": ...
                }
            }
        }
    """
    query = """
    SELECT category, segment_id, status, updated_at
    FROM review_decisions
    WHERE document_id = %s;
    """
    conn = get_connection(db_url)
    try:
        reviews: dict[str, dict[str, Any]] = {}
        with conn:
            with conn.cursor() as cur:
                cur.execute(query, (document_id,))
                rows = cur.fetchall()
                for cat, seg_id, status, updated_at in rows:
                    passage_key = f"{cat}::{seg_id}"
                    updated_str = (
                        updated_at.isoformat()
                        if hasattr(updated_at, "isoformat")
                        else str(updated_at)
                    )
                    reviews[passage_key] = {
                        "status": status,
                        "category": cat,
                        "segment_id": seg_id,
                        "updated_at": updated_str,
                    }
        return {
            "version": 1,
            "document_id": document_id,
            "backend": "postgres",
            "reviews": reviews,
        }
    except Exception as exc:
        raise DatabaseStorageError(
            f"Failed to load reviews for document '{document_id}' from PostgreSQL: {exc}"
        ) from exc
    finally:
        conn.close()


def set_passage_review_status(
    db_url: str,
    document_id: str,
    category: str,
    segment_id: str,
    status: str,
    note: str = "",
) -> None:
    """Set or update a passage review decision in PostgreSQL.

    Uses parameterized atomic UPSERT: INSERT ... ON CONFLICT ... DO UPDATE.
    If status is 'unreviewed', the decision row is removed (absence = unreviewed).
    """
    if status == "unreviewed":
        clear_passage_review(db_url, document_id, category, segment_id)
        return

    if status not in ("relevant", "irrelevant"):
        raise ValueError(
            f"Invalid status '{status}'. PostgreSQL backend only stores 'relevant' or 'irrelevant'."
        )

    query = """
    INSERT INTO review_decisions (document_id, category, segment_id, status, updated_at)
    VALUES (%s, %s, %s, %s, NOW())
    ON CONFLICT (document_id, category, segment_id)
    DO UPDATE SET status = EXCLUDED.status, updated_at = NOW();
    """
    conn = get_connection(db_url)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(query, (document_id, category, segment_id, status))
    except Exception as exc:
        raise DatabaseStorageError(
            f"Failed to set review status in PostgreSQL for ({document_id}, {category}, {segment_id}): {exc}"
        ) from exc
    finally:
        conn.close()


def clear_passage_review(
    db_url: str,
    document_id: str,
    category: str,
    segment_id: str,
) -> None:
    """Clear (delete) a passage review decision from PostgreSQL."""
    query = """
    DELETE FROM review_decisions
    WHERE document_id = %s AND category = %s AND segment_id = %s;
    """
    conn = get_connection(db_url)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(query, (document_id, category, segment_id))
    except Exception as exc:
        raise DatabaseStorageError(
            f"Failed to clear review decision in PostgreSQL for ({document_id}, {category}, {segment_id}): {exc}"
        ) from exc
    finally:
        conn.close()

