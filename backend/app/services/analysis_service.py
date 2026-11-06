"""
backend.app.services.analysis_service
-------------------------------------
Service layer for consuming existing canonical analysis JSON outputs.
Never recalculates or re-extracts canonical analysis.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

from backend.app.core.config import PROCESSED_DATA_DIR
from backend.app.schemas.documents import (
    CategorySummary,
    DocumentDetail,
    DocumentSummary,
    MatchedTermCount,
    PassageItem,
    PassageListResponse,
)

CANONICAL_DOCUMENTS: dict[str, dict[str, str]] = {
    "latvia_sdc_2023": {
        "id": "latvia_sdc_2023",
        "country": "Latvia",
        "title": "State Defence Concept 2023–2027",
    },
    "uk_sdr_2025": {
        "id": "uk_sdr_2025",
        "country": "United Kingdom",
        "title": "Strategic Defence Review 2025",
    },
    "netherlands_dwp_2024": {
        "id": "netherlands_dwp_2024",
        "country": "Netherlands",
        "title": "Defence White Paper 2024",
    },
    "japan_doj_2026": {
        "id": "japan_doj_2026",
        "country": "Japan",
        "title": "Defense of Japan 2026",
    },
}


class AnalysisService:
    """Provides access to precomputed canonical threat analysis outputs."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or PROCESSED_DATA_DIR
        self._cache: dict[str, dict[str, Any]] = {}

    def _load_canonical_json(self, document_id: str) -> dict[str, Any] | None:
        """Load and cache canonical threat matches JSON."""
        if document_id in self._cache:
            return self._cache[document_id]

        if document_id not in CANONICAL_DOCUMENTS:
            return None

        file_path = self.data_dir / f"{document_id}_core_body_threat_matches.json"
        if not file_path.exists():
            return None

        with file_path.open(encoding="utf-8") as f:
            data = json.load(f)

        self._cache[document_id] = data
        return data

    def list_documents(self) -> list[DocumentSummary]:
        """Return lightweight document summaries for all canonical documents."""
        summaries: list[DocumentSummary] = []
        for doc_id, meta in CANONICAL_DOCUMENTS.items():
            data = self._load_canonical_json(doc_id)
            if not data:
                continue

            doc_info = data.get("document", {})
            matches = data.get("matches", [])
            summaries.append(
                DocumentSummary(
                    id=doc_id,
                    country=meta["country"],
                    title=meta["title"],
                    total_words=doc_info.get("total_analysis_words", 0),
                    total_segments=doc_info.get("total_segments", 0),
                    detected_matches=len(matches),
                )
            )
        return summaries

    def get_document(self, document_id: str) -> DocumentDetail | None:
        """Return detailed canonical metrics, category summaries, and rankings."""
        data = self._load_canonical_json(document_id)
        if not data:
            return None

        meta = CANONICAL_DOCUMENTS[document_id]
        doc_info = data.get("document", {})
        matches = data.get("matches", [])
        summary = data.get("summary", {})
        rankings = data.get("ranking_by_frequency", [])

        categories: dict[str, CategorySummary] = {}
        raw_baseline_total = 0

        for cat_name, cat_data in summary.items():
            if not isinstance(cat_data, dict):
                continue
            raw_base = cat_data.get("raw_baseline_mentions", 0)
            raw_baseline_total += raw_base

            categories[cat_name] = CategorySummary(
                category=cat_name,
                frequency_per_1000_words=cat_data.get("frequency_per_1000_words", 0.0),
                raw_baseline_mentions=raw_base,
                detected_mentions=cat_data.get("detected_mentions", 0),
                review_required_mentions=cat_data.get("review_required_mentions", 0),
                segment_hits=cat_data.get("segment_hits", 0),
            )

        return DocumentDetail(
            id=document_id,
            country=meta["country"],
            title=meta["title"],
            total_words=doc_info.get("total_analysis_words", 0),
            total_segments=doc_info.get("total_segments", 0),
            detected_matches=len(matches),
            raw_baseline_total=raw_baseline_total,
            categories=categories,
            rankings=rankings,
        )

    def get_category(self, document_id: str, category: str) -> CategorySummary | None:
        """Return category summary metrics for a given document and category."""
        data = self._load_canonical_json(document_id)
        if not data:
            return None

        cat_data = data.get("summary", {}).get(category)
        if not cat_data or not isinstance(cat_data, dict):
            return None

        return CategorySummary(
            category=category,
            frequency_per_1000_words=cat_data.get("frequency_per_1000_words", 0.0),
            raw_baseline_mentions=cat_data.get("raw_baseline_mentions", 0),
            detected_mentions=cat_data.get("detected_mentions", 0),
            review_required_mentions=cat_data.get("review_required_mentions", 0),
            segment_hits=cat_data.get("segment_hits", 0),
        )

    def get_passages(
        self,
        document_id: str,
        category: str,
        show_review_only: bool = False,
        include_review_only: bool = False,
    ) -> PassageListResponse | None:
        """Return unique passage items grouped by (document_id, category, segment_id).

        Preserves individual constituent matches for full analytical traceability.
        """
        data = self._load_canonical_json(document_id)
        if not data:
            return None

        if category not in data.get("summary", {}):
            return None

        matches = data.get("matches", [])

        # 1. Filter matches according to category and review flags
        active_matches = [
            m for m in data.get("matches", []) if m.get("category") == category
        ]
        if not include_review_only:
            active_matches = [
                m for m in active_matches if m.get("count_in_raw_baseline", True)
            ]
        if show_review_only:
            active_matches = [
                m for m in active_matches if m.get("requires_review", False)
            ]

        # 2. Group into unique passages by segment_id
        passages_by_segment: dict[str, list[dict[str, Any]]] = {}
        for m in active_matches:
            seg_id = m["segment_id"]
            if seg_id not in passages_by_segment:
                passages_by_segment[seg_id] = []
            passages_by_segment[seg_id].append(m)

        # 3. Construct API passage items
        passage_items: list[PassageItem] = []
        for seg_id, group_matches in passages_by_segment.items():
            first_match = group_matches[0]
            term_counter = Counter(
                m.get("matched_text") or m.get("term") or m.get("pattern_id") or ""
                for m in group_matches
            )
            matched_terms = [
                MatchedTermCount(term=term, count=count)
                for term, count in term_counter.most_common()
            ]

            pdf_page = (
                first_match.get("page_number_pdf")
                or first_match.get("pdf_page")
                or 0
            )
            printed_page = (
                first_match.get("page_number_printed")
                or first_match.get("printed_page")
            )

            passage_items.append(
                PassageItem(
                    segment_id=seg_id,
                    category=category,
                    pdf_page=pdf_page,
                    printed_page=printed_page,
                    text=first_match.get("segment_text", ""),
                    match_count=len(group_matches),
                    matched_terms=matched_terms,
                    matches=group_matches,
                )
            )

        return PassageListResponse(
            document_id=document_id,
            category=category,
            total_passages=len(passage_items),
            total_raw_mentions=len(active_matches),
            passages=passage_items,
        )

    def is_canonical_document(self, document_id: str) -> bool:
        """Check if document_id is one of the supported canonical documents."""
        return document_id in CANONICAL_DOCUMENTS

    def is_valid_category(self, document_id: str, category: str) -> bool:
        """Check if category exists in canonical data for the specified document."""
        data = self._load_canonical_json(document_id)
        if not data:
            return False
        return category in data.get("summary", {})


analysis_service = AnalysisService()
