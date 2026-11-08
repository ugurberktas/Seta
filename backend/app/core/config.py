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


def _load_env_file() -> None:
    """Load key-value pairs from .env into os.environ if not already set."""
    env_file = REPO_ROOT / ".env"
    if not env_file.is_file():
        return
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


_load_env_file()


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
        or os.environ.get("RENDER", "").lower() == "true"
    )
    COOKIE_SAMESITE: str = "lax"


settings = Settings()

