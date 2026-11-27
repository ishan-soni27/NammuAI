"""Environment configuration (infrastructure only, no business rules).

Purpose
    One typed place for everything that differs between a laptop, Vercel and the test
    suite: the database URL, CORS origins, log level and an optional override of the business
    "today" (AS_OF_DATE). Values come from environment variables or `backend/.env`.

How it fits
    `get_settings()` is cached and used by `main.py`, `db/session.py`, the loader CLI and
    FastAPI dependencies. Business numbers (lead times, thresholds) live in
    `business_rules.py`, NOT here. This file is about *where* things run, not *how the
    business works*.

Key decisions
    - "Today" is Boston's calendar date (ADR-034, config/clock.py). AS_OF_DATE is only an
      explicit override, for tests and a fixed demo; blank or unset = the real calendar. Code
      must never call `date.today()` for business logic (invariant #1): the clock is read in
      config/clock.py only.
    - Supabase hands out `postgresql://` URLs. SQLAlchemy needs `postgresql+psycopg://` to
      pick the psycopg 3 driver, so we normalize it here rather than make Ishan edit the
      string by hand (a classic "works locally, broken in production" trap).

How to change this
    Add a new env var: add a typed field below (with a default if it is optional), document
    it in `backend/.env.example`, and set it in the Vercel API project (Settings → Environment Variables).
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ (this file is backend/app/config/settings.py)
BACKEND_DIR = Path(__file__).resolve().parents[2]
# Repo root, where data/raw and data/reference live.
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Typed environment settings. Field names match env var names (case-insensitive)."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Vercel injects many unrelated env vars; ignore them.
    )

    # Empty string means "not configured". The API still boots, and /health reports
    # db = "not_configured", so a missing secret is visible instead of a crash loop.
    database_url: str = ""

    # Override of the business "today" (blank = follow the data). See module docstring.
    as_of_date: date | None = None

    # Comma-separated in the environment, e.g. "https://kestrel.vercel.app,http://localhost:5173".
    cors_origins: str = "http://localhost:5173"

    log_level: str = "INFO"

    # "production" hides exception details from error responses (they still go to logs).
    app_env: str = "local"

    # Git commit of the running code, shown in /health and recorded on load runs.
    # Vercel sets VERCEL_GIT_COMMIT_SHA automatically; GIT_COMMIT works anywhere else.
    git_commit: str = Field(default="", validation_alias=AliasChoices("VERCEL_GIT_COMMIT_SHA", "GIT_COMMIT"))

    # Vercel sets VERCEL=1 inside its functions. We use it to size the DB pool (see db/session.py).
    vercel: str = ""

    @field_validator("as_of_date", mode="before")
    @classmethod
    def _blank_means_follow_the_data(cls, value: object) -> object:
        """AS_OF_DATE= (blank) is the same as not set: "today" follows the latest load."""
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("database_url")
    @classmethod
    def _use_psycopg3_driver(cls, value: str) -> str:
        """Rewrite `postgres://` / `postgresql://` to `postgresql+psycopg://`.

        Example: "postgresql://u:p@host:5432/postgres" -> "postgresql+psycopg://u:p@host:5432/postgres".
        Other schemes (e.g. "sqlite://" in tests) pass through unchanged.
        """
        value = value.strip()
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a list, ignoring blanks and trailing slashes.

        Browsers send the Origin header without a trailing slash, so
        "https://x.vercel.app/" would silently never match. We strip it.
        """
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def is_serverless(self) -> bool:
        """True when running as a Vercel serverless function (ADR-002)."""
        return self.vercel == "1"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings (read once, then cached).

    Tests that need different values call `get_settings.cache_clear()` after
    changing the environment (see tests/conftest.py).
    """
    return Settings()
