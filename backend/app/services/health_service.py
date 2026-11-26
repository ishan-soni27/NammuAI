"""Health check logic: can we reach the database, and when was data last loaded?

Purpose
    Backs `GET /api/v1/health`, which serves three audiences:
      - uptime checks (is the API up?),
      - the daily Vercel cron in backend/vercel.json (it touches the DB, which stops Supabase's
        free tier from pausing the project after a week idle, §15),
      - the web app, which shows "Data as of ..." and a friendly message if the DB is down.

Key decision
    This never raises. A database problem is reported as `db = "down"` instead of an
    exception. The endpoint can then always answer 200, and the UI can say exactly what is
    wrong ("the database isn't responding") instead of a generic failure.

How to change this
    Add a check (e.g. "is the latest load older than a week?"): extend `DatabaseHealth`
    and compute it in `check_database`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from sqlalchemy import select, text
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError

from app.db.models import LoadRun
from app.db.session import DatabaseNotConfiguredError, get_engine

logger = logging.getLogger(__name__)

DbState = Literal["ok", "down", "not_configured"]


@dataclass(frozen=True)
class DatabaseHealth:
    db: DbState
    schema_ready: bool  # False until `alembic upgrade head` has run
    last_load_at: datetime | None  # finish time of the latest successful load run
    snapshot_date: date | None = None  # its BlueTide stock count date ("today" is the day after)


def check_database() -> DatabaseHealth:
    """Ping the database and read the latest successful load time. Never raises."""
    try:
        engine = get_engine()
    except DatabaseNotConfiguredError:
        return DatabaseHealth(db="not_configured", schema_ready=False, last_load_at=None)

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            try:
                latest = conn.execute(
                    select(LoadRun.finished_at, LoadRun.summary)
                    .where(LoadRun.status == "succeeded")
                    .order_by(LoadRun.id.desc())
                    .limit(1)
                ).first()
            except ProgrammingError:
                # Connected, but the tables don't exist yet (migrations not run).
                logger.warning("database reachable but schema missing; run `alembic upgrade head`")
                return DatabaseHealth(db="ok", schema_ready=False, last_load_at=None)
    except SQLAlchemyError:
        logger.warning("database check failed", exc_info=True)
        return DatabaseHealth(db="down", schema_ready=False, last_load_at=None)

    if latest is None:
        return DatabaseHealth(db="ok", schema_ready=True, last_load_at=None)
    snapshot = (latest.summary or {}).get("snapshot_date")
    return DatabaseHealth(
        db="ok",
        schema_ready=True,
        last_load_at=latest.finished_at,
        snapshot_date=date.fromisoformat(snapshot) if snapshot else None,
    )
