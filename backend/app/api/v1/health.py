"""GET /api/v1/health: is the API up, can it reach the database, what is "today"?

Always answers 200 (see services/health_service.py for why). `status` says whether
everything is fine. Also accepts HEAD, because uptime monitors (the keep-warm ping, §15)
often send HEAD requests, and a 405 would look like an outage.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.schemas import HealthResponse
from app.config.business_rules import BusinessRules, get_business_rules
from app.config.settings import Settings, get_settings
from app.services.health_service import DatabaseHealth, check_database

router = APIRouter(tags=["health"])


def get_database_health() -> DatabaseHealth:
    """Dependency wrapper so tests can swap in a fake DB result (app.dependency_overrides)."""
    return check_database()


@router.api_route("/health", methods=["GET", "HEAD"], response_model=HealthResponse)
def health(
    db_health: DatabaseHealth = Depends(get_database_health),
    rules: BusinessRules = Depends(get_business_rules),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Report API and database health plus the business date."""
    healthy = db_health.db == "ok" and db_health.schema_ready
    return HealthResponse(
        status="ok" if healthy else "degraded",
        db=db_health.db,
        schema_ready=db_health.schema_ready,
        as_of=rules.as_of_date,
        last_load_at=db_health.last_load_at,
        version=(settings.render_git_commit[:7] or "local"),
    )
