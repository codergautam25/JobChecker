"""Application configuration via pydantic-settings.

All settings are loaded from environment variables or a .env file.
Paths are relative to the project root unless absolute.
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _project_root() -> Path:
    """Resolve the project root (directory containing pyproject.toml)."""
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return current


PROJECT_ROOT = _project_root()


class Settings(BaseSettings):
    """Central configuration for the Career Tracker application.

    Values are read from environment variables first, then from a .env
    file located at the project root.
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────────────────
    openai_api_key: str = Field(default="", description="OpenAI (or compatible) API key")
    openai_api_base: str = Field(
        default="https://api.openai.com/v1",
        description="Base URL for the OpenAI-compatible API",
    )
    llm_model: str = Field(default="gpt-4o-mini", description="Model name for completions")
    llm_temperature: float = Field(default=0.3, ge=0.0, le=2.0)

    # ── Gmail ────────────────────────────────────────────────────────────
    gmail_credentials_path: Path = Field(default=Path("data/credentials.json"))
    gmail_token_path: Path = Field(default=Path("data/token.json"))
    gmail_scopes: list[str] = Field(
        default=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.modify",
        ]
    )

    # ── Storage ──────────────────────────────────────────────────────────
    db_path: Path = Field(default=Path("data/career_tracker.db"))
    chroma_path: Path = Field(default=Path("data/chroma"))
    resumes_dir: Path = Field(default=Path("data/resumes"))
    cover_letters_dir: Path = Field(default=Path("data/cover_letters"))
    attachments_dir: Path = Field(default=Path("data/attachments"))
    logs_dir: Path = Field(default=Path("data/logs"))

    # ── Workflow ─────────────────────────────────────────────────────────
    email_poll_interval_seconds: int = Field(default=300, ge=30)
    email_lookback_hours: int = Field(default=24, ge=1, le=720,
        description="How many hours back to scan for emails on each run")
    max_retries: int = Field(default=3, ge=1)
    classification_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    # ── Embedding ────────────────────────────────────────────────────────
    embedding_model: str = Field(default="all-MiniLM-L6-v2")
    
    # ── UI ───────────────────────────────────────────────────────────────
    ui_cache_ttl_seconds: int = Field(default=60, ge=1, le=3600,
        description="Time-to-live for UI cache queries in seconds")

    # ── Helpers ──────────────────────────────────────────────────────────

    def resolve_path(self, path: Path) -> Path:
        """Resolve a potentially relative path against the project root."""
        if path.is_absolute():
            return path
        return PROJECT_ROOT / path

    def ensure_directories(self) -> None:
        """Create all required data directories if they don't exist."""
        for dir_path in [
            self.resumes_dir,
            self.cover_letters_dir,
            self.attachments_dir,
            self.logs_dir,
            self.chroma_path,
        ]:
            resolved = self.resolve_path(dir_path)
            resolved.mkdir(parents=True, exist_ok=True)

        # Ensure parent directory of the database exists
        self.resolve_path(self.db_path).parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    settings = Settings()
    settings.ensure_directories()
    return settings
