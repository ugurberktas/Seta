"""
backend.app.api.health
----------------------
Public health check endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health check")
def health_check() -> dict[str, str]:
    """Return application operational status."""
    return {"status": "ok"}

