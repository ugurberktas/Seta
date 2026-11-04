"""
tests/test_review_hardening.py
------------------------------
Focused test suite for final review-layer hardening:
- passage grouping by (category, segment_id)
- duplicate card prevention
- legacy unanimous review inheritance
- legacy conflicting reviews fallback to unreviewed
- passage-level decision precedence
- filter order & review-only / review-required interaction
- invalid status normalization
- review store temporary directory isolation
- concurrency safety
- canonical analysis values regression protection
"""

import concurrent.futures
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

import pytest

from app.app import (
    get_active_matches,
    group_matches_into_passages,
    group_passages_by_status,
    load_analysis,
)
from review_store import (
    clear_passage_review,
    clear_review,
    get_passage_review_status,
    get_review_status,
    get_review_summary,
    get_reviews_dir,
    load_reviews,
    make_passage_key,
    normalize_status,
    resolve_passage_status,
    set_passage_review_status,
    set_review_status,
    set_reviews_dir,
)

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"


@pytest.fixture(autouse=True)
def isolated_review_dir(tmp_path, monkeypatch):
    """Ensure every test in this module runs with an isolated review storage directory."""
    temp_reviews = tmp_path / "reviews"
    temp_reviews.mkdir(parents=True, exist_ok=True)
    set_reviews_dir(temp_reviews)
    yield temp_reviews
    set_reviews_dir(None)


def test_passage_grouping_by_category_and_segment_id():
    """Japan / Russia: 890 raw matches must group into exactly 269 unique passages."""
    data = load_analysis("japan_doj_2026")
    assert data is not None

    active_matches = get_active_matches(
        data,
        category="Russia",
        show_review_only=False,
        include_review_only=False,
    )
    assert len(active_matches) == 890

    passages = group_matches_into_passages(active_matches, category="Russia")
    assert len(passages) == 269

    # Verify each passage key is prefixed by category
    for p in passages:
        assert p["category"] == "Russia"
        assert p["passage_key"] == f"Russia::{p['segment_id']}"
        assert len(p["matches"]) >= 1


def test_no_duplicate_passage_cards():
    """Verify that multiple matches in one segment produce exactly one passage card."""
    data = load_analysis("japan_doj_2026")
    active_matches = get_active_matches(
        data,
        category="Russia",
        show_review_only=False,
        include_review_only=False,
    )
    passages = group_matches_into_passages(active_matches, category="Russia")

    passage_keys = [p["passage_key"] for p in passages]
    assert len(passage_keys) == len(set(passage_keys))

    # Segment p080_s001 has 16 constituent matches; must appear as exactly 1 passage
    p080 = [p for p in passages if p["segment_id"] == "japan_doj_2026_p080_s001"]
    assert len(p080) == 1
    assert len(p080[0]["matches"]) == 16
    assert p080[0]["term_counts"]["Russia"] == 9
    assert p080[0]["term_counts"]["Russia’s"] == 2
    assert p080[0]["term_counts"]["Russian"] == 4
    assert p080[0]["term_counts"]["Russian Federation"] == 1


def test_multi_category_segments_have_distinct_passage_keys():
    """Segments containing matches from multiple categories must have distinct passage keys."""
    data = load_analysis("japan_doj_2026")
    russia_matches = get_active_matches(data, "Russia", False, False)
    china_matches = get_active_matches(data, "China", False, False)

    russia_passages = group_matches_into_passages(russia_matches, "Russia")
    china_passages = group_matches_into_passages(china_matches, "China")

    r_p069 = [p for p in russia_passages if p["segment_id"] == "japan_doj_2026_p069_s001"]
    c_p069 = [p for p in china_passages if p["segment_id"] == "japan_doj_2026_p069_s001"]

    assert len(r_p069) == 1
    assert len(c_p069) == 1
    assert r_p069[0]["passage_key"] == "Russia::japan_doj_2026_p069_s001"
    assert c_p069[0]["passage_key"] == "China::japan_doj_2026_p069_s001"
    assert r_p069[0]["passage_key"] != c_p069[0]["passage_key"]


def test_legacy_unanimous_review_inheritance():
    """When all legacy reviewed matches in a segment share the same status, passage inherits it."""
    matches = [
        {"match_id": "doc_p1_s1_r1", "category": "Russia"},
        {"match_id": "doc_p1_s1_r2", "category": "Russia"},
    ]
    reviews = {
        "doc_p1_s1_r1": {"status": "relevant"},
        "doc_p1_s1_r2": {"status": "relevant"},
    }

    status, diag = resolve_passage_status("Russia", "doc_p1_s1", matches, reviews)
    assert status == "relevant"
    assert diag["source"] == "legacy_unanimous"

    reviews_irr = {
        "doc_p1_s1_r1": {"status": "irrelevant"},
        "doc_p1_s1_r2": {"status": "irrelevant"},
    }
    status_irr, diag_irr = resolve_passage_status("Russia", "doc_p1_s1", matches, reviews_irr)
    assert status_irr == "irrelevant"
    assert diag_irr["source"] == "legacy_unanimous"


def test_legacy_conflicting_reviews_resolve_to_unreviewed():
    """Conflicting legacy match reviews must safely resolve to unreviewed."""
    matches = [
        {"match_id": "doc_p1_s1_r1", "category": "Russia"},
        {"match_id": "doc_p1_s1_r2", "category": "Russia"},
    ]
    conflicting_reviews = {
        "doc_p1_s1_r1": {"status": "relevant"},
        "doc_p1_s1_r2": {"status": "irrelevant"},
    }

    status, diag = resolve_passage_status("Russia", "doc_p1_s1", matches, conflicting_reviews)
    assert status == "unreviewed"
    assert diag["source"] == "legacy_conflict"
    assert set(diag["conflicting_statuses"]) == {"relevant", "irrelevant"}


def test_legacy_review_inheritance_matrix():
    """Verify exact 0/N, partial (1/N, 3/4), N/N unanimous, and N/N conflicting rules."""
    matches = [
        {"match_id": f"m_{i}", "category": "Russia"}
        for i in range(1, 5)  # N = 4 constituent matches
    ]

    # 1. 0/N reviewed: passage must be unreviewed
    reviews_0_of_4 = {}
    st_0, diag_0 = resolve_passage_status("Russia", "seg_x", matches, reviews_0_of_4)
    assert st_0 == "unreviewed"
    assert diag_0["source"] == "default"

    # 2. 1/N reviewed: passage must NOT become relevant, stays unreviewed
    reviews_1_of_4 = {"m_1": {"status": "relevant"}}
    st_1, diag_1 = resolve_passage_status("Russia", "seg_x", matches, reviews_1_of_4)
    assert st_1 == "unreviewed"
    assert diag_1["source"] == "partial_legacy_review"
    assert diag_1["reviewed_matches"] == 1
    assert diag_1["total_constituent_matches"] == 4

    # 3. 3/N reviewed (partial): still stays unreviewed
    reviews_3_of_4 = {
        "m_1": {"status": "relevant"},
        "m_2": {"status": "relevant"},
        "m_3": {"status": "relevant"},
    }
    st_3, diag_3 = resolve_passage_status("Russia", "seg_x", matches, reviews_3_of_4)
    assert st_3 == "unreviewed"
    assert diag_3["source"] == "partial_legacy_review"
    assert diag_3["reviewed_matches"] == 3
    assert diag_3["total_constituent_matches"] == 4

    # 4. N/N unanimous relevant: passage becomes relevant
    reviews_all_rel = {f"m_{i}": {"status": "relevant"} for i in range(1, 5)}
    st_rel, diag_rel = resolve_passage_status("Russia", "seg_x", matches, reviews_all_rel)
    assert st_rel == "relevant"
    assert diag_rel["source"] == "legacy_unanimous"
    assert diag_rel["inherited_from_matches"] == 4

    # 5. N/N unanimous irrelevant: passage becomes irrelevant
    reviews_all_irr = {f"m_{i}": {"status": "irrelevant"} for i in range(1, 5)}
    st_irr, diag_irr = resolve_passage_status("Russia", "seg_x", matches, reviews_all_irr)
    assert st_irr == "irrelevant"
    assert diag_irr["source"] == "legacy_unanimous"
    assert diag_irr["inherited_from_matches"] == 4

    # 6. N/N conflicting: 3 relevant + 1 irrelevant -> unreviewed
    reviews_conflict = {
        "m_1": {"status": "relevant"},
        "m_2": {"status": "relevant"},
        "m_3": {"status": "relevant"},
        "m_4": {"status": "irrelevant"},
    }
    st_conf, diag_conf = resolve_passage_status("Russia", "seg_x", matches, reviews_conflict)
    assert st_conf == "unreviewed"
    assert diag_conf["source"] == "legacy_conflict"
    assert diag_conf["total_matches_reviewed"] == 4


def test_passage_level_decision_precedence():
    """Direct passage-level review takes strict precedence over legacy match records."""
    matches = [
        {"match_id": "doc_p1_s1_r1", "category": "Russia"},
        {"match_id": "doc_p1_s1_r2", "category": "Russia"},
    ]
    # Legacy had conflicting matches, but human set passage to 'relevant'
    reviews = {
        "doc_p1_s1_r1": {"status": "irrelevant"},
        "doc_p1_s1_r2": {"status": "irrelevant"},
        "Russia::doc_p1_s1": {"status": "relevant"},
    }

    status, diag = resolve_passage_status("Russia", "doc_p1_s1", matches, reviews)
    assert status == "relevant"
    assert diag["source"] == "passage"


def test_clear_passage_review_precedence_over_legacy():
    """Clearing a passage review leaves it unreviewed even if legacy matches were relevant."""
    matches = [
        {"match_id": "doc_p1_s1_r1", "category": "Russia"},
    ]
    reviews = {
        "doc_p1_s1_r1": {"status": "relevant"},
        "Russia::doc_p1_s1": {"status": "unreviewed"},
    }

    status, diag = resolve_passage_status("Russia", "doc_p1_s1", matches, reviews)
    assert status == "unreviewed"
    assert diag["source"] == "passage"


def test_filter_semantics_review_only_not_bypassed():
    """Review-required checkbox must not bypass include_review_only filter."""
    data = load_analysis("japan_doj_2026")

    # When include_review_only is False and show_review_only is True:
    # Any match with count_in_raw_baseline == False (e.g. Moscow) must NOT be present
    filtered = get_active_matches(
        data,
        category="Russia",
        show_review_only=True,
        include_review_only=False,
    )

    for m in filtered:
        assert m.get("count_in_raw_baseline", True) is True
        assert m.get("requires_review", False) is True
        assert m.get("pattern_id") != "moscow"

    # When include_review_only is True and show_review_only is True:
    # Moscow review-only matches (which require review) now enter
    filtered_with_review_only = get_active_matches(
        data,
        category="Russia",
        show_review_only=True,
        include_review_only=True,
    )
    moscow_matches = [m for m in filtered_with_review_only if m.get("pattern_id") == "moscow"]
    assert len(moscow_matches) == 13


def test_invalid_status_handling():
    """Malformed or unknown status strings must strictly normalize to unreviewed."""
    assert normalize_status("relevant") == "relevant"
    assert normalize_status("irrelevant") == "irrelevant"
    assert normalize_status("unreviewed") == "unreviewed"
    assert normalize_status("unknown") == "unreviewed"
    assert normalize_status(None) == "unreviewed"
    assert normalize_status(123) == "unreviewed"

    matches = [{"match_id": "m1", "category": "Russia"}]
    reviews = {"Russia::s1": {"status": "corrupt_data"}}
    status, diag = resolve_passage_status("Russia", "s1", matches, reviews)
    assert status == "unreviewed"
    assert diag["source"] == "invalid_status"


def test_review_directory_isolation(tmp_path):
    """Verify that custom reviews directory completely isolates file reads and writes."""
    custom_dir = tmp_path / "custom_reviews"
    set_reviews_dir(custom_dir)

    set_passage_review_status("japan_doj_2026", "Russia", "seg_test", "relevant")

    expected_file = custom_dir / "japan_doj_2026_reviews.json"
    assert expected_file.exists()

    content = json.loads(expected_file.read_text())
    assert "Russia::seg_test" in content["reviews"]
    assert content["reviews"]["Russia::seg_test"]["status"] == "relevant"

    # Real data/reviews must not have been touched
    real_file = Path("data/reviews/japan_doj_2026_reviews.json")
    if real_file.exists():
        real_content = json.loads(real_file.read_text())
        assert "Russia::seg_test" not in real_content.get("reviews", {})


def test_concurrency_safe_passage_review_writes(tmp_path):
    """Concurrent updates across threads must not produce lost updates or corrupt JSON."""
    custom_dir = tmp_path / "concurrent_reviews"
    set_reviews_dir(custom_dir)

    doc_id = "test_doc"
    num_updates = 20

    def write_worker(idx):
        set_passage_review_status(doc_id, "Russia", f"seg_{idx:03d}", "relevant")

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(write_worker, i) for i in range(num_updates)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    data = load_reviews(doc_id)
    reviews = data.get("reviews", {})
    assert len(reviews) == num_updates
    for i in range(num_updates):
        assert f"Russia::seg_{i:03d}" in reviews
        assert reviews[f"Russia::seg_{i:03d}"]["status"] == "relevant"


def test_canonical_analysis_values_unchanged():
    """Verify all 4 canonical analysis match files remain strictly intact."""
    docs = {
        "latvia_sdc_2023": (7108, 151, 71),
        "uk_sdr_2025": (41923, 822, 162),
        "netherlands_dwp_2024": (18465, 148, 130),
        "japan_doj_2026": (324705, 3746, 2956),
    }

    for doc_id, (expected_words, expected_segs, expected_matches) in docs.items():
        data = load_analysis(doc_id)
        assert data is not None
        assert data["document"]["total_analysis_words"] == expected_words
        assert data["document"]["total_segments"] == expected_segs
        assert len(data["matches"]) == expected_matches

    # Japan category baselines
    japan_data = load_analysis("japan_doj_2026")
    summary = japan_data["summary"]

    assert summary["Russia"]["raw_baseline_mentions"] == 890
    assert summary["Russia"]["segment_hits"] == 269
    assert summary["China"]["raw_baseline_mentions"] == 1441
    assert summary["China"]["segment_hits"] == 384
    assert summary["Cyber"]["raw_baseline_mentions"] == 582
    assert summary["Cyber"]["segment_hits"] == 205
