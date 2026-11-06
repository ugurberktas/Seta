"""
backend.app.services.review_service
-----------------------------------
Service layer for human review decisions backed by PostgreSQL (Neon).
Reuses verified parameterized database adapter in src/db_review_store.py.
Never falls back to JSON.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.core.config import REPO_ROOT, settings

# Ensure src/ is importable for db_review_store
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

import db_review_store
from db_review_store import DatabaseStorageError


class ReviewServiceError(RuntimeError):
    """Raised when review storage operation cannot be performed."""
    pass


class ReviewService:
    """Manages passage review decisions in PostgreSQL."""

    def _get_db_url(self) -> str:
        url = settings.DATABASE_URL
        if not url:
            raise ReviewServiceError(
                "DATABASE_URL is not configured on the backend server. Persistent review operations require PostgreSQL."
            )
        return url

    def load_document_reviews(self, document_id: str) -> dict[str, Any]:
        """Load all review decisions for document_id from PostgreSQL.

        Raises ReviewServiceError if database connection fails.
        """
        db_url = self._get_db_url()
        try:
            return db_review_store.load_reviews(db_url, document_id)
        except DatabaseStorageError as exc:
            raise ReviewServiceError(f"Failed to load reviews from database: {exc}") from exc

    def set_review(
        self,
        document_id: str,
        category: str,
        segment_id: str,
        status: str,
    ) -> dict[str, str]:
        """Set or update a passage review decision (relevant/irrelevant) in PostgreSQL.

        Uses atomic parameterized UPSERT.
        """
        if status not in ("relevant", "irrelevant"):
            raise ValueError(f"Invalid review status '{status}'. Allowed: 'relevant', 'irrelevant'.")

        db_url = self._get_db_url()
        try:
            db_review_store.set_passage_review_status(
                db_url,
                document_id=document_id,
                category=category,
                segment_id=segment_id,
                status=status,
            )
            return {
                "document_id": document_id,
                "category": category,
                "segment_id": segment_id,
                "status": status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        except DatabaseStorageError as exc:
            raise ReviewServiceError(f"Failed to record review decision in database: {exc}") from exc

    def clear_review(
        self,
        document_id: str,
        category: str,
        segment_id: str,
    ) -> dict[str, str]:
        """Delete a passage review decision from PostgreSQL (absence = unreviewed)."""
        db_url = self._get_db_url()
        try:
            db_review_store.clear_passage_review(
                db_url,
                document_id=document_id,
                category=category,
                segment_id=segment_id,
            )
            return {
                "document_id": document_id,
                "category": category,
                "segment_id": segment_id,
                "status": "unreviewed",
                "cleared_at": datetime.now(timezone.utc).isoformat(),
            }
        except DatabaseStorageError as exc:
            raise ReviewServiceError(f"Failed to clear review decision in database: {exc}") from exc


review_service = ReviewService()

