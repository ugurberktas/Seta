"""
review_store.py
---------------
Persist researcher review decisions for threat-match and passage records.

Storage: data/reviews/<document_id>_reviews.json
Matches: data/processed/<document_id>_core_body_threat_matches.json

The review file is SEPARATE from matcher output; re-running the matcher
does not overwrite reviews.

Allowed statuses: "unreviewed", "relevant", "irrelevant"
A record absent from the review file has effective status "unreviewed".
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import db_review_store
from db_review_store import DatabaseStorageError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_REVIEWS_DIR = Path(__file__).parent.parent / "data" / "reviews"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

_custom_reviews_dir: Path | None = None
_custom_database_url: str | None = None

ALLOWED_STATUSES = {"unreviewed", "relevant", "irrelevant"}
SCHEMA_VERSION = 1
DEFAULT_SCOPE = "core_body"


# ---------------------------------------------------------------------------
# Backend Selection & Configuration
# ---------------------------------------------------------------------------

def get_database_url() -> str | None:
    """Return configured DATABASE_URL from custom override, env, or Streamlit secrets."""
    if _custom_database_url is not None:
        return _custom_database_url
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "DATABASE_URL" in st.secrets:
            return str(st.secrets["DATABASE_URL"])
    except Exception:
        pass
    return None


def set_database_url(url: str | None) -> None:
    """Configure or override the active database URL for testing/isolation."""
    global _custom_database_url
    _custom_database_url = url


def get_storage_backend() -> str:
    """Return 'postgres' if DATABASE_URL is configured, else 'json'."""
    return "postgres" if get_database_url() else "json"


# ---------------------------------------------------------------------------
# Path & Directory Isolation Helpers
# ---------------------------------------------------------------------------

def get_reviews_dir() -> Path:
    """Return the active reviews directory (supports runtime and test isolation)."""
    if _custom_reviews_dir is not None:
        return _custom_reviews_dir
    env_dir = os.environ.get("SETA_REVIEWS_DIR")
    if env_dir:
        return Path(env_dir)
    return DEFAULT_REVIEWS_DIR


def set_reviews_dir(path: Path | str | None) -> None:
    """Configure a custom reviews directory for testing or isolation."""
    global _custom_reviews_dir
    _custom_reviews_dir = Path(path) if path is not None else None


def _review_path(document_id: str) -> Path:
    """Return the path to the review JSON for a given document."""
    reviews_dir = get_reviews_dir()
    reviews_dir.mkdir(parents=True, exist_ok=True)
    return reviews_dir / f"{document_id}_reviews.json"


def _matches_path(document_id: str, scope: str = DEFAULT_SCOPE) -> Path:
    """Return the path to the matcher output for a given document."""
    return PROCESSED_DIR / f"{document_id}_{scope}_threat_matches.json"


# ---------------------------------------------------------------------------
# Concurrency File Lock
# ---------------------------------------------------------------------------

@contextmanager
def document_lock(document_id: str):
    """Acquire a per-document file lock to ensure atomic read-modify-write."""
    lock_dir = get_reviews_dir() / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{document_id}.lock"
    with open(lock_path, "a+") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Passage Key Helper
# ---------------------------------------------------------------------------

def make_passage_key(category: str, segment_id: str) -> str:
    """Construct the canonical passage-category review key."""
    return f"{category}::{segment_id}"


def parse_passage_key(key: str) -> tuple[str, str] | None:
    """Split '{category}::{segment_id}' into (category, segment_id), or None."""
    if "::" in key:
        parts = key.split("::", 1)
        return parts[0], parts[1]
    return None


def normalize_status(status: Any) -> str:
    """Safely normalise a review status; invalid values default to 'unreviewed'."""
    if isinstance(status, str) and status in ALLOWED_STATUSES:
        return status
    return "unreviewed"


# ---------------------------------------------------------------------------
# Load / Save
# ---------------------------------------------------------------------------

def load_reviews(document_id: str) -> dict:
    """Load the review store for *document_id*.

    Returns a canonical dict:
        {
            "version": 1,
            "document_id": "...",
            "reviews": { ... }
        }
    If the file does not exist, returns an empty-reviews structure.
    Uses PostgreSQL if DATABASE_URL is configured, else local JSON.
    """
    db_url = get_database_url()
    if db_url:
        return db_review_store.load_reviews(db_url, document_id)

    path = _review_path(document_id)
    if not path.exists():
        return _empty_store(document_id)
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if "reviews" not in data:
        data["reviews"] = {}
    return data


def save_reviews(document_id: str, data: dict) -> None:
    """Atomically write *data* to the review JSON for *document_id*.

    Uses write-to-temp + os.replace to minimise corrupt-file risk.
    """
    path = _review_path(document_id)
    fd, tmp_path = tempfile.mkstemp(
        dir=path.parent, prefix=".review_tmp_", suffix=".json"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _empty_store(document_id: str) -> dict:
    return {
        "version": SCHEMA_VERSION,
        "document_id": document_id,
        "reviews": {},
    }


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _load_matches_data(document_id: str, scope: str = DEFAULT_SCOPE) -> dict:
    """Load matcher output; raise FileNotFoundError if missing."""
    path = _matches_path(document_id, scope)
    if not path.exists():
        raise FileNotFoundError(
            f"Matcher output not found: {path}\n"
            "Run match_threats.py first."
        )
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _known_match_ids(matches_data: dict) -> set[str]:
    return {m["match_id"] for m in matches_data.get("matches", [])}


def validate_match_id(
    document_id: str,
    match_id: str,
    matches_data: dict,
) -> None:
    """Raise ValueError if *match_id* is not in the matcher output."""
    known = _known_match_ids(matches_data)
    if match_id not in known:
        raise ValueError(
            f"Unknown match_id '{match_id}' for document '{document_id}'.\n"
            f"It does not exist in the current matcher output."
        )


def _validate_status(status: str) -> None:
    if status not in ALLOWED_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. Allowed: {sorted(ALLOWED_STATUSES)}"
        )


# ---------------------------------------------------------------------------
# Passage-Level Resolution & Status Logic
# ---------------------------------------------------------------------------

def resolve_passage_status(
    category: str,
    segment_id: str,
    constituent_matches: list[dict] | None,
    reviews_dict: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Determine effective passage review status from passage decisions and legacy match records.

    Rules:
    1. Direct passage-level record ("{category}::{segment_id}") takes precedence.
    2. If no direct record, inspect legacy match-level records:
       - No reviewed legacy matches -> "unreviewed"
       - All reviewed legacy matches have same status -> inherit that status (unanimous)
       - Conflicting statuses -> "unreviewed" (flagged as legacy conflict)
    3. Invalid/unknown stored values are strictly treated as "unreviewed".

    Returns:
        (effective_status, diagnostics_dict)
    """
    passage_key = make_passage_key(category, segment_id)
    record = reviews_dict.get(passage_key)
    if record is not None and isinstance(record, dict):
        raw_status = record.get("status")
        if raw_status in ("relevant", "irrelevant"):
            return raw_status, {"source": "passage", "raw_status": raw_status}
        elif raw_status == "unreviewed":
            return "unreviewed", {"source": "passage", "raw_status": "unreviewed"}
        else:
            return "unreviewed", {
                "source": "invalid_status",
                "raw_status": raw_status,
                "note": "Invalid passage status treated as unreviewed",
            }

    # No direct passage record: inspect legacy constituent matches
    if not constituent_matches:
        return "unreviewed", {"source": "default"}

    legacy_statuses: list[str] = []
    invalid_found: list[Any] = []

    for m in constituent_matches:
        mid = m.get("match_id")
        if not mid:
            continue
        m_rec = reviews_dict.get(mid)
        if m_rec is not None and isinstance(m_rec, dict):
            s = m_rec.get("status")
            if s in ("relevant", "irrelevant"):
                legacy_statuses.append(s)
            elif s == "unreviewed":
                pass
            else:
                invalid_found.append(s)

    if not legacy_statuses:
        diag: dict[str, Any] = {"source": "default"}
        if invalid_found:
            diag["invalid_legacy_statuses"] = invalid_found
        return "unreviewed", diag

    unique_statuses = set(legacy_statuses)
    if len(unique_statuses) == 1:
        inherited = legacy_statuses[0]
        diag = {
            "source": "legacy_unanimous",
            "inherited_from_matches": len(legacy_statuses),
        }
        if invalid_found:
            diag["invalid_legacy_statuses"] = invalid_found
        return inherited, diag

    # Conflicting legacy statuses exist
    return "unreviewed", {
        "source": "legacy_conflict",
        "conflicting_statuses": sorted(unique_statuses),
        "total_matches_reviewed": len(legacy_statuses),
    }


def get_passage_review_status(
    document_id: str,
    category: str,
    segment_id: str,
    constituent_matches: list[dict] | None = None,
    reviews_data: dict | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return the effective review status and diagnostics for a passage."""
    if reviews_data is None:
        reviews_data = load_reviews(document_id)
    reviews_dict = reviews_data.get("reviews", {})
    return resolve_passage_status(category, segment_id, constituent_matches, reviews_dict)


def set_passage_review_status(
    document_id: str,
    category: str,
    segment_id: str,
    status: str,
    note: str = "",
) -> None:
    """Set the review status for (document_id, category, segment_id).

    Uses PostgreSQL atomic UPSERT if DATABASE_URL is configured,
    else JSON backend with document lock.
    """
    _validate_status(status)
    db_url = get_database_url()
    if db_url:
        db_review_store.set_passage_review_status(
            db_url, document_id, category, segment_id, status, note
        )
        return

    passage_key = make_passage_key(category, segment_id)

    with document_lock(document_id):
        data = load_reviews(document_id)
        data.setdefault("reviews", {})
        data["reviews"][passage_key] = {
            "status": status,
            "category": category,
            "segment_id": segment_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "note": note,
        }
        save_reviews(document_id, data)


def clear_passage_review(
    document_id: str,
    category: str,
    segment_id: str,
    constituent_matches: list[dict] | None = None,
) -> None:
    """Clear review for (document_id, category, segment_id).

    In PostgreSQL, deletes the row.
    In JSON, explicitly sets the passage status to 'unreviewed' so that legacy
    match-level records do not re-inherit a status.
    """
    db_url = get_database_url()
    if db_url:
        db_review_store.clear_passage_review(
            db_url, document_id, category, segment_id
        )
        return

    set_passage_review_status(document_id, category, segment_id, "unreviewed")


# ---------------------------------------------------------------------------
# Match-Level API (Backward Compatibility)
# ---------------------------------------------------------------------------

def get_review_status(document_id: str, match_id: str) -> str:
    """Return the stored review status for *match_id*, or 'unreviewed'."""
    data = load_reviews(document_id)
    record = data.get("reviews", {}).get(match_id)
    if record is None or not isinstance(record, dict):
        return "unreviewed"
    return normalize_status(record.get("status"))


def set_review_status(
    document_id: str,
    match_id: str,
    status: str,
    note: str = "",
    scope: str = DEFAULT_SCOPE,
) -> None:
    """Set the review status for *match_id*."""
    _validate_status(status)
    matches_data = _load_matches_data(document_id, scope)
    validate_match_id(document_id, match_id, matches_data)

    db_url = get_database_url()
    if db_url:
        match_obj = next(m for m in matches_data["matches"] if m["match_id"] == match_id)
        db_review_store.set_passage_review_status(
            db_url, document_id, match_obj["category"], match_obj["segment_id"], status, note
        )
        return

    with document_lock(document_id):
        data = load_reviews(document_id)
        data.setdefault("reviews", {})
        if status == "unreviewed":
            data["reviews"].pop(match_id, None)
        else:
            data["reviews"][match_id] = {
                "status": status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "note": note,
            }
        save_reviews(document_id, data)


def clear_review(document_id: str, match_id: str) -> None:
    """Remove the review record for *match_id* (effective status → unreviewed)."""
    db_url = get_database_url()
    if db_url:
        matches_data = _load_matches_data(document_id)
        match_obj = next((m for m in matches_data.get("matches", []) if m["match_id"] == match_id), None)
        if match_obj:
            db_review_store.clear_passage_review(
                db_url, document_id, match_obj["category"], match_obj["segment_id"]
            )
        return

    with document_lock(document_id):
        data = load_reviews(document_id)
        data.setdefault("reviews", {})
        removed = data["reviews"].pop(match_id, None)
        save_reviews(document_id, data)
        if removed is None:
            pass


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def get_review_summary(
    document_id: str,
    matches_data: dict | None = None,
    scope: str = DEFAULT_SCOPE,
) -> dict:
    """Return a breakdown of review statuses across passages and matches.

    Args:
        document_id: The document to summarise.
        matches_data: Pre-loaded matcher output (optional; loaded if None).
        scope: Matcher scope (default "core_body").

    Returns:
        {
            "overall": {total_matches, reviewed, unreviewed, relevant, irrelevant},
            "categories": { <cat>: {total, reviewed, unreviewed, relevant, irrelevant} },
            "passages": {
                "overall": {total_passages, reviewed, unreviewed, relevant, irrelevant},
                "categories": { <cat>: {total, reviewed, unreviewed, relevant, irrelevant} }
            }
        }
    """
    if matches_data is None:
        matches_data = _load_matches_data(document_id, scope)

    reviews_data = load_reviews(document_id)
    reviews_dict = reviews_data.get("reviews", {})
    matches = matches_data.get("matches", [])

    # Group matches by (category, segment_id)
    passages_by_cat_seg: dict[tuple[str, str], list[dict]] = {}
    categories_present: set[str] = set()

    for m in matches:
        cat = m["category"]
        seg_id = m["segment_id"]
        categories_present.add(cat)
        key = (cat, seg_id)
        if key not in passages_by_cat_seg:
            passages_by_cat_seg[key] = []
        passages_by_cat_seg[key].append(m)

    # Initialize structures
    categories_matches: dict[str, dict] = {
        cat: {"total": 0, "reviewed": 0, "unreviewed": 0, "relevant": 0, "irrelevant": 0}
        for cat in categories_present
    }
    overall_matches = {
        "total_matches": 0, "reviewed": 0, "unreviewed": 0, "relevant": 0, "irrelevant": 0
    }

    categories_passages: dict[str, dict] = {
        cat: {"total": 0, "reviewed": 0, "unreviewed": 0, "relevant": 0, "irrelevant": 0}
        for cat in categories_present
    }
    overall_passages = {
        "total_passages": 0, "reviewed": 0, "unreviewed": 0, "relevant": 0, "irrelevant": 0
    }

    # Evaluate passage-level statuses and tally
    for (cat, seg_id), c_matches in passages_by_cat_seg.items():
        status, _ = resolve_passage_status(cat, seg_id, c_matches, reviews_dict)
        overall_passages["total_passages"] += 1
        categories_passages[cat]["total"] += 1

        if status == "unreviewed":
            overall_passages["unreviewed"] += 1
            categories_passages[cat]["unreviewed"] += 1
        else:
            overall_passages["reviewed"] += 1
            categories_passages[cat]["reviewed"] += 1
            if status == "relevant":
                overall_passages["relevant"] += 1
                categories_passages[cat]["relevant"] += 1
            elif status == "irrelevant":
                overall_passages["irrelevant"] += 1
                categories_passages[cat]["irrelevant"] += 1

        # Match tallying (inherits passage status if resolved, or direct match status)
        for m in c_matches:
            overall_matches["total_matches"] += 1
            categories_matches[cat]["total"] += 1
            if status == "unreviewed":
                overall_matches["unreviewed"] += 1
                categories_matches[cat]["unreviewed"] += 1
            else:
                overall_matches["reviewed"] += 1
                categories_matches[cat]["reviewed"] += 1
                if status == "relevant":
                    overall_matches["relevant"] += 1
                    categories_matches[cat]["relevant"] += 1
                elif status == "irrelevant":
                    overall_matches["irrelevant"] += 1
                    categories_matches[cat]["irrelevant"] += 1

    return {
        "overall": overall_matches,
        "categories": categories_matches,
        "passages": {
            "overall": overall_passages,
            "categories": categories_passages,
        },
    }
