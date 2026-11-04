"""Regression / golden tests for src/segment.py.

Synthetic tests cover boundary detection and Netherlands-specific handling.
When local extraction output (data/processed/*_core_body.json) exists, full
re-segmentation is compared with the stored segments and the pinned baselines.
"""

import json

import pytest

import segment as sg
from conftest import PROJECT_ROOT

PROCESSED = PROJECT_ROOT / "data" / "processed"
NL = sg.NETHERLANDS_DOCUMENT_ID

BASELINES = {  # words / segments
    "latvia_sdc_2023": (7108, 151),
    "uk_sdr_2025": (41923, 822),
    "netherlands_dwp_2024": (18465, 148),
}


def page(text, document_id="doc", page_number=1):
    return {
        "document_id": document_id,
        "country": "Testland",
        "page_number_pdf": page_number,
        "page_number_printed": page_number,
        "cleaned_text": text,
        "include_in_analysis": True,
    }


# ---------------------------------------------------------------------------
# Generic boundary detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "line,expected",
    [
        ("STRATEGIC CONTEXT", "heading"),
        ("Recommendations:", "heading"),
        ("1.", "numbered_paragraph"),
        ("59. The MOD will act.", "numbered_paragraph"),
        ("131 The defence sector grows.", "numbered_paragraph"),
        ("• Item one", "bullet_item"),
        ("- Item two", "bullet_item"),
        ("* Item three", "bullet_item"),
        ("Plain prose continues here.", None),
        ("", None),
    ],
)
def test_detect_boundary_type(line, expected):
    assert sg.detect_boundary_type(line) == expected


def test_is_heading_is_conservative():
    assert sg.is_heading("UK") is False           # fewer than 4 letters
    assert sg.is_heading("NATO") is True
    assert sg.is_heading("A VERY " + "LONG " * 12 + "HEADING") is False  # more than 12 words
    assert sg.is_heading("Mixed Case Title") is False


def test_segments_never_merge_across_pages_and_ids_are_deterministic():
    first = sg.segment_page(page("Para one\ncontinues.", page_number=3))
    second = sg.segment_page(page("Para two.", page_number=4))
    assert [s["segment_id"] for s in first] == ["doc_p003_s001"]
    assert [s["segment_id"] for s in second] == ["doc_p004_s001"]
    assert first[0]["text"] == "Para one continues."
    assert (first[0]["source_line_start"], first[0]["source_line_end"]) == (1, 2)


def test_segment_page_splits_types_and_tracks_lines():
    text = "Some prose\nmore prose.\n1. First numbered.\n• bullet a\n• bullet b\nINTRODUCTION"
    segs = sg.segment_page(page(text))
    assert [s["segment_type"] for s in segs] == [
        "paragraph", "numbered_paragraph", "bullet_item", "bullet_item", "heading"
    ]
    assert segs[0]["text"] == "Some prose more prose."
    assert segs[0]["word_count"] == 4
    assert [(s["source_line_start"], s["source_line_end"]) for s in segs] == [(1, 2), (3, 3), (4, 4), (5, 5), (6, 6)]
    assert [s["segment_index"] for s in segs] == [1, 2, 3, 4, 5]


def test_unbroken_lines_after_a_heading_stay_in_the_heading_segment():
    # Characterisation of current behaviour that the stored baselines depend on:
    # a heading segment absorbs following lines until the next boundary.
    segs = sg.segment_page(page("INTRODUCTION\nSome prose\nmore prose."))
    assert [(s["segment_type"], s["text"]) for s in segs] == [
        ("heading", "INTRODUCTION Some prose more prose.")
    ]


def test_empty_page_yields_no_segments():
    assert sg.segment_page(page("")) == []


def test_segment_document_skips_excluded_pages_and_counts_types(tmp_path):
    doc = {
        "document": {"document_id": "doc", "country": "Testland", "analysis_scope": "core_body"},
        "pages": [page("1. One."), {**page("2. Two.", page_number=2), "include_in_analysis": False}],
    }
    result = sg.segment_document(doc, tmp_path / "in.json", tmp_path / "out.json")
    assert result["document"]["total_segments"] == 1
    assert result["document"]["segments_by_type"]["numbered_paragraph"] == 1
    assert json.loads((tmp_path / "out.json").read_text(encoding="utf-8")) == result


# ---------------------------------------------------------------------------
# Netherlands-specific handling
# ---------------------------------------------------------------------------

def test_netherlands_decimal_headings():
    assert sg.is_netherlands_decimal_heading("4.2")
    assert sg.is_netherlands_decimal_heading("4.2 Strong Armed Forces")
    assert sg.is_netherlands_decimal_heading("1.2.3 Detail")
    assert not sg.is_netherlands_decimal_heading("4. Not decimal")
    assert not sg.is_netherlands_decimal_heading("4.2 " + "word " * 15)


def test_netherlands_decimal_heading_only_applies_to_netherlands():
    assert sg.detect_boundary_type("4.2 Strong forces", NL) == "heading"
    assert sg.detect_boundary_type("4.2 Strong forces", "doc") is None


def test_netherlands_bullet_marker_only_applies_to_netherlands():
    line = "> \x07 Invest in capabilities"
    assert sg.detect_boundary_type(line, NL) == "bullet_item"
    assert sg.detect_boundary_type(line, "doc") is None


def test_netherlands_title_case_heading_requires_context():
    prev = "The previous sentence ends here."
    nxt = "The next paragraph starts capitalised."
    assert sg.is_netherlands_title_case_heading("Defence Industry", prev, nxt)
    # Wrapped prose (previous line is unfinished) must not become a heading.
    assert not sg.is_netherlands_title_case_heading("Defence Industry", "ends mid", nxt)
    # Lines that end like sentences, contain prose verbs, or precede lowercase text are rejected.
    assert not sg.is_netherlands_title_case_heading("Defence Industry.", prev, nxt)
    assert not sg.is_netherlands_title_case_heading("Defence Industry Will Grow", prev, nxt)
    assert not sg.is_netherlands_title_case_heading("Defence Industry", prev, "lower case next")
    assert not sg.is_netherlands_title_case_heading("Defence Industry", prev, None)


def test_netherlands_title_case_heading_only_applies_to_netherlands():
    prev, nxt = "Previous sentence.", "Next sentence."
    assert sg.detect_boundary_type("Defence Industry", NL, prev, nxt) == "heading"
    assert sg.detect_boundary_type("Defence Industry", "doc", prev, nxt) is None


def test_netherlands_small_segments_are_not_split():
    segs = sg.segment_page(page("4.1 Title\nShort paragraph text.\n4.2 Next\nMore text.", NL))
    assert [(s["segment_type"], s["text"]) for s in segs] == [
        ("heading", "4.1 Title Short paragraph text."),
        ("heading", "4.2 Next More text."),
    ]


def _long_paragraph_lines(words_per_line=10, lines=100):
    """A single paragraph of 1,000 words (> NETHERLANDS_MAX_SEGMENT_WORDS), no boundaries."""
    return [
        " ".join(f"w{i}_{j}" for j in range(words_per_line - 1)) + f" end{i}."
        for i in range(lines)
    ]


def test_netherlands_oversized_segment_is_split_deterministically():
    text = "\n".join(_long_paragraph_lines())
    segs = sg.segment_page(page(text, NL))
    assert len(segs) > 1
    assert sum(s["word_count"] for s in segs) == 1000  # no words lost or duplicated
    assert all(s["word_count"] <= sg.NETHERLANDS_FALLBACK_PREFERRED_MAX_WORDS for s in segs)
    assert all(s["segment_type"] == "paragraph" for s in segs)
    # Contiguous, ordered, non-overlapping line coverage with sequential ids.
    assert segs[0]["source_line_start"] == 1 and segs[-1]["source_line_end"] == 100
    for prev, cur in zip(segs, segs[1:]):
        assert cur["source_line_start"] == prev["source_line_end"] + 1
    assert [s["segment_id"] for s in segs] == [f"{NL}_p001_s{i:03d}" for i in range(1, len(segs) + 1)]
    assert segs == sg.segment_page(page(text, NL))  # deterministic


def test_oversized_segment_is_not_split_for_other_documents():
    text = "\n".join(_long_paragraph_lines())
    segs = sg.segment_page(page(text, "uk_sdr_2025"))
    assert len(segs) == 1 and segs[0]["word_count"] == 1000


def test_netherlands_split_changes_heading_type_to_paragraph():
    segment = {
        "segment_type": "heading", "source_line_start": 1, "source_line_end": 100,
        "word_count": 1000, "text": "x", "char_count": 1,
    }
    parts = sg.split_netherlands_oversized_segment(segment, _long_paragraph_lines())
    assert len(parts) > 1 and {p["segment_type"] for p in parts} == {"paragraph"}


# ---------------------------------------------------------------------------
# Golden checks against real processed data (skipped without local extraction output)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("document_id,expected", BASELINES.items())
def test_resegmentation_reproduces_stored_segments_and_baselines(document_id, expected, tmp_path):
    extraction = PROCESSED / f"{document_id}_core_body.json"
    stored = PROCESSED / f"{document_id}_core_body_segments.json"
    if not (extraction.exists() and stored.exists()):
        pytest.skip("extraction/segment intermediates are not tracked; only available after local processing")
    doc = json.loads(extraction.read_text(encoding="utf-8"))
    result = sg.segment_document(doc, extraction, tmp_path / "segments.json")
    words, segments = expected
    assert result["document"]["total_segments"] == segments
    assert sum(s["word_count"] for s in result["segments"]) == words
    assert result["segments"] == json.loads(stored.read_text(encoding="utf-8"))["segments"]


def test_netherlands_real_segments_respect_max_words():
    stored = PROCESSED / f"{NL}_core_body_segments.json"
    if not stored.exists():
        pytest.skip("segments file is not tracked")
    segments = json.loads(stored.read_text(encoding="utf-8"))["segments"]
    assert max(s["word_count"] for s in segments) <= sg.NETHERLANDS_MAX_SEGMENT_WORDS
