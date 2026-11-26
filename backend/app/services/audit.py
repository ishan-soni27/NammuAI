"""Audit trail and event log writers (logging layers 3 and 1, BUILD_PROMPT §10, ADR-010).

Audit rule: every change Dana makes (lead times, PO dates, handled notes, item settings) adds an
`audit_log` row IN THE SAME DATABASE SESSION as the change, before the commit. They succeed or fail
together, so there is never a change without its record, or a record of a change that didn't happen.

Who: the X-Actor header (default "Dana", no login in v1, ADR-011), read from the request context.
When: real UTC time (log timestamps use the clock; business dates use AS_OF, invariant #1).

How to change this: a new editable thing calls `record_change(...)` with before/after dicts.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.db.models import AuditLog, EventLog, RequestLog
from app.db.session import DatabaseNotConfiguredError, get_engine
from app.logging_setup import DEFAULT_ACTOR, actor_var, request_id_var

logger = logging.getLogger(__name__)


def jsonable(value: Any) -> Any:
    """Make dates and Decimals JSON-safe for the before/after columns."""
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def current_actor() -> str:
    return actor_var.get() or DEFAULT_ACTOR


def record_change(
    session: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> None:
    """Add an audit row to the caller's session. The caller commits (same transaction)."""
    session.add(
        AuditLog(
            actor=current_actor(),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=jsonable(before) if before is not None else None,
            after=jsonable(after) if after is not None else None,
            request_id=request_id_var.get(),
        )
    )
    logger.info("audited change", extra={"action": action, "entity": f"{entity_type}:{entity_id}"})


def record_event(session: Session, *, level: str, source: str, event: str, details: dict[str, Any]) -> None:
    """Add an event_log row (notable events and errors) to the caller's session."""
    session.add(
        EventLog(
            level=level,
            source=source,
            event=event,
            request_id=request_id_var.get(),
            details=jsonable(details),
        )
    )


def write_request_log(row: dict[str, Any]) -> None:
    """Store one request_log row in its own short transaction. Never raises.

    Called by the middleware after the response has been sent, in a worker thread, so a slow or
    unavailable database never slows down or breaks Dana's request.
    """
    try:
        engine = get_engine()
    except DatabaseNotConfiguredError:
        return
    try:
        with engine.begin() as conn:
            conn.execute(insert(RequestLog.__table__).values(**row))
    except Exception:  # noqa: BLE001 - logging must never break the app
        logger.warning("could not write request_log", exc_info=True)


def write_error_event(details: dict[str, Any]) -> None:
    """Store an unexpected server error in event_log (best effort, own transaction)."""
    try:
        with get_engine().begin() as conn:
            conn.execute(
                insert(EventLog.__table__).values(
                    level="ERROR",
                    source="api",
                    event="unhandled_error",
                    request_id=details.get("request_id"),
                    details=jsonable(details),
                )
            )
    except Exception:  # noqa: BLE001
        logger.warning("could not write error event", exc_info=True)
