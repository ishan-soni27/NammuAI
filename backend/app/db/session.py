"""Database engine and sessions (SQLAlchemy 2, psycopg 3, Supabase Postgres).

Purpose
    One lazily created engine per process, plus a `get_db` FastAPI dependency that hands
    each request its own session and always closes it.

Key decisions
    - Lazy: the app can boot (and /health can say "not_configured") even if DATABASE_URL
      is missing, so a missing secret in production is obvious instead of a crash loop.
    - Small pool. On Vercel (serverless, ADR-002) many function instances may run at once,
      each with its own pool, so each keeps at most 1 + 2 connections, and the deployed
      DATABASE_URL uses Supabase's *transaction* pooler (port 6543), which multiplexes them.
      Locally (one process) the pool is 5 + 5 against the session pooler (port 5432).
    - `pool_pre_ping`: Supabase's pooler drops idle connections, and an idle serverless
      instance can be frozen between requests. Pre-ping replaces a dead connection instead of
      failing the first request after a quiet spell.
    - `connect_timeout=5`: if the database is paused or unreachable, /health answers in
      seconds instead of hanging until the browser gives up.
    - `prepare_threshold=None` turns off psycopg's server-side prepared statements. They
      break behind Supabase's *transaction* pooler (port 6543). We use the session pooler
      (5432), but this makes either URL work at no noticeable cost at our scale.
    - All access goes through this backend (RLS is on with no policies, ADR-015).

How to change this
    Pool sizes: edit `create_engine` below. A second database (e.g. tests): pass a URL to
    `make_engine(url)`.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config.settings import get_settings


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when code needs the database but DATABASE_URL is empty."""


def make_engine(url: str, *, pooled: bool = True) -> Engine:
    """Create an engine with the settings described in the module docstring.

    `pooled=False` opens a fresh connection per use and keeps none around. Used by
    one-off processes (migrations, the loader CLI) so they don't hold pooler slots.
    """
    if not url:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL is not set. Copy backend/.env.example to backend/.env and fill it in."
        )
    connect_args: dict[str, object] = {}
    if url.startswith("postgresql"):
        connect_args = {"connect_timeout": 5, "prepare_threshold": None}
    if not pooled:
        return create_engine(url, poolclass=NullPool, connect_args=connect_args)
    serverless = get_settings().is_serverless
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=1 if serverless else 5,
        max_overflow=2 if serverless else 5,
        pool_recycle=300,  # seconds; recycle before the pooler's idle timeout
        connect_args=connect_args,
    )


@lru_cache
def get_engine() -> Engine:
    """The process-wide engine, created on first use."""
    return make_engine(get_settings().database_url)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    # expire_on_commit=False: objects stay readable after commit (handy when building responses).
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed.

    Endpoints that write call `db.commit()` themselves, so the change and its audit row
    commit together in one transaction (BUILD_PROMPT §10, layer 3).
    """
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
