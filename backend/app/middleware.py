"""Per-request context: request id, actor, timing, request log, last-resort error handling.

Purpose
    For every HTTP request this middleware:
      1. assigns a request id (reuses a safe incoming `X-Request-ID`, otherwise a new one),
      2. reads who is acting from `X-Actor` (default "Dana"; there is no auth in v1, ADR-011),
      3. puts both in context variables so every log line and audit row can carry them,
      4. returns the id to the browser as the `X-Request-ID` response header,
      5. logs one structured "request finished" line with method, path, status, duration,
      6. turns any unexpected exception into the standard 500 error envelope.

How it fits
    Logging layer 1 (BUILD_PROMPT §10). Phase 4 adds a background write of the same fields
    to the `request_log` table, hooked in at `_log_request`.

Key decisions
    - Pure ASGI middleware rather than `BaseHTTPMiddleware`: it is faster, and context
      variables set here are reliably visible inside endpoints.
    - It must be added *before* CORSMiddleware in `main.py` (Starlette runs the last-added
      middleware first). CORS therefore wraps this, and even our 500 responses carry CORS
      headers. Otherwise the browser reports a confusing CORS error instead of our message.

How to change this
    New per-request field (e.g. a tenant id): read it from `headers` below, store it in a
    contextvar in `logging_setup.py`, and add it to `_log_request`.
"""

from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.errors import error_response
from app.logging_setup import actor_var, request_id_var

logger = logging.getLogger("app.request")

DEFAULT_ACTOR = "Dana"  # BUILD_PROMPT §8.5: X-Actor defaults to "Dana"
_MAX_ACTOR_LEN = 80
# Accept a caller's request id only if it is short and harmless (it ends up in logs).
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def clean_actor(raw: str | None) -> str:
    """Normalize the X-Actor header: trimmed, single-spaced, at most 80 chars, default "Dana".

    Examples: None -> "Dana"; "  ishan  " -> "ishan"; "" -> "Dana".
    """
    if not raw:
        return DEFAULT_ACTOR
    cleaned = " ".join(raw.split())[:_MAX_ACTOR_LEN]
    return cleaned or DEFAULT_ACTOR


def clean_request_id(raw: str | None) -> str:
    """Reuse a safe incoming request id (so frontend and backend logs share it), else make one."""
    if raw and _SAFE_REQUEST_ID.match(raw):
        return raw
    return uuid.uuid4().hex


class RequestContextMiddleware:
    """See module docstring."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":  # lifespan / websockets pass straight through
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = clean_request_id(headers.get("x-request-id"))
        actor = clean_actor(headers.get("x-actor"))
        rid_token = request_id_var.set(request_id)
        actor_token = actor_var.set(actor)

        start = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            # Stack trace goes to the logs; Dana sees a plain message plus the reference id.
            logger.exception(
                "unhandled error",
                extra={"method": scope.get("method"), "path": scope.get("path")},
            )
            if response_started:  # too late to send a clean error; let the server close it
                raise
            response = error_response(
                500,
                "internal_error",
                "Something went wrong on our side. Please try again. If it keeps "
                "happening, share the reference id with Ishan.",
                request_id=request_id,
            )
            await response(scope, receive, send_with_request_id)
        finally:
            _log_request(scope, status_code, (time.perf_counter() - start) * 1000)
            request_id_var.reset(rid_token)
            actor_var.reset(actor_token)


def _log_request(scope: Scope, status: int, duration_ms: float) -> None:
    """One structured line per request (request_id and actor are added by ContextFilter).

    Phase 4: also queue a `request_log` row here.
    """
    level = logging.WARNING if status >= 500 else logging.INFO
    logger.log(
        level,
        "request finished",
        extra={
            "method": scope.get("method"),
            "path": scope.get("path"),
            "status": status,
            "duration_ms": round(duration_ms, 1),
        },
    )
