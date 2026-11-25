"""Response and request models for /api/v1 (Pydantic v2).

Purpose
    The API's public shapes in one file, so the frontend's TypeScript types
    (`frontend/src/api/types.ts`) have one place to mirror. These models also generate the
    OpenAPI docs at /docs.

Naming
    Fields that reach the UI use Dana's words where it matters (`order_at_least`,
    `on_hold_qty`, `stuck_tags`, BUILD_PROMPT §12).

How to change this ("show a new number on the dashboard", §17)
    Engine output (`planning/types.py`) → add the field here → map it in the service →
    add it to `frontend/src/api/types.ts` → render it.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """GET /api/v1/health."""

    status: Literal["ok", "degraded"] = Field(
        description="'ok' when the database is reachable and migrated, otherwise 'degraded'."
    )
    db: Literal["ok", "down", "not_configured"]
    schema_ready: bool = Field(description="False until database migrations have been run.")
    as_of: date = Field(description="The business 'today' (AS_OF_DATE), never the server clock.")
    last_load_at: datetime | None = Field(
        description="When BlueTide data was last loaded successfully (UTC). Null before the first load."
    )
    version: str = Field(description="Short git commit of the running API, or 'local'.")
