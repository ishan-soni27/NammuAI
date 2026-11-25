"""The one error shape every API failure uses (BUILD_PROMPT §8.5).

Purpose
    Whatever goes wrong, the frontend gets the same JSON:
        {"error": {"code": "not_found", "message": "We couldn't find item XYZ.", "request_id": "3f2c..."}}
    `message` is plain English that can be shown to Dana as is. `request_id` is the
    "reference id" the UI shows, so Ishan can find the matching log lines on Render.

How it fits
    - Code raises `AppError(...)` for expected problems (unknown item, bad date, etc.).
    - `install_error_handlers(app)` converts AppError, HTTP errors (404/405...) and request
      validation errors into the envelope.
    - Truly unexpected exceptions are caught one level up, in `middleware.py`. That is on
      purpose: a FastAPI handler for `Exception` runs *outside* the CORS middleware, so the
      browser would see a CORS failure instead of our message. The middleware sits inside
      CORS, so even a 500 reaches the UI readable.

How to change this
    New error type: raise `AppError(status_code=409, code="conflict", message="...")`.
    There is no need to register anything.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_setup import request_id_var


class AppError(Exception):
    """An expected failure with a plain-English message for Dana.

    Example: raise AppError(404, "item_not_found", "We couldn't find item SHR-9999.")
    """

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


# Friendly defaults for HTTP errors that FastAPI/Starlette raise themselves.
_HTTP_MESSAGES: dict[int, tuple[str, str]] = {
    400: ("bad_request", "That request didn't make sense to the server."),
    404: ("not_found", "We couldn't find that page or record."),
    405: ("method_not_allowed", "That action isn't allowed here."),
    429: ("too_many_requests", "Too many requests. Please wait a moment and try again."),
}
# FastAPI/Starlette's own default detail strings, which we replace with the messages above.
_GENERIC_DETAILS = {"Not Found", "Method Not Allowed", "Bad Request", "Too Many Requests"}


def error_response(
    status_code: int,
    code: str,
    message: str,
    request_id: str | None = None,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    """Build the standard error envelope.

    `details` is optional and used only for validation errors (which field was wrong).
    """
    body: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": request_id or request_id_var.get(),
    }
    if details:
        body["details"] = details
    return JSONResponse(status_code=status_code, content={"error": body})


def install_error_handlers(app: FastAPI) -> None:
    """Register the handlers that turn exceptions into the error envelope."""

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, default_message = _HTTP_MESSAGES.get(
            exc.status_code, ("http_error", "The server couldn't complete that request.")
        )
        # Keep a custom detail string, but replace FastAPI's generic ones ("Not Found") with ours.
        has_custom_detail = isinstance(exc.detail, str) and exc.detail not in _GENERIC_DETAILS
        message = exc.detail if has_custom_detail else default_message
        return error_response(exc.status_code, code, message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(p) for p in err.get("loc", ()) if p != "body"),
                "problem": err.get("msg", ""),
            }
            for err in exc.errors()
        ]
        first = details[0] if details else {"field": "", "problem": ""}
        message = (
            f"Please check '{first['field']}': {first['problem']}."
            if first["field"]
            else "Some of the information sent was not valid."
        )
        return error_response(422, "invalid_request", message, details=details)
