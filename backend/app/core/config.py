"""
backend.app.core.config
-----------------------
Application configuration loaded exclusively from environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path


# Repository root (3 levels up from backend/app/core)
REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DATA_DIR = REPO_ROOT / "data" / "processed"


class Settings:
    PROJECT_NAME: str = "Security Research Assistant API"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"

    @property
    def APP_USERNAME(self) -> str | None:
        val = os.environ.get("APP_USERNAME")
        return val.strip() if val else None

    @property
    def APP_PASSWORD(self) -> str | None:
        val = os.environ.get("APP_PASSWORD")
        return val if val else None

    @property
    def SESSION_SECRET(self) -> str | None:
        val = os.environ.get("SESSION_SECRET")
        return val.strip() if val else None

    @property
    def DATABASE_URL(self) -> str | None:
        val = os.environ.get("DATABASE_URL")
        return val.strip() if val else None

    @property
    def FRONTEND_ORIGIN(self) -> str | None:
        val = os.environ.get("FRONTEND_ORIGIN")
        return val.strip() if val else None

    @property
    def ALLOWED_ORIGINS(self) -> list[str]:
        origins: list[str] = []
        if self.FRONTEND_ORIGIN:
            origins.append(self.FRONTEND_ORIGIN)
        # Default development and local origins (never "*")
        origins.extend([
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ])
        # Return deduplicated list
        return list(dict.fromkeys(origins))

    COOKIE_NAME: str = "sra_session"
    COOKIE_MAX_AGE: int = 14 * 24 * 3600  # 14 days
    COOKIE_SECURE: bool = (
        os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower() == "production"
    )
    COOKIE_SAMESITE: str = "lax"


settings = Settings()

