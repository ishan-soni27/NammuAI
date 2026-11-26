"""Shared test setup.

Isolation first: tests must never touch the real Supabase database by accident, even if
`backend/.env` holds a real DATABASE_URL. Environment variables beat the .env file in
pydantic-settings, so we pin safe values here *before* any app module is imported.
Tests that need a real database (Phase 4) use DATABASE_URL_TEST explicitly.
"""

from __future__ import annotations

import os

os.environ["DATABASE_URL"] = ""
os.environ["AS_OF_DATE"] = "2026-11-16"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"
os.environ["APP_ENV"] = "test"
os.environ["LOG_LEVEL"] = "WARNING"

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config.business_rules import get_business_rules  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.db.session import _default_engine, get_sessionmaker  # noqa: E402


def clear_config_caches() -> None:
    """Forget cached settings/rules/engine so the next call re-reads the environment."""
    for cached in (get_settings, get_business_rules, _default_engine, get_sessionmaker):
        cached.cache_clear()


@pytest.fixture(autouse=True)
def _fresh_config() -> Iterator[None]:
    """Each test starts (and ends) with caches cleared, so env changes can't leak."""
    clear_config_caches()
    yield
    clear_config_caches()


@pytest.fixture
def app() -> FastAPI:
    """A freshly built app (not the module-level one), so overrides stay per-test."""
    from app.main import create_app

    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
