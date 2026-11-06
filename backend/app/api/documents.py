"""
backend.app.api.documents
-------------------------
Document, category summary, and passage retrieval endpoints.
All endpoints require authentication.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.core.security import CurrentUser
from backend.app.schemas.documents import (
    CategorySummary,
    DocumentDetail,
    DocumentSummary,
    PassageListResponse,
)
from backend.app.services.analysis_service import analysis_service

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("", response_model=list[DocumentSummary], summary="List documents")
def list_documents(user: CurrentUser) -> list[DocumentSummary]:
    """Retrieve lightweight metadata for all canonical national security documents."""
    return analysis_service.list_documents()


@router.get("/{document_id}", response_model=DocumentDetail, summary="Get document details")
def get_document(document_id: str, user: CurrentUser) -> DocumentDetail:
    """Retrieve full analytical metadata, category metrics, and rankings for a document."""
    doc = analysis_service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )
    return doc


@router.get(
    "/{document_id}/categories/{category}",
    response_model=CategorySummary,
    summary="Get category metrics",
)
def get_category_metrics(
    document_id: str,
    category: str,
    user: CurrentUser,
) -> CategorySummary:
    """Retrieve category-level metrics (frequency, raw mentions, segment hits, review required)."""
    cat_summary = analysis_service.get_category(document_id, category)
    if not cat_summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{category}' not found for document '{document_id}'.",
        )
    return cat_summary


@router.get(
    "/{document_id}/categories/{category}/passages",
    response_model=PassageListResponse,
    summary="Get grouped passage items",
)
def get_passages(
    document_id: str,
    category: str,
    user: CurrentUser,
    show_review_only: bool = Query(
        False, description="Show only matches requiring human review"
    ),
    include_review_only: bool = Query(
        False, description="Include review-only matches alongside baseline"
    ),
) -> PassageListResponse:
    """Retrieve passages grouped by segment_id with individual constituent match traceability."""
    passages = analysis_service.get_passages(
        document_id=document_id,
        category=category,
        show_review_only=show_review_only,
        include_review_only=include_review_only,
    )
    if not passages:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Passages not found for document '{document_id}' and category '{category}'.",
        )
    return passages

