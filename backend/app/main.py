"""FastAPI application factory. Run with: `uvicorn app.main:app --reload`.

Purpose
    Wires everything together: JSON logging, request-context middleware, CORS, the error
    envelope and the /api/v1 routers. Contains no business logic.

Middleware order (it matters)
    Starlette runs the LAST-added middleware FIRST. We add RequestContextMiddleware first
    and CORSMiddleware second, so a request flows:
        CORS → RequestContext (request id, timing, 500 safety net) → routes
    That way every response, including a crash turned into a 500 envelope, carries CORS
    headers, and the browser shows our message instead of "CORS error" (§16).

How to change this
    New router: add it in `app/api/v1/__init__.py`, not here.
    New allowed web origin: set CORS_ORIGINS in the Vercel API project (comma-separated), no code change.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.config.business_rules import get_business_rules
from app.config.settings import get_settings
from app.errors import install_error_handlers
from app.logging_setup import configure_logging, redact_database_url
from app.middleware import RequestContextMiddleware

logger = logging.getLogger("app")

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    """Build a configured app. Tests call this to get a fresh instance."""
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        rules = get_business_rules()
        # Never log the full connection string (it contains the password).
        logger.info(
            "api starting",
            extra={
                "as_of": rules.as_of_date.isoformat(),
                "rules_fingerprint": rules.fingerprint(),
                "database": redact_database_url(settings.database_url),
                "cors_origins": settings.cors_origin_list,
                "app_env": settings.app_env,
            },
        )
        yield
        logger.info("api stopping")

    app = FastAPI(
        title="Kestrel Bay ordering API",
        version="0.1.0",
        description=(
            "Answers Dana's two Monday questions: what will run out before a new order "
            "can arrive, and what is she stuck with. All business dates use AS_OF_DATE."
        ),
        lifespan=lifespan,
        # Under /api/v1 because the site root belongs to the website (one Vercel project, ADR-002).
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
        redoc_url=None,
    )

    install_error_handlers(app)

    # Order matters; see module docstring.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Actor", "X-Request-ID"],
        expose_headers=["X-Request-ID"],  # so the UI can show the reference id on errors
    )

    app.include_router(api_router, prefix=API_PREFIX)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        """A friendly landing response for anyone opening the bare API URL."""
        return {
            "service": "Kestrel Bay ordering API",
            "docs": f"{API_PREFIX}/docs",
            "health": f"{API_PREFIX}/health",
        }

    return app


app = create_app()
