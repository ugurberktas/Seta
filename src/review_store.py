"""
review_store.py
---------------
Persist researcher review decisions for threat-match records.

Storage: data/reviews/<document_id>_reviews.json
Matches: data/processed/<document_id>_core_body_threat_matches.json

The review file is SEPARATE from matcher output; re-running the matcher
does not overwrite reviews.

Allowed statuses: "unreviewed", "relevant", "irrelevant"
A match_id absent from the review file has effective status "unreviewed".
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REVIEWS_DIR = Path(__file__).parent.parent / "data" / "reviews"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

ALLOWED_STATUSES = {"unreviewed", "relevant", "irrelevant"}
SCHEMA_VERSION = 1
DEFAULT_SCOPE = "core_body"


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _review_path(document_id: str) -> Path:
    """Return the path to the review JSON for a given document."""
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    return REVIEWS_DIR / f"{document_id}_reviews.json"


def _matches_path(document_id: str, scope: str = DEFAULT_SCOPE) -> Path:
    """Return the path to the matcher output for a given document."""
    return PROCESSED_DIR / f"{document_id}_{scope}_threat_matches.json"


# ---------------------------------------------------------------------------
# Load / Save
# ---------------------------------------------------------------------------

def load_reviews(document_id: str) -> dict:
    """Load the review store for *document_id*.

    Returns a canonical dict:
        {
            "version": 1,
            "document_id": "...",
            "reviews": { "<match_id>": {"status": ..., "updated_at": ..., "note": ...} }
        }
    If the file does not exist, returns an empty-reviews structure.
    """
    path = _review_path(document_id)
    if not path.exists():
        return _empty_store(document_id)
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    # Basic migration / sanity
    if "reviews" not in data:
        data["reviews"] = {}
    return data


def save_reviews(document_id: str, data: dict) -> None:
    """Atomically write *data* to the review JSON for *document_id*.

    Uses write-to-temp + os.replace to minimise corrupt-file risk.
    """
    path = _review_path(document_id)
    # Write to a sibling temp file, then atomically replace
    fd, tmp_path = tempfile.mkstemp(
        dir=path.parent, prefix=".review_tmp_", suffix=".json"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        # Clean up temp file on failure
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


def _known_match_ids(matches_data: dict) -> set:
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
# Public API
# ---------------------------------------------------------------------------

def get_review_status(document_id: str, match_id: str) -> str:
    """Return the stored review status for *match_id*, or 'unreviewed'."""
    data = load_reviews(document_id)
    record = data["reviews"].get(match_id)
    if record is None:
        return "unreviewed"
    return record.get("status", "unreviewed")


def set_review_status(
    document_id: str,
    match_id: str,
    status: str,
    note: str = "",
    scope: str = DEFAULT_SCOPE,
) -> None:
    """Set the review status for *match_id*.

    Validates:
    - match_id exists in current matcher output
    - status is in ALLOWED_STATUSES (but 'unreviewed' clears the record
      rather than writing it, since absent == unreviewed)

    Raises:
        ValueError  — unknown match_id or invalid status
        FileNotFoundError — matcher output missing
    """
    _validate_status(status)
    matches_data = _load_matches_data(document_id, scope)
    validate_match_id(document_id, match_id, matches_data)

    data = load_reviews(document_id)
    if status == "unreviewed":
        # Remove the record; absence == unreviewed
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
    data = load_reviews(document_id)
    removed = data["reviews"].pop(match_id, None)
    save_reviews(document_id, data)
    if removed is None:
        # Already absent — not an error
        pass


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def get_review_summary(
    document_id: str,
    matches_data: dict | None = None,
    scope: str = DEFAULT_SCOPE,
) -> dict:
    """Return a breakdown of review statuses across all matches.

    Args:
        document_id: The document to summarise.
        matches_data: Pre-loaded matcher output (optional; loaded if None).
        scope: Matcher scope (default "core_body").

    Returns:
        {
            "overall": {total_matches, reviewed, unreviewed, relevant, irrelevant},
            "categories": { <cat>: {total, reviewed, unreviewed, relevant, irrelevant} }
        }
    """
    if matches_data is None:
        matches_data = _load_matches_data(document_id, scope)

    reviews = load_reviews(document_id)["reviews"]
    matches = matches_data.get("matches", [])

    # Collect all categories present in matches
    categories: dict[str, dict] = {}
    for m in matches:
        cat = m["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "reviewed": 0, "unreviewed": 0,
                               "relevant": 0, "irrelevant": 0}

    overall = {"total_matches": 0, "reviewed": 0, "unreviewed": 0,
               "relevant": 0, "irrelevant": 0}

    for m in matches:
        cat = m["category"]
        mid = m["match_id"]
        status = reviews.get(mid, {}).get("status", "unreviewed")

        overall["total_matches"] += 1
        categories[cat]["total"] += 1

        if status == "unreviewed":
            overall["unreviewed"] += 1
            categories[cat]["unreviewed"] += 1
        else:
            overall["reviewed"] += 1
            categories[cat]["reviewed"] += 1
            if status == "relevant":
                overall["relevant"] += 1
                categories[cat]["relevant"] += 1
            elif status == "irrelevant":
                overall["irrelevant"] += 1
                categories[cat]["irrelevant"] += 1

    return {"overall": overall, "categories": categories}
