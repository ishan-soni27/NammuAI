"""Structured JSON logging (logging layer 1 of 4, BUILD_PROMPT §10 / ADR-010).

Purpose
    Every log line is one JSON object on stdout, so Render's log viewer (and any log tool
    later) can filter by request_id, actor or event. Example line:
    {"timestamp": "2026-11-25T12:00:00.123+00:00", "level": "INFO", "logger": "app.request",
     "message": "request finished", "request_id": "3f2c...", "actor": "Dana",
     "method": "GET", "path": "/api/v1/health", "status": 200, "duration_ms": 4.1}

How it fits
    `middleware.py` sets the request id and actor in context variables at the start of
    each request. `ContextFilter` copies them onto every log record made while that
    request runs, so code deep in the planning service gets them for free.

Key decisions
    - stdlib `logging` + python-json-logger: boring and well known, no extra framework.
    - Log timestamps are real UTC time. Business dates use AS_OF_DATE (invariant #1).
    - uvicorn's own access log is silenced because our middleware writes a richer one
      (with request_id, actor and duration). That avoids two lines per request.
    - Never log secrets. Use `redact_database_url()` when mentioning the database.

How to change this
    Add a field to every line: set it in a contextvar (like `request_id_var`) and copy it
    in `ContextFilter.filter`. Add a field to one line: `logger.info("msg", extra={...})`.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from urllib.parse import urlsplit

from pythonjsonlogger.json import JsonFormatter

# Context for the current request. Defaults apply outside a request (loader CLI, startup).
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
actor_var: ContextVar[str | None] = ContextVar("actor", default=None)


class ContextFilter(logging.Filter):
    """Attach the current request_id and actor to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.actor = actor_var.get()
        return True


def configure_logging(level: str = "INFO") -> None:
    """Send all logs (ours, uvicorn's, SQLAlchemy's) through one JSON handler on stdout.

    Safe to call more than once (tests create several apps): it replaces handlers
    instead of stacking them, so lines are never duplicated.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter(
            "%(levelname)s %(name)s %(message)s %(request_id)s %(actor)s",
            rename_fields={"levelname": "level", "name": "logger"},
            timestamp=True,  # adds "timestamp" in UTC ISO-8601
        )
    )
    handler.addFilter(ContextFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    # uvicorn installs its own handlers; route them through ours instead.
    for name in ("uvicorn", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True
    # Our middleware logs every request with more detail; silence the duplicate.
    logging.getLogger("uvicorn.access").disabled = True
    # HTTP client libraries (used by the test client) log every call at INFO; keep them quiet.
    for name in ("httpx", "httpx2", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


def redact_database_url(url: str) -> str:
    """Return only the driver, host and database of a connection string, never the password.

    Example: "postgresql+psycopg://postgres.abc:secret@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
             -> "postgresql+psycopg://aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    """
    if not url:
        return "<not configured>"
    parts = urlsplit(url)
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{host}{port}{parts.path}"
