#!/usr/bin/env python3
"""
src/segment.py

Segments cleaned page-level text into traceable, granular source passages
(paragraphs, headings, bullet items, numbered paragraphs) for analysis.

Part of Sprint 1 (Adım 4B).
"""

import argparse
import json
import re
import sys
from pathlib import Path


NETHERLANDS_DOCUMENT_ID = "netherlands_dwp_2024"
NETHERLANDS_MAX_SEGMENT_WORDS = 450
NETHERLANDS_FALLBACK_TARGET_WORDS = 300
NETHERLANDS_FALLBACK_PREFERRED_MAX_WORDS = 400

JAPAN_DOCUMENT_ID = "japan_doj_2026"
JAPAN_MAX_SEGMENT_WORDS = 400
JAPAN_TARGET_WORDS = 280
JAPAN_PREFERRED_MAX_WORDS = 380


def load_json(file_path: Path) -> dict:
    """Load JSON file."""
    if not file_path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_heading(line: str) -> bool:
    """
    Determines if a line is a heading conservatively:
    - Special exact/prefix match: Recommendations:
    - All-caps check:
      - At least 4 alphabetic characters
      - At most 12 words
      - Letters must all be uppercase
    """
    stripped = line.strip()
    if not stripped:
        return False

    # Specific known heading patterns
    if re.match(r"^recommendations\s*:?$", stripped, re.IGNORECASE):
        return True

    words = stripped.split()
    if len(words) > 12:
        return False

    letters = [c for c in stripped if c.isalpha()]
    if len(letters) < 4:
        return False

    # Check if all letters are uppercase
    if all(c.isupper() for c in letters):
        # Disallow purely numeric/punct lines
        return True

    return False


def is_netherlands_decimal_heading(line: str) -> bool:
    """Detect short Netherlands section headings such as '4.2' or '4.2 Title'."""
    stripped = line.strip()
    if len(stripped.split()) > 15:
        return False
    return bool(re.match(r"^\d+\.\d+(?:\.\d+)?(?:\s+\S.*)?$", stripped))


def is_netherlands_title_case_heading(
    line: str,
    previous_line: str | None = None,
    next_line: str | None = None,
) -> bool:
    """Detect conservative short sentence-case headings in the Netherlands source."""
    stripped = line.strip()
    words = stripped.split()
    if not stripped or len(words) > 8 or len(stripped) > 80:
        return False
    if stripped.endswith((".", "!", "?", ":", ";", ",")):
        return False
    if re.match(r"^(?:[•\-*]|>\s*\x07?)\s*", stripped):
        return False
    if re.match(r"^\d", stripped):
        return False

    alpha_words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[-'][A-Za-zÀ-ÖØ-öø-ÿ]+)*", stripped)
    if not alpha_words:
        return False

    # Wrapped prose commonly contains these verbs; rejecting them prevents
    # ordinary short source lines from becoming headings.
    prose_verbs = {
        "am", "are", "be", "been", "being", "can", "could", "did", "do",
        "does", "has", "have", "intends", "is", "must", "need", "needs",
        "should", "was", "were", "will", "would",
    }
    if any(word.lower() in prose_verbs for word in alpha_words):
        return False

    insignificant_words = {
        "a", "an", "and", "at", "by", "for", "from", "in", "of", "on",
        "or", "the", "to", "with",
    }
    significant_words = [
        word for word in alpha_words if word.lower() not in insignificant_words
    ]
    if not significant_words:
        return False

    if not significant_words[0][0].isupper():
        return False

    if previous_line is not None:
        previous = previous_line.strip()
        previous_ends_sentence = bool(re.search(r"[.!?][\"')\]]*\d*$", previous))
        if not previous_ends_sentence and not is_netherlands_decimal_heading(previous):
            return False

    if next_line is None or not re.match(r"^[\"'(]*[A-ZÀ-ÖØ-Þ]", next_line.strip()):
        return False

    capitalized = sum(word[0].isupper() for word in significant_words)
    return capitalized * 2 >= len(significant_words)


def detect_boundary_type(
    line: str,
    document_id: str | None = None,
    previous_line: str | None = None,
    next_line: str | None = None,
) -> str | None:
    """
    Detects if a non-empty line starts a new segment boundary.
    Returns: 'heading', 'numbered_paragraph', 'bullet_item', or None.
    """
    stripped = line.strip()
    if not stripped:
        return None

    # 1. Heading check
    if is_heading(stripped):
        return "heading"

    if document_id == NETHERLANDS_DOCUMENT_ID:
        if is_netherlands_decimal_heading(stripped):
            return "heading"
        if is_netherlands_title_case_heading(stripped, previous_line, next_line):
            return "heading"
        if re.match(r"^>\s*\x07", stripped):
            return "bullet_item"

    # 2. Numbered paragraph patterns:
    # A) Single number line: "1." or "7"
    if re.match(r"^\d+\.?$", stripped):
        return "numbered_paragraph"

    # B) UK numbered start: "59. The MOD...", "3. With rapid..."
    if re.match(r"^\d+\.\s+[A-Z]", stripped):
        return "numbered_paragraph"

    # C) Latvia numbered start: "1 The State...", "131 The defence..."
    if re.match(r"^\d+\s+[A-Z]", stripped):
        return "numbered_paragraph"

    # 3. Bullet item pattern: "• ...", "- ...", "* ..."
    if re.match(r"^[•\-\*]\s+", stripped):
        return "bullet_item"

    return None


def normalize_segment_text(lines: list[str]) -> str:
    """Join source lines using the same normalization as regular segments."""
    text = " ".join(line.strip() for line in lines if line.strip())
    return re.sub(r"[ \t]+", " ", text).strip()


def split_netherlands_oversized_segment(segment: dict, page_lines: list[str]) -> list[dict]:
    """Split an oversized Netherlands segment at deterministic source-line boundaries."""
    if segment["word_count"] <= NETHERLANDS_MAX_SEGMENT_WORDS:
        return [segment]

    line_entries = [
        (line_number, page_lines[line_number - 1].strip())
        for line_number in range(segment["source_line_start"], segment["source_line_end"] + 1)
        if page_lines[line_number - 1].strip()
    ]
    chunks = []
    start_index = 0

    while start_index < len(line_entries):
        remaining_entries = line_entries[start_index:]
        remaining_words = sum(len(line.split()) for _, line in remaining_entries)
        if remaining_words <= NETHERLANDS_FALLBACK_PREFERRED_MAX_WORDS:
            chunks.append(remaining_entries)
            break

        candidates = []
        cumulative_words = 0
        for relative_index, (_, line) in enumerate(remaining_entries[:-1]):
            cumulative_words += len(line.split())
            trailing_words = remaining_words - cumulative_words
            if cumulative_words < 200 or trailing_words < 120:
                continue
            if cumulative_words > NETHERLANDS_FALLBACK_PREFERRED_MAX_WORDS:
                break
            ends_sentence = line.rstrip().endswith((".", "!", "?"))
            candidates.append((not ends_sentence, abs(cumulative_words - NETHERLANDS_FALLBACK_TARGET_WORDS), relative_index))

        if candidates:
            _, _, split_relative_index = min(candidates)
        else:
            cumulative_words = 0
            safe_candidates = []
            for relative_index, (_, line) in enumerate(remaining_entries[:-1]):
                cumulative_words += len(line.split())
                trailing_words = remaining_words - cumulative_words
                if cumulative_words >= 150 and trailing_words >= 100:
                    safe_candidates.append((abs(cumulative_words - NETHERLANDS_FALLBACK_TARGET_WORDS), relative_index))
                if cumulative_words >= NETHERLANDS_FALLBACK_PREFERRED_MAX_WORDS:
                    break
            if not safe_candidates:
                chunks.append(remaining_entries)
                break
            _, split_relative_index = min(safe_candidates)

        split_index = start_index + split_relative_index + 1
        chunks.append(line_entries[start_index:split_index])
        start_index = split_index

    split_segments = []
    fallback_type = segment["segment_type"]
    if fallback_type in {"heading", "bullet_item"}:
        fallback_type = "paragraph"

    for chunk in chunks:
        chunk_text = normalize_segment_text([line for _, line in chunk])
        split_segment = dict(segment)
        split_segment.update({
            "segment_type": fallback_type,
            "source_line_start": chunk[0][0],
            "source_line_end": chunk[-1][0],
            "text": chunk_text,
            "word_count": len(chunk_text.split()),
            "char_count": len(chunk_text),
        })
        split_segments.append(split_segment)

    return split_segments


def is_japan_structural_start(line: str) -> bool:
    """Detect structural sub-headings and figure/box starts in Japan White Paper."""
    s = line.strip()
    if re.match(r"^\(\d+\)\s+", s):
        return True
    if re.match(r"^\([ivx]+\)\s+", s, re.IGNORECASE):
        return True
    if re.match(r"^[a-z]\.\s+[A-Z]", s):
        return True
    if re.match(r"^(?:Fig\.|Table)\s+[I|V|X|\d]+", s):
        return True
    if re.match(r"^(?:Commentary|Perspective|VOICE)\b", s):
        return True
    return False


def is_sentence_end(line: str) -> bool:
    """Check if a line ends with standard sentence-ending punctuation."""
    s = line.rstrip()
    return s.endswith((".", "!", "?", '."', ".'", '?”', '!”', ".\”", ".”"))


def split_japan_oversized_segment(segment: dict, page_lines: list[str]) -> list[dict]:
    """
    Split an oversized Japan segment at deterministic textual boundaries:
    1. Structural markers ((1), (i), a., Fig., Commentary/Perspective/VOICE)
    2. Sentence boundaries
    3. Safe line fallback
    """
    if segment["word_count"] <= JAPAN_MAX_SEGMENT_WORDS:
        return [segment]

    line_entries = [
        (line_number, page_lines[line_number - 1].strip())
        for line_number in range(segment["source_line_start"], segment["source_line_end"] + 1)
        if page_lines[line_number - 1].strip()
    ]
    chunks = []
    start_index = 0

    while start_index < len(line_entries):
        remaining_entries = line_entries[start_index:]
        remaining_words = sum(len(line.split()) for _, line in remaining_entries)
        if remaining_words <= JAPAN_PREFERRED_MAX_WORDS:
            chunks.append(remaining_entries)
            break

        candidates = []
        cumulative_words = 0
        for relative_index, (_, line) in enumerate(remaining_entries[:-1]):
            cumulative_words += len(line.split())
            trailing_words = remaining_words - cumulative_words
            next_line = remaining_entries[relative_index + 1][1]

            is_struct = is_japan_structural_start(next_line)
            is_sent = is_sentence_end(line)

            # Priority 0: Structural sub-heading boundary
            if is_struct and cumulative_words >= 140 and trailing_words >= 100:
                candidates.append((0, abs(cumulative_words - JAPAN_TARGET_WORDS), relative_index))
            # Priority 1: Sentence boundary
            elif is_sent and cumulative_words >= 170 and trailing_words >= 100:
                candidates.append((1, abs(cumulative_words - JAPAN_TARGET_WORDS), relative_index))

            if cumulative_words > JAPAN_PREFERRED_MAX_WORDS:
                break

        if candidates:
            candidates.sort(key=lambda c: (c[0], c[1]))
            split_relative_index = candidates[0][2]
        else:
            # Fallback 1: Any sentence boundary before 450 words
            cumulative_words = 0
            sent_candidates = []
            for relative_index, (_, line) in enumerate(remaining_entries[:-1]):
                cumulative_words += len(line.split())
                trailing_words = remaining_words - cumulative_words
                if is_sentence_end(line) and cumulative_words >= 120 and trailing_words >= 80:
                    sent_candidates.append((abs(cumulative_words - JAPAN_TARGET_WORDS), relative_index))
                if cumulative_words > 450:
                    break
            if sent_candidates:
                sent_candidates.sort(key=lambda c: c[0])
                split_relative_index = sent_candidates[0][1]
            else:
                # Fallback 2: Any line boundary
                cumulative_words = 0
                safe_candidates = []
                for relative_index, (_, line) in enumerate(remaining_entries[:-1]):
                    cumulative_words += len(line.split())
                    trailing_words = remaining_words - cumulative_words
                    if cumulative_words >= 150 and trailing_words >= 80:
                        safe_candidates.append((abs(cumulative_words - JAPAN_TARGET_WORDS), relative_index))
                    if cumulative_words >= JAPAN_PREFERRED_MAX_WORDS:
                        break
                if not safe_candidates:
                    chunks.append(remaining_entries)
                    break
                safe_candidates.sort(key=lambda c: c[0])
                split_relative_index = safe_candidates[0][1]

        split_index = start_index + split_relative_index + 1
        chunks.append(line_entries[start_index:split_index])
        start_index = split_index

    split_segments = []
    fallback_type = segment["segment_type"]
    if fallback_type in {"heading", "bullet_item"}:
        fallback_type = "paragraph"

    for chunk in chunks:
        first_line = chunk[0][1]
        chunk_type = fallback_type
        if is_japan_structural_start(first_line):
            if re.match(r"^\(\d+\)\s+", first_line) or re.match(r"^\([ivx]+\)\s+", first_line, re.IGNORECASE):
                chunk_type = "numbered_paragraph"
            elif re.match(r"^[a-z]\.\s+", first_line):
                chunk_type = "paragraph"
        chunk_text = normalize_segment_text([line for _, line in chunk])
        split_segment = dict(segment)
        split_segment.update({
            "segment_type": chunk_type,
            "source_line_start": chunk[0][0],
            "source_line_end": chunk[-1][0],
            "text": chunk_text,
            "word_count": len(chunk_text.split()),
            "char_count": len(chunk_text),
        })
        split_segments.append(split_segment)

    return split_segments


def finalize_page_segments(page_data: dict, segments: list[dict], page_lines: list[str]) -> list[dict]:
    """Apply document-specific fallback splitting and assign final deterministic IDs."""
    if page_data["document_id"] == NETHERLANDS_DOCUMENT_ID:
        finalized = []
        for segment in segments:
            finalized.extend(split_netherlands_oversized_segment(segment, page_lines))
    elif page_data["document_id"] == JAPAN_DOCUMENT_ID:
        finalized = []
        for segment in segments:
            finalized.extend(split_japan_oversized_segment(segment, page_lines))
    else:
        finalized = segments

    for segment_index, segment in enumerate(finalized, start=1):
        segment["segment_index"] = segment_index
        segment["segment_id"] = (
            f"{page_data['document_id']}_p{page_data['page_number_pdf']:03d}_s{segment_index:03d}"
        )
    return finalized


def segment_page(page_data: dict) -> list[dict]:
    """
    Segments a single page's cleaned_text into traceable passages.
    Never merges across pages.
    """
    cleaned_text = page_data.get("cleaned_text", "")
    if not cleaned_text:
        return []

    lines = cleaned_text.split("\n")
    segments = []

    current_segment_lines = []
    current_segment_type = None
    current_line_start = None
    current_line_end = None
    previous_nonempty_line = None

    def flush_segment():
        nonlocal current_segment_lines, current_segment_type, current_line_start, current_line_end
        if not current_segment_lines:
            return

        text = normalize_segment_text(current_segment_lines)

        if text:
            seg_idx = len(segments) + 1
            seg_id = f"{page_data['document_id']}_p{page_data['page_number_pdf']:03d}_s{seg_idx:03d}"
            segments.append({
                "segment_id": seg_id,
                "document_id": page_data["document_id"],
                "country": page_data["country"],
                "page_number_pdf": page_data["page_number_pdf"],
                "page_number_printed": page_data["page_number_printed"],
                "segment_index": seg_idx,
                "segment_type": current_segment_type,
                "source_line_start": current_line_start,
                "source_line_end": current_line_end,
                "text": text,
                "word_count": len(text.split()),
                "char_count": len(text)
            })

        current_segment_lines = []
        current_segment_type = None
        current_line_start = None
        current_line_end = None

    for idx, line in enumerate(lines):
        line_num = idx + 1
        stripped = line.strip()

        if not stripped:
            continue

        next_nonempty_line = next(
            (candidate.strip() for candidate in lines[idx + 1:] if candidate.strip()),
            None,
        )
        boundary = detect_boundary_type(
            stripped,
            page_data["document_id"],
            previous_nonempty_line,
            next_nonempty_line,
        )

        if boundary is not None:
            # New boundary detected; flush previous segment
            flush_segment()
            current_segment_lines = [stripped]
            current_segment_type = boundary
            current_line_start = line_num
            current_line_end = line_num
        else:
            # Continuing line or initial paragraph without explicit boundary
            if current_segment_type is None:
                current_segment_lines = [stripped]
                current_segment_type = "paragraph"
                current_line_start = line_num
                current_line_end = line_num
            else:
                current_segment_lines.append(stripped)
                current_line_end = line_num

        previous_nonempty_line = stripped

    flush_segment()
    return finalize_page_segments(page_data, segments, lines)


def segment_document(doc_data: dict, input_path: Path, output_path: Path) -> dict:
    """
    Segments all included pages in a document and outputs structured JSON.
    """
    all_segments = []
    type_counts = {
        "heading": 0,
        "numbered_paragraph": 0,
        "bullet_item": 0,
        "paragraph": 0
    }

    pages = doc_data.get("pages", [])
    for page in pages:
        if not page.get("include_in_analysis", False):
            continue

        page_segments = segment_page(page)
        for seg in page_segments:
            seg_type = seg["segment_type"]
            type_counts[seg_type] = type_counts.get(seg_type, 0) + 1
            all_segments.append(seg)

    result = {
        "document": {
            "document_id": doc_data["document"]["document_id"],
            "country": doc_data["document"]["country"],
            "analysis_scope": doc_data["document"]["analysis_scope"],
            "source_extraction_file": str(input_path),
            "total_segments": len(all_segments),
            "segments_by_type": type_counts
        },
        "segments": all_segments
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def main():
    parser = argparse.ArgumentParser(description="Segment extracted pages into traceable source passages.")
    parser.add_argument("--document-id", required=True, help="Document ID (e.g. latvia_sdc_2023)")
    parser.add_argument("--scope", default="core_body", help="Analysis scope (default: core_body)")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    input_filename = f"{args.document_id}_{args.scope}.json"
    input_path = project_root / "data" / "processed" / input_filename

    if not input_path.exists():
        print(f"Error: Input extraction file does not exist: {input_path}", file=sys.stderr)
        sys.exit(1)

    doc_data = load_json(input_path)
    output_filename = f"{args.document_id}_{args.scope}_segments.json"
    output_path = project_root / "data" / "processed" / output_filename

    result = segment_document(doc_data, input_path, output_path)

    doc_info = result["document"]
    print("Document:", doc_info["document_id"])
    print("Scope:", doc_info["analysis_scope"])
    print("Total segments:", doc_info["total_segments"])
    print("Segments by type:", doc_info["segments_by_type"])
    print("Output:", output_path)


if __name__ == "__main__":
    main()
