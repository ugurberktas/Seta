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


def detect_boundary_type(line: str) -> str | None:
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

    def flush_segment():
        nonlocal current_segment_lines, current_segment_type, current_line_start, current_line_end
        if not current_segment_lines:
            return

        text = " ".join(line.strip() for line in current_segment_lines if line.strip())
        # Clean any accidental extra internal spaces
        text = re.sub(r"[ \t]+", " ", text).strip()

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

        boundary = detect_boundary_type(stripped)

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

    flush_segment()
    return segments


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
