#!/usr/bin/env python3
"""
src/extract.py

Extracts text from verified defence policy PDF documents page by page,
applying structural rules from data/extraction_rules.json and metadata
from data/sources.json to produce structured JSON outputs.

Part of Sprint 1 (Adım 2B).
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import pymupdf  # PyMuPDF
except ImportError:
    try:
        import fitz as pymupdf
    except ImportError:
        print("Error: PyMuPDF is not installed. Please activate your virtual environment.", file=sys.stderr)
        sys.exit(1)


def load_json(file_path: Path):
    """Load and parse JSON file."""
    if not file_path.exists():
        print(f"Error: Required file not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def expand_page_specs(specs: list) -> set[int]:
    """
    Expands a list of page specifications into a set of 1-based page numbers.
    Supports single integers (e.g., 1, 2) and ranges (e.g., [3, 19]).
    """
    expanded = set()
    for item in specs:
        if isinstance(item, int):
            expanded.add(item)
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            start, end = item
            expanded.update(range(start, end + 1))
        else:
            raise ValueError(f"Unsupported page specification format: {item}")
    return expanded


def parse_page_sets(page_rules: dict) -> dict[str, set[int]]:
    """Parse all page sets from the page rules dictionary."""
    return {
        "cover": expand_page_specs(page_rules.get("cover", [])),
        "back_cover": expand_page_specs(page_rules.get("back_cover", [])),
        "publication_metadata": expand_page_specs(page_rules.get("publication_metadata", [])),
        "table_of_contents": expand_page_specs(page_rules.get("table_of_contents", [])),
        "front_matter": expand_page_specs(page_rules.get("front_matter", [])),
        "section_dividers": expand_page_specs(page_rules.get("section_dividers", [])),
        "appendices": expand_page_specs(page_rules.get("appendices", [])),
        "blank_pages": expand_page_specs(page_rules.get("blank_pages", [])),
        "visual_only": expand_page_specs(page_rules.get("visual_only", [])),
        "foreword": expand_page_specs(page_rules.get("foreword", [])) | expand_page_specs(page_rules.get("foreword_ranges", [])),
        "core_body": expand_page_specs(page_rules.get("core_body", [])) | expand_page_specs(page_rules.get("core_body_ranges", [])),
        "visual_heavy": expand_page_specs(page_rules.get("visual_heavy", [])) | expand_page_specs(page_rules.get("visual_heavy_pages", []))
    }


def classify_page(page_num: int, page_sets: dict[str, set[int]]) -> tuple[str, bool]:
    """
    Classifies a 1-based PDF page into a section_type and visual_heavy flag.
    Explicit exclusion types win over core_body.
    """
    is_visual_heavy = page_num in page_sets["visual_heavy"]

    if page_num in page_sets["blank_pages"]:
        return "blank_page", is_visual_heavy
    if page_num in page_sets["visual_only"]:
        return "visual_only", is_visual_heavy
    if page_num in page_sets["section_dividers"]:
        return "section_divider", is_visual_heavy
    if page_num in page_sets["appendices"]:
        return "appendix", is_visual_heavy
    if page_num in page_sets["front_matter"]:
        return "front_matter", is_visual_heavy
    if page_num in page_sets["back_cover"]:
        return "back_cover", is_visual_heavy
    if page_num in page_sets["cover"]:
        return "cover", is_visual_heavy
    if page_num in page_sets["publication_metadata"]:
        return "publication_metadata", is_visual_heavy
    if page_num in page_sets["table_of_contents"]:
        return "table_of_contents", is_visual_heavy
    if page_num in page_sets["foreword"]:
        return "foreword", is_visual_heavy
    if page_num in page_sets["core_body"]:
        return "core_body", is_visual_heavy

    return "other", is_visual_heavy


def resolve_scope(requested_scope: str | None, doc_rules: dict) -> str:
    """Resolve and validate the analysis scope."""
    scope = requested_scope or doc_rules.get("default_analysis_scope", "core_body")
    available_scopes = doc_rules.get("available_analysis_scopes", {})

    # If document has explicitly defined scopes, validate against them
    if available_scopes and scope not in available_scopes and scope != "core_body":
        print(f"Error: Invalid scope '{scope}'. Available: {list(available_scopes.keys())}", file=sys.stderr)
        sys.exit(1)

    if scope not in ("core_body", "extended_body"):
        print(f"Error: Unsupported scope '{scope}'. Supported: core_body, extended_body", file=sys.stderr)
        sys.exit(1)

    return scope


def clean_latvia_header(text: str, page_num_pdf: int) -> str:
    """
    Latvia cleaning rule:
    If the first non-empty line equals the printed page number (str(page_num_pdf)),
    remove only that first line.
    Preserves all numbers in the rest of the text.
    """
    if not text:
        return ""

    lines = text.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped:
            if stripped == str(page_num_pdf):
                # Remove this header line
                return "\n".join(lines[:i] + lines[i + 1:])
            break
    return text


def clean_uk_footer(text: str, page_number_printed: int | None) -> str:
    """
    UK cleaning rule:
    Check only the last two non-empty lines.
    If the penultimate non-empty line exactly equals str(page_number_printed),
    remove both the printed page number line and the trailing section title line.
    Does not apply to pages where page_number_printed is None (cover/TOC/metadata).
    """
    if not text or page_number_printed is None:
        return text

    lines = text.split("\n")
    non_empty_indices = [i for i, line in enumerate(lines) if line.strip()]

    if len(non_empty_indices) >= 2:
        penultimate_idx = non_empty_indices[-2]
        if lines[penultimate_idx].strip() == str(page_number_printed):
            # Remove from penultimate_idx onwards (page number + section title)
            return "\n".join(lines[:penultimate_idx])

    return text


NETHERLANDS_RUNNING_HEADERS = {
    "1. SECURITY ENVIRONMENT",
    "2. TASKS AND OBJECTIVES",
    "3. STRATEGIC COURSE FOR STRENGTHENING DEFENCE",
    "4. COMBAT POWER",
    "5. PEOPLE",
    "6. MATERIEL",
    "7. PRECONDITIONS",
}
NETHERLANDS_RUNNING_FOOTER = "DEFENCE WHITE PAPER | 2024"


def clean_netherlands_page(text: str, page_num_pdf: int) -> str:
    """
    Remove only the confirmed trailing running-header/footer block.

    Each Netherlands PDF page is a two-page printed spread. The cleaner
    considers only the final ten non-empty lines, requires the exact running
    footer to be present there, and removes a contiguous suffix containing:
    - exact known chapter running headers,
    - the exact running footer, and
    - the two folio numbers structurally associated with that PDF spread.

    Body text and standalone numbers elsewhere are preserved.
    """
    if not text:
        return ""

    lines = text.split("\n")
    non_empty_indices = [i for i, line in enumerate(lines) if line.strip()]
    if not non_empty_indices:
        return text

    def normalized_line(index: int) -> str:
        return re.sub(r"\s+", " ", lines[index]).strip()

    tail_indices = non_empty_indices[-10:]
    if NETHERLANDS_RUNNING_FOOTER not in {
        normalized_line(i) for i in tail_indices
    }:
        return text

    expected_folios = {
        str((2 * page_num_pdf) - 2),
        str((2 * page_num_pdf) - 1),
    }
    removable_lines = (
        NETHERLANDS_RUNNING_HEADERS
        | {NETHERLANDS_RUNNING_FOOTER}
        | expected_folios
    )

    remove_indices = set()
    for index in reversed(non_empty_indices):
        if normalized_line(index) not in removable_lines:
            break
        remove_indices.add(index)

    return "\n".join(
        line for index, line in enumerate(lines) if index not in remove_indices
    )


def repair_hyphenated_line_breaks(text: str) -> str:
    """
    Repairs safe hyphenated line-breaks:
    word- <newline> word -> word-word
    Preserves the hyphen and words (e.g., nuclear- \n powered -> nuclear-powered).
    Does not modify em-dashes (—), en-dashes, or non-line-break hyphens.
    """
    if not text:
        return ""
    return re.sub(r"([A-Za-z]+)-[ \t]*\n[ \t]*([A-Za-z]+)", r"\1-\2", text)


def normalize_whitespace(text: str) -> str:
    """
    Conservative whitespace normalization:
    - Normalizes CRLF to LF.
    - Strips trailing whitespace per line.
    - Collapses horizontal whitespace (spaces/tabs) to a single space.
    - Collapses 3+ consecutive newlines to at most 2 newlines (preserves paragraph boundaries).
    - Strips overall leading/trailing whitespace.
    """
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    cleaned_lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", line)
        cleaned_lines.append(line.strip())

    result = "\n".join(cleaned_lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def clean_page_text(raw_text: str, doc_id: str, page_num_pdf: int, page_number_printed: int | None) -> str:
    """
    Executes the cleaning pipeline:
    raw_text
    -> document-specific header/footer cleanup
    -> non-breaking space replacement
    -> hyphenated line-break repair
    -> conservative whitespace normalization
    -> cleaned_text
    """
    if not raw_text:
        return ""

    text = raw_text

    # 1. Document-specific header/footer cleanup
    if doc_id == "latvia_sdc_2023":
        text = clean_latvia_header(text, page_num_pdf)
    elif doc_id == "uk_sdr_2025":
        text = clean_uk_footer(text, page_number_printed)
    elif doc_id == "netherlands_dwp_2024":
        text = clean_netherlands_page(text, page_num_pdf)

    # 2. Non-breaking space replacement (\u00a0 -> space)
    text = text.replace("\u00a0", " ")

    # 3. Hyphenated line-break repair (word- \n word -> word-word)
    text = repair_hyphenated_line_breaks(text)

    # 4. Conservative line-break / whitespace normalization
    text = normalize_whitespace(text)

    return text


def calculate_word_count(text: str) -> int:
    """
    Calculate word count using whitespace tokenization.
    Note: Simple token count; can be refined in future analysis steps.
    """
    if not text:
        return 0
    return len(text.split())


def determine_inclusion_and_reason(section_type: str, scope: str) -> tuple[bool, str | None]:
    """
    Determine if a page is included in analysis and the exclusion reason if not.
    """
    # Non-body pages are always excluded
    if section_type in (
        "cover",
        "back_cover",
        "publication_metadata",
        "table_of_contents",
        "front_matter",
        "visual_only",
        "section_divider",
        "appendix",
        "blank_page",
        "other",
    ):
        return False, section_type

    if scope == "core_body":
        if section_type == "core_body":
            return True, None
        return False, f"{section_type}_excluded_in_core_scope"

    if scope == "extended_body":
        if section_type in ("core_body", "foreword"):
            return True, None
        return False, f"{section_type}_excluded_in_extended_scope"

    return False, "unknown_scope"


def extract_document(doc_meta: dict, doc_rules: dict, scope: str, raw_pdf_path: Path, output_path: Path) -> dict:
    """
    Extracts pages from a single verified document and writes the processed JSON output.
    """
    expected_pages = doc_rules.get("total_pdf_pages_expected")
    printed_page_mode = doc_rules.get("page_number_printed_mode", "offset")
    if printed_page_mode not in ("offset", "none"):
        raise ValueError(
            "Unsupported page_number_printed_mode "
            f"'{printed_page_mode}'. Allowed values: offset, none"
        )
    offset = doc_rules.get("page_number_printed_offset", 0)
    page_sets = parse_page_sets(doc_rules.get("pages", {}))

    doc = pymupdf.open(str(raw_pdf_path))
    actual_pages = len(doc)

    if expected_pages is not None and actual_pages != expected_pages:
        print(
            f"Error: Page count mismatch for {doc_meta['id']}. Expected {expected_pages}, got {actual_pages}.",
            file=sys.stderr
        )
        sys.exit(1)

    pages_output = []
    included_page_numbers = []
    total_analysis_words = 0

    for idx, page in enumerate(doc):
        page_num_pdf = idx + 1
        raw_text = page.get_text()

        section_type, is_visual_heavy = classify_page(page_num_pdf, page_sets)
        include_in_analysis, exclusion_reason = determine_inclusion_and_reason(section_type, scope)

        # Printed page number computation
        if printed_page_mode == "none":
            page_number_printed = None
        elif section_type in ("cover", "publication_metadata", "table_of_contents", "blank_page"):
            page_number_printed = None
        else:
            calc_printed = page_num_pdf + offset
            page_number_printed = calc_printed if calc_printed > 0 else None

        # Clean text using pipeline
        cleaned_text = clean_page_text(raw_text, doc_meta["id"], page_num_pdf, page_number_printed)

        word_count = calculate_word_count(cleaned_text)
        char_count = len(cleaned_text)

        if include_in_analysis:
            included_page_numbers.append(page_num_pdf)
            total_analysis_words += word_count

        page_record = {
            "document_id": doc_meta["id"],
            "country": doc_meta["country"],
            "page_number_pdf": page_num_pdf,
            "page_number_printed": page_number_printed,
            "section_type": section_type,
            "is_visual_heavy": is_visual_heavy,
            "raw_text": raw_text,
            "cleaned_text": cleaned_text,
            "include_in_analysis": include_in_analysis,
            "exclusion_reason": exclusion_reason,
            "word_count": word_count,
            "char_count": char_count
        }
        pages_output.append(page_record)

    doc.close()

    result = {
        "document": {
            "document_id": doc_meta["id"],
            "title": doc_meta["title"],
            "country": doc_meta["country"],
            "year": doc_meta["year"],
            "analysis_scope": scope,
            "total_pdf_pages": actual_pages,
            "included_pages_count": len(included_page_numbers),
            "excluded_pages_count": actual_pages - len(included_page_numbers),
            "included_page_numbers_pdf": included_page_numbers,
            "total_analysis_words": total_analysis_words
        },
        "pages": pages_output
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def main():
    parser = argparse.ArgumentParser(description="Extract structured text from defense policy PDFs.")
    parser.add_argument("--document-id", required=True, help="ID of the document to extract (e.g. latvia_sdc_2023)")
    parser.add_argument("--scope", default=None, help="Analysis scope (core_body or extended_body)")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    sources_file = project_root / "data" / "sources.json"
    rules_file = project_root / "data" / "extraction_rules.json"

    sources_data = load_json(sources_file)
    rules_data = load_json(rules_file)

    # Find document in sources.json
    doc_meta = next((s for s in sources_data if s.get("id") == args.document_id), None)
    if not doc_meta:
        print(f"Error: Document ID '{args.document_id}' not found in sources.json.", file=sys.stderr)
        sys.exit(1)

    # Check verified download status
    if doc_meta.get("download_status") != "verified":
        print(
            f"Error: Document '{args.document_id}' has download_status='{doc_meta.get('download_status')}'. "
            "Only 'verified' documents can be extracted.",
            file=sys.stderr
        )
        sys.exit(1)

    # Find document rules
    doc_rules = rules_data.get(args.document_id)
    if not doc_rules:
        print(f"Error: Document ID '{args.document_id}' not found in extraction_rules.json.", file=sys.stderr)
        sys.exit(1)

    # Check PDF file existence
    pdf_filename = doc_meta.get("filename")
    if not pdf_filename:
        print(f"Error: No filename specified for '{args.document_id}' in sources.json.", file=sys.stderr)
        sys.exit(1)

    raw_pdf_path = project_root / "data" / "raw" / pdf_filename
    if not raw_pdf_path.exists():
        print(f"Error: Raw PDF file does not exist: {raw_pdf_path}", file=sys.stderr)
        sys.exit(1)

    scope = resolve_scope(args.scope, doc_rules)
    output_filename = f"{args.document_id}_{scope}.json"
    output_path = project_root / "data" / "processed" / output_filename

    result = extract_document(doc_meta, doc_rules, scope, raw_pdf_path, output_path)

    doc_info = result["document"]
    print("Document:", doc_info["document_id"])
    print("Scope:", doc_info["analysis_scope"])
    print("PDF pages:", doc_info["total_pdf_pages"])
    print("Included pages:", doc_info["included_pages_count"])
    print("Excluded pages:", doc_info["excluded_pages_count"])
    print("Analysis words:", doc_info["total_analysis_words"])
    print("Output:", output_path)


if __name__ == "__main__":
    main()
