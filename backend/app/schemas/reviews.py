"""
backend.app.schemas.reviews
---------------------------
Request and response schemas for review decision endpoints.
"""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class ReviewDecisionRequest(BaseModel):
    status: Literal["relevant", "irrelevant"] = Field(
        ..., description="Review status decision: 'relevant' or 'irrelevant'"
    )


class ReviewDecisionResponse(BaseModel):
    document_id: str
    category: str
    segment_id: str
    status: str
    updated_at: str


class DocumentReviewsResponse(BaseModel):
    document_id: str
    total_reviews: int
    reviews: dict[str, dict]

