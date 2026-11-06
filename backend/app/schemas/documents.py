"""
backend.app.schemas.documents
-----------------------------
Request and response schemas for document, category, and passage endpoints.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class DocumentSummary(BaseModel):
    id: str = Field(..., description="Canonical document ID")
    country: str = Field(..., description="Document country")
    title: str = Field(..., description="Official document title")
    total_words: int = Field(..., description="Total analyzed words")
    total_segments: int = Field(..., description="Total segments in document")
    detected_matches: int = Field(..., description="Total detected matches found")


class CategorySummary(BaseModel):
    category: str = Field(..., description="Threat category name")
    frequency_per_1000_words: float = Field(..., description="Normalized frequency per 1,000 words")
    raw_baseline_mentions: int = Field(..., description="Raw baseline term mentions")
    detected_mentions: int = Field(..., description="Total detected mentions")
    review_required_mentions: int = Field(..., description="Review required mentions count")
    segment_hits: int = Field(..., description="Unique segment hits containing mentions")


class DocumentDetail(BaseModel):
    id: str
    country: str
    title: str
    total_words: int
    total_segments: int
    detected_matches: int
    raw_baseline_total: int
    categories: dict[str, CategorySummary]
    rankings: list[dict[str, Any]]


class MatchedTermCount(BaseModel):
    term: str
    count: int


class PassageItem(BaseModel):
    segment_id: str
    category: str
    pdf_page: int
    printed_page: int | None = None
    text: str
    match_count: int
    matched_terms: list[MatchedTermCount]
    matches: list[dict[str, Any]]


class PassageListResponse(BaseModel):
    document_id: str
    category: str
    total_passages: int
    total_raw_mentions: int
    passages: list[PassageItem]

