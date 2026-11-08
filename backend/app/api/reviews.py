"""
backend.app.api.reviews
-----------------------
Human review decision endpoints backed by PostgreSQL.
All endpoints require authentication.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, status

logger = logging.getLogger("sra_reviews")

from backend.app.core.rate_limit import rate_limiter
from backend.app.core.security import CurrentUser
from backend.app.schemas.reviews import (
    DocumentReviewsResponse,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
)
from backend.app.services.analysis_service import analysis_service
from backend.app.services.review_service import ReviewServiceError, review_service

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.get(
    "/{document_id}",
    response_model=DocumentReviewsResponse,
    summary="Get document reviews",
)
def get_document_reviews(document_id: str, user: CurrentUser) -> DocumentReviewsResponse:
    """Retrieve all stored review decisions for a document from PostgreSQL."""
    if not analysis_service.is_canonical_document(document_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    try:
        data = review_service.load_document_reviews(document_id)
        reviews_dict = data.get("reviews", {})
        return DocumentReviewsResponse(
            document_id=document_id,
            total_reviews=len(reviews_dict),
            reviews=reviews_dict,
        )
    except ReviewServiceError as exc:
        logger.error("Failed to load reviews for document %s: %s", document_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review storage service unavailable. Please try again later.",
        ) from exc


@router.put(
    "/{document_id}/{category}/{segment_id}",
    response_model=ReviewDecisionResponse,
    summary="Set passage review decision",
)
def set_passage_review(
    document_id: str,
    category: str,
    segment_id: str,
    payload: ReviewDecisionRequest,
    user: CurrentUser,
) -> ReviewDecisionResponse:
    """Record or update a passage review decision ('relevant' or 'irrelevant') in PostgreSQL."""
    # 1. Validate inputs
    if not analysis_service.is_canonical_document(document_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )
    if not analysis_service.is_valid_category(document_id, category):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{category}' not found for document '{document_id}'.",
        )
    if not segment_id or not segment_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="segment_id cannot be empty.",
        )

    # 2. Enforce rate limit (30 mutations per 60s per authenticated user)
    rate_limiter.check_review_mutation_rate(session_key=user)

    # 3. Persist decision
    try:
        res = review_service.set_review(
            document_id=document_id,
            category=category,
            segment_id=segment_id.strip(),
            status=payload.status,
        )
        return ReviewDecisionResponse(**res)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ReviewServiceError as exc:
        logger.error("Failed to load reviews for document %s: %s", document_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review storage service unavailable. Please try again later.",
        ) from exc


@router.delete(
    "/{document_id}/{category}/{segment_id}",
    summary="Clear passage review decision",
)
def clear_passage_review(
    document_id: str,
    category: str,
    segment_id: str,
    user: CurrentUser,
) -> dict[str, str]:
    """Delete a passage review decision from PostgreSQL (absence = unreviewed)."""
    # 1. Validate inputs
    if not analysis_service.is_canonical_document(document_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )
    if not analysis_service.is_valid_category(document_id, category):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{category}' not found for document '{document_id}'.",
        )
    if not segment_id or not segment_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="segment_id cannot be empty.",
        )

    # 2. Enforce rate limit (30 mutations per 60s per authenticated user)
    rate_limiter.check_review_mutation_rate(session_key=user)

    # 3. Clear decision
    try:
        return review_service.clear_review(
            document_id=document_id,
            category=category,
            segment_id=segment_id.strip(),
        )
    except ReviewServiceError as exc:
        logger.error("Failed to load reviews for document %s: %s", document_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review storage service unavailable. Please try again later.",
        ) from exc


