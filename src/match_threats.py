#!/usr/bin/env python3
"""
src/match_threats.py

Matches threat patterns from data/threat_dictionary.json against segmented
source text passages in a deterministic and traceable manner.

Part of Sprint 2 (Adım 2C).
"""

import argparse
import json
import re
import sys
from pathlib import Path


def load_json(file_path: Path) -> dict:
    """Load JSON file."""
    if not file_path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def portable_path(path: Path) -> str:
    """Return a stable, machine-independent path string for output metadata.

    Paths inside the repository are emitted relative to the repo root with
    forward slashes; other paths are emitted as given (never resolved to an
    absolute machine-specific location).
    """
    path = Path(path)
    if path.is_absolute():
        try:
            return path.relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            return path.as_posix()
    return path.as_posix()


def spans_overlap(span1: tuple[int, int], span2: tuple[int, int]) -> bool:
    """Check if two half-open spans [s1, e1) and [s2, e2) overlap."""
    return max(span1[0], span2[0]) < min(span1[1], span2[1])


def resolve_overlaps(candidates: list[dict]) -> list[dict]:
    """
    Applies longest_non_overlapping_match policy.
    Sorts candidates by:
      1. Length descending (-length)
      2. Start position ascending (start)
      3. Pattern order ascending (order)
    Greedily selects non-overlapping candidates, then sorts winners by char_start.
    """
    if not candidates:
        return []

    sorted_candidates = sorted(
        candidates,
        key=lambda c: (
            -(c["char_end"] - c["char_start"]),
            c["char_start"],
            c["pattern_order"]
        )
    )

    selected = []
    for cand in sorted_candidates:
        cand_span = (cand["char_start"], cand["char_end"])
        # Check collision with already selected
        collision = any(
            spans_overlap(cand_span, (s["char_start"], s["char_end"]))
            for s in selected
        )
        if not collision:
            selected.append(cand)

    # Return ordered by appearance in text
    return sorted(selected, key=lambda c: c["char_start"])


def match_category_in_segment(
    segment: dict,
    category_name: str,
    category_config: dict,
    case_insensitive: bool
) -> list[dict]:
    """
    Finds and resolves matches for a single category within a single segment.
    """
    text = segment.get("text", "")
    if not text:
        return []

    flags = re.IGNORECASE if case_insensitive else 0

    # 1. Collect exclusion spans
    exclude_spans = []
    for exc_pattern in category_config.get("exclude_patterns", []):
        for m in re.finditer(exc_pattern, text, flags):
            exclude_spans.append(m.span())

    # 2. Collect candidates for each pattern
    raw_candidates = []
    patterns = category_config.get("patterns", [])
    for p_idx, pat in enumerate(patterns):
        regex = pat["regex"]
        for m in re.finditer(regex, text, flags):
            m_span = m.span()

            # Skip if overlaps with any exclusion span
            is_excluded = any(spans_overlap(m_span, exc_span) for exc_span in exclude_spans)
            if is_excluded:
                continue

            raw_candidates.append({
                "char_start": m_span[0],
                "char_end": m_span[1],
                "matched_text": text[m_span[0]:m_span[1]],
                "pattern_order": p_idx,
                "pattern_id": pat["id"],
                "tier": pat["tier"],
                "count_in_raw_baseline": pat["count_in_raw_baseline"],
                "requires_review": pat["requires_review"],
                "pattern_note": pat.get("note", "")
            })

    # 3. Resolve overlaps
    resolved = resolve_overlaps(raw_candidates)

    # 4. Build formal match records
    matches = []
    cat_slug = category_name.lower().replace(" ", "_")
    for idx, item in enumerate(resolved, start=1):
        match_id = f"{segment['segment_id']}_{cat_slug}_{idx:03d}"
        matches.append({
            "match_id": match_id,
            "document_id": segment["document_id"],
            "country": segment["country"],
            "category": category_name,
            "pattern_id": item["pattern_id"],
            "tier": item["tier"],
            "count_in_raw_baseline": item["count_in_raw_baseline"],
            "requires_review": item["requires_review"],
            "segment_id": segment["segment_id"],
            "page_number_pdf": segment["page_number_pdf"],
            "page_number_printed": segment.get("page_number_printed"),
            "source_line_start": segment.get("source_line_start"),
            "source_line_end": segment.get("source_line_end"),
            "char_start": item["char_start"],
            "char_end": item["char_end"],
            "matched_text": item["matched_text"],
            "segment_text": text
        })

    return matches


def match_threats(
    segments_data: dict,
    dict_data: dict,
    input_segments_path: Path,
    output_matches_path: Path
) -> dict:
    """
    Main matching logic across all segments and categories.
    """
    methodology = dict_data.get("methodology", {})
    case_insensitive = methodology.get("case_insensitive_default", True)
    categories = dict_data.get("categories", {})

    all_matches = []
    # Initialize summary structure dynamically from dictionary
    summary = {}
    for cat_name in categories.keys():
        summary[cat_name] = {
            "detected_mentions": 0,
            "raw_baseline_mentions": 0,
            "review_required_mentions": 0,
            "review_only_mentions": 0,
            "segment_hits": 0,
            "_hit_segment_ids": set()
        }

    segments = segments_data.get("segments", [])

    for seg in segments:
        for cat_name, cat_config in categories.items():
            cat_matches = match_category_in_segment(seg, cat_name, cat_config, case_insensitive)
            if cat_matches:
                all_matches.extend(cat_matches)
                cat_summary = summary[cat_name]
                for m in cat_matches:
                    cat_summary["detected_mentions"] += 1
                    if m["count_in_raw_baseline"]:
                        cat_summary["raw_baseline_mentions"] += 1
                        cat_summary["_hit_segment_ids"].add(m["segment_id"])
                    else:
                        cat_summary["review_only_mentions"] += 1

                    if m["requires_review"]:
                        cat_summary["review_required_mentions"] += 1

    # Finalize segment_hits count and remove internal set
    for cat_name, cat_summary in summary.items():
        cat_summary["segment_hits"] = len(cat_summary["_hit_segment_ids"])
        del cat_summary["_hit_segment_ids"]

    # Calculate total words from segments or document metadata
    doc_meta = segments_data.get("document", {})
    total_words = sum(s.get("word_count", 0) for s in segments)

    if total_words <= 0:
        print("Error: total_analysis_words must be greater than zero", file=sys.stderr)
        sys.exit(1)

    # Compute frequency_per_1000_words for each category
    ranking_list = []
    for cat_name, cat_summary in summary.items():
        raw_baseline = cat_summary["raw_baseline_mentions"]
        freq = round((raw_baseline / total_words) * 1000, 6)
        cat_summary["frequency_per_1000_words"] = freq
        ranking_list.append({
            "category": cat_name,
            "frequency_per_1000_words": freq
        })

    # Sort ranking deterministically: frequency descending, then category name ascending
    ranking_list.sort(key=lambda item: (-item["frequency_per_1000_words"], item["category"]))

    result = {
        "document": {
            "document_id": doc_meta.get("document_id"),
            "country": doc_meta.get("country"),
            "analysis_scope": doc_meta.get("analysis_scope"),
            "source_segments_file": portable_path(input_segments_path),
            "dictionary_version": dict_data.get("version", 1),
            "total_analysis_words": total_words,
            "total_segments": len(segments)
        },
        "ranking_by_frequency": ranking_list,
        "summary": summary,
        "matches": all_matches
    }

    output_matches_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_matches_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def main():
    parser = argparse.ArgumentParser(description="Match threat patterns against segmented text passages.")
    parser.add_argument("--document-id", required=True, help="Document ID (e.g. latvia_sdc_2023)")
    parser.add_argument("--scope", default="core_body", help="Analysis scope (default: core_body)")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    dict_file = project_root / "data" / "threat_dictionary.json"
    segments_file = project_root / "data" / "processed" / f"{args.document_id}_{args.scope}_segments.json"

    dict_data = load_json(dict_file)
    segments_data = load_json(segments_file)

    output_file = project_root / "data" / "processed" / f"{args.document_id}_{args.scope}_threat_matches.json"

    result = match_threats(segments_data, dict_data, segments_file, output_file)

    doc_info = result["document"]
    print("Document:", doc_info["document_id"])
    print("Scope:", doc_info["analysis_scope"])
    print("Total segments:", doc_info["total_segments"])
    print("Total analysis words:", doc_info["total_analysis_words"])
    print("Total matches found:", len(result["matches"]))
    print("Ranking by frequency (per 1000 words):")
    for rank_idx, item in enumerate(result["ranking_by_frequency"], start=1):
        print(f"  {rank_idx}. {item['category']}: {item['frequency_per_1000_words']}")
    print("Output:", output_file)


if __name__ == "__main__":
    main()
