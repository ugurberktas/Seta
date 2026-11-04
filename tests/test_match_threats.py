"""Regression / golden tests for src/match_threats.py.

Synthetic tests exercise matcher rules in isolation. Baseline tests pin the
canonical demo outputs (tracked in data/processed/) for the 3 demo documents.
When the intermediate segment files are available locally, the matcher is also
re-run and compared byte-for-byte with the tracked outputs.
"""

import json
from pathlib import Path

import pytest

import match_threats as mt
from conftest import PROJECT_ROOT

PROCESSED = PROJECT_ROOT / "data" / "processed"
DICTIONARY_PATH = PROJECT_ROOT / "data" / "threat_dictionary.json"

# Exact existing baselines: words / segments / matches.
BASELINES = {
    "latvia_sdc_2023": (7108, 151, 71),
    "uk_sdr_2025": (41923, 822, 162),
    "netherlands_dwp_2024": (18465, 148, 130),
}
# Dictionary order (data/threat_dictionary.json), preserved in summaries.
CATEGORIES = ["Russia", "China", "Hybrid", "Cyber", "Migration"]


def pat(pid, regex, baseline=True, review=False, tier="strong"):
    return {
        "id": pid,
        "regex": regex,
        "tier": tier,
        "count_in_raw_baseline": baseline,
        "requires_review": review,
    }


def seg(text, seg_id="doc_p001_s001", words=None):
    return {
        "segment_id": seg_id,
        "document_id": "doc",
        "country": "Testland",
        "page_number_pdf": 1,
        "page_number_printed": 1,
        "source_line_start": 1,
        "source_line_end": 1,
        "text": text,
        "word_count": words if words is not None else len(text.split()),
    }


def run(segments, categories, tmp_path):
    seg_data = {
        "document": {"document_id": "doc", "country": "Testland", "analysis_scope": "core_body"},
        "segments": segments,
    }
    dict_data = {
        "version": 1,
        "methodology": {"case_insensitive_default": True},
        "categories": categories,
    }
    return mt.match_threats(seg_data, dict_data, Path("segments.json"), tmp_path / "out.json")


# ---------------------------------------------------------------------------
# Overlap resolution
# ---------------------------------------------------------------------------

def test_spans_overlap_is_half_open():
    assert mt.spans_overlap((0, 5), (4, 8))
    assert not mt.spans_overlap((0, 5), (5, 8))  # touching spans do not overlap
    assert mt.spans_overlap((2, 3), (0, 10))


def _cand(start, end, order):
    return {"char_start": start, "char_end": end, "pattern_order": order}


def test_resolve_overlaps_prefers_longest_match():
    short, long_ = _cand(0, 5, 0), _cand(0, 12, 1)
    assert mt.resolve_overlaps([short, long_]) == [long_]


def test_resolve_overlaps_ties_break_on_start_then_pattern_order():
    a, b = _cand(0, 5, 1), _cand(3, 8, 0)  # same length, overlapping -> earlier start wins
    assert mt.resolve_overlaps([b, a]) == [a]
    c, d = _cand(0, 5, 2), _cand(0, 5, 1)  # identical span -> lower pattern order wins
    assert mt.resolve_overlaps([c, d]) == [d]


def test_resolve_overlaps_returns_text_order_and_keeps_disjoint():
    late, early = _cand(20, 25, 0), _cand(0, 5, 1)
    assert mt.resolve_overlaps([late, early]) == [early, late]
    assert mt.resolve_overlaps([]) == []


def test_longest_pattern_wins_over_embedded_shorter_pattern(tmp_path):
    cats = {"Cyber": {"patterns": [pat("cyber", r"\bcyber\b"), pat("cyber_defence", r"\bcyber\s+defence\b")]}}
    result = run([seg("Our cyber defence is strong and cyber matters.")], cats, tmp_path)
    got = [(m["pattern_id"], m["matched_text"]) for m in result["matches"]]
    assert got == [("cyber_defence", "cyber defence"), ("cyber", "cyber")]


def test_real_dictionary_cyber_security_counts_once():
    cfg = json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))["categories"]["Cyber"]
    matches = mt.match_category_in_segment(seg("Cyber security and cybersecurity."), "Cyber", cfg, True)
    assert [(m["pattern_id"], m["matched_text"]) for m in matches] == [
        ("cyber_security", "Cyber security"),
        ("cybersecurity", "cybersecurity"),
    ]


# ---------------------------------------------------------------------------
# Exclusions
# ---------------------------------------------------------------------------

def test_exclusion_pattern_suppresses_overlapping_matches():
    cfg = {"exclude_patterns": [r"\bhybrid\s+working\b"], "patterns": [pat("hybrid", r"\bhybrid\b")]}
    assert mt.match_category_in_segment(seg("Hybrid working is common."), "Hybrid", cfg, True) == []
    kept = mt.match_category_in_segment(seg("Hybrid working and hybrid threats."), "Hybrid", cfg, True)
    assert [m["matched_text"] for m in kept] == ["hybrid"]
    assert kept[0]["char_start"] == 19


@pytest.mark.parametrize(
    "category,text,expected",
    [
        ("Hybrid", "hybrid working, hybrid workforce and hybrid carrier", 0),
        ("Hybrid", "hybrid warfare", 1),
        ("Migration", "data migration and cloud migration", 0),
        ("Migration", "irregular migration and refugees", 2),
    ],
)
def test_real_dictionary_exclusions(category, text, expected):
    cfg = json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))["categories"][category]
    assert len(mt.match_category_in_segment(seg(text), category, cfg, True)) == expected


def test_case_insensitivity_flag():
    cfg = {"patterns": [pat("russia", r"\brussia\b")]}
    assert len(mt.match_category_in_segment(seg("RUSSIA and Russia"), "Russia", cfg, True)) == 2
    assert len(mt.match_category_in_segment(seg("RUSSIA and Russia"), "Russia", cfg, False)) == 0


def test_empty_text_yields_no_matches():
    assert mt.match_category_in_segment(seg(""), "Russia", {"patterns": [pat("r", r"russia")]}, True) == []


# ---------------------------------------------------------------------------
# Review-only / review-required behaviour and frequency maths
# ---------------------------------------------------------------------------

def test_review_only_matches_are_detected_but_excluded_from_frequency(tmp_path):
    cats = {
        "Russia": {
            "patterns": [
                pat("russia", r"\brussia\b"),
                pat("moscow", r"\bmoscow\b", baseline=False, review=True, tier="context_sensitive"),
            ]
        }
    }
    result = run([seg("Russia and Moscow", words=1000)], cats, tmp_path)
    summary = result["summary"]["Russia"]
    assert summary["detected_mentions"] == 2
    assert summary["raw_baseline_mentions"] == 1
    assert summary["review_only_mentions"] == 1
    assert summary["review_required_mentions"] == 1
    assert summary["segment_hits"] == 1
    assert summary["frequency_per_1000_words"] == 1.0  # review-only match is not counted
    moscow = [m for m in result["matches"] if m["pattern_id"] == "moscow"][0]
    assert moscow["count_in_raw_baseline"] is False and moscow["requires_review"] is True


def test_review_only_segment_does_not_count_as_segment_hit(tmp_path):
    cats = {"Russia": {"patterns": [pat("moscow", r"\bmoscow\b", baseline=False, review=True)]}}
    result = run([seg("Moscow only")], cats, tmp_path)
    assert result["summary"]["Russia"]["segment_hits"] == 0
    assert result["summary"]["Russia"]["detected_mentions"] == 1


def test_frequency_normalised_per_1000_words_and_ranking_is_deterministic(tmp_path):
    cats = {
        "Beta": {"patterns": [pat("b", r"\bb\b")]},
        "Alpha": {"patterns": [pat("a", r"\ba\b")]},
        "Gamma": {"patterns": [pat("g", r"\bg\b")]},
    }
    segments = [seg("a b", "s1", words=500), seg("a b g", "s2", words=500)]
    result = run(segments, cats, tmp_path)
    assert result["document"]["total_analysis_words"] == 1000
    assert result["summary"]["Alpha"]["frequency_per_1000_words"] == 2.0
    # Ties are broken alphabetically (Alpha before Beta), lowest frequency last.
    assert [r["category"] for r in result["ranking_by_frequency"]] == ["Alpha", "Beta", "Gamma"]


def test_match_ids_and_traceability_fields(tmp_path):
    cats = {"Cyber": {"patterns": [pat("cyber", r"\bcyber\b")]}}
    result = run([seg("cyber cyber", "doc_p001_s007")], cats, tmp_path)
    assert [m["match_id"] for m in result["matches"]] == ["doc_p001_s007_cyber_001", "doc_p001_s007_cyber_002"]
    first = result["matches"][0]
    assert (first["page_number_pdf"], first["segment_id"], first["char_start"], first["char_end"]) == (
        1, "doc_p001_s007", 0, 5,
    )
    assert first["segment_text"] == "cyber cyber"


def test_zero_words_exits(tmp_path):
    with pytest.raises(SystemExit):
        run([seg("x", words=0)], {"Cyber": {"patterns": [pat("c", r"x")]}}, tmp_path)


def test_matching_is_deterministic(tmp_path):
    cfg = json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))
    segments = [seg("Russia, hybrid threats and cyber security; Moscow; migration.", "s1")]
    seg_data = {"document": {"document_id": "doc"}, "segments": segments}
    a = mt.match_threats(seg_data, cfg, Path("s.json"), tmp_path / "a.json")
    b = mt.match_threats(seg_data, cfg, Path("s.json"), tmp_path / "b.json")
    assert a == b


# ---------------------------------------------------------------------------
# Canonical demo baselines
# ---------------------------------------------------------------------------

def load_matches(document_id):
    path = PROCESSED / f"{document_id}_core_body_threat_matches.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("document_id,expected", BASELINES.items())
def test_document_baseline_totals(document_id, expected):
    words, segments, matches = expected
    data = load_matches(document_id)
    assert data["document"]["document_id"] == document_id
    assert data["document"]["total_analysis_words"] == words
    assert data["document"]["total_segments"] == segments
    assert len(data["matches"]) == matches


@pytest.mark.parametrize("document_id", BASELINES)
def test_baseline_summary_is_internally_consistent(document_id):
    data = load_matches(document_id)
    words = data["document"]["total_analysis_words"]
    assert list(data["summary"]) == CATEGORIES
    assert sum(s["detected_mentions"] for s in data["summary"].values()) == len(data["matches"])
    for category, s in data["summary"].items():
        in_category = [m for m in data["matches"] if m["category"] == category]
        assert s["detected_mentions"] == len(in_category)
        assert s["raw_baseline_mentions"] == sum(m["count_in_raw_baseline"] for m in in_category)
        assert s["review_only_mentions"] == s["detected_mentions"] - s["raw_baseline_mentions"]
        assert s["review_required_mentions"] == sum(m["requires_review"] for m in in_category)
        assert s["frequency_per_1000_words"] == round(s["raw_baseline_mentions"] / words * 1000, 6)
    assert len({m["match_id"] for m in data["matches"]}) == len(data["matches"])


def test_russia_frequency_ordering_latvia_netherlands_uk():
    freq = {d: load_matches(d)["summary"]["Russia"]["frequency_per_1000_words"] for d in BASELINES}
    assert freq["latvia_sdc_2023"] > freq["netherlands_dwp_2024"] > freq["uk_sdr_2025"]


def test_uk_has_single_review_only_russia_match():
    data = load_matches("uk_sdr_2025")
    review_only = [m for m in data["matches"] if not m["count_in_raw_baseline"]]
    assert [(m["category"], m["pattern_id"]) for m in review_only] == [("Russia", "moscow")]


@pytest.mark.parametrize("document_id", BASELINES)
def test_rematching_local_segments_reproduces_tracked_output(document_id, tmp_path):
    segments_path = PROCESSED / f"{document_id}_core_body_segments.json"
    if not segments_path.exists():
        pytest.skip("intermediate segments file is not tracked; only available after local processing")
    segments = json.loads(segments_path.read_text(encoding="utf-8"))
    dictionary = json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))
    result = mt.match_threats(segments, dictionary, segments_path, tmp_path / "out.json")
    tracked = load_matches(document_id)
    assert result["matches"] == tracked["matches"]
    assert result["summary"] == tracked["summary"]
    assert result["ranking_by_frequency"] == tracked["ranking_by_frequency"]


# ---------------------------------------------------------------------------
# Portability of canonical outputs
# ---------------------------------------------------------------------------

ABSOLUTE_PATH_PATTERNS = [
    r"/Users/",
    r"/home/",
    r"[A-Za-z]:\\",       # Windows drive path, e.g. C:\...
    r"[A-Za-z]:\\\\",     # same, as escaped inside JSON strings
    r"(?:^|[\s\"'\(])[A-Za-z]:/",  # Windows drive path with forward slashes, e.g. C:/
]


@pytest.mark.parametrize("document_id", BASELINES)
def test_canonical_outputs_contain_no_machine_specific_paths(document_id):
    import re

    path = PROCESSED / f"{document_id}_core_body_threat_matches.json"
    raw = path.read_text(encoding="utf-8")
    for pattern in ABSOLUTE_PATH_PATTERNS:
        assert not re.search(pattern, raw), f"{path.name} contains a machine-specific path ({pattern})"
    source = json.loads(raw)["document"]["source_segments_file"]
    assert source == f"data/processed/{document_id}_core_body_segments.json"


def test_portable_path_is_repo_relative_and_never_absolute(tmp_path):
    inside = PROJECT_ROOT / "data" / "processed" / "x_segments.json"
    assert mt.portable_path(inside) == "data/processed/x_segments.json"
    assert mt.portable_path(Path("data/processed/x_segments.json")) == "data/processed/x_segments.json"
    # Paths outside the repo are kept as given, not rewritten to a repo location.
    assert mt.portable_path(tmp_path / "s.json") == (tmp_path / "s.json").as_posix()


# ---------------------------------------------------------------------------
# Japan-specific regression tests
# ---------------------------------------------------------------------------

JAPAN_BASELINE = {
    "document_id": "japan_doj_2026",
    "total_analysis_words": 324705,
    "total_segments": 3746,
    "total_matches": 2956,
    "raw_counts": {
        "China": 1441,
        "Russia": 890,
        "Cyber": 582,
        "Hybrid": 24,
        "Migration": 6,
    },
    "frequencies": {
        "China": 4.437874,
        "Russia": 2.740949,
        "Cyber": 1.792396,
        "Hybrid": 0.073913,
        "Migration": 0.018478,
    },
}


def test_japan_canonical_threat_matches_baseline():
    import re

    path = PROCESSED / "japan_doj_2026_core_body_threat_matches.json"
    if not path.exists():
        pytest.skip("Japan threat matches canonical file not found")
    data = json.loads(path.read_text(encoding="utf-8"))

    doc = data["document"]
    assert doc["document_id"] == JAPAN_BASELINE["document_id"]
    assert doc["total_analysis_words"] == JAPAN_BASELINE["total_analysis_words"]
    assert doc["total_segments"] == JAPAN_BASELINE["total_segments"]
    assert doc["source_segments_file"] == "data/processed/japan_doj_2026_core_body_segments.json"

    assert len(data["matches"]) == JAPAN_BASELINE["total_matches"]

    for cat, expected_raw in JAPAN_BASELINE["raw_counts"].items():
        assert data["summary"][cat]["raw_baseline_mentions"] == expected_raw
        assert data["summary"][cat]["frequency_per_1000_words"] == JAPAN_BASELINE["frequencies"][cat]

    # Verify no machine-specific absolute path
    raw_text = path.read_text(encoding="utf-8")
    for pattern in ABSOLUTE_PATH_PATTERNS:
        assert not re.search(pattern, raw_text), f"Japan matches file contains a machine-specific path ({pattern})"


def test_rematching_japan_segments_reproduces_tracked_output(tmp_path):
    segments_path = PROCESSED / "japan_doj_2026_core_body_segments.json"
    matches_path = PROCESSED / "japan_doj_2026_core_body_threat_matches.json"
    if not (segments_path.exists() and matches_path.exists()):
        pytest.skip("Japan segments or matches file not found")
    segments = json.loads(segments_path.read_text(encoding="utf-8"))
    dictionary = json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))
    result = mt.match_threats(segments, dictionary, segments_path, tmp_path / "out.json")
    tracked = json.loads(matches_path.read_text(encoding="utf-8"))
    assert result["matches"] == tracked["matches"]
    assert result["summary"] == tracked["summary"]
    assert result["ranking_by_frequency"] == tracked["ranking_by_frequency"]

