"""GET /api/v1/health: is the API up, can it reach the database, what is "today"?

Always answers 200 (see services/health_service.py for why). `status` says whether
everything is fine. Also accepts HEAD, because uptime monitors (the keep-warm ping, §15)
often send HEAD requests, and a 405 would look like an outage.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.schemas import HealthResponse
from app.config.business_rules import rules_for, server_today
from app.config.settings import Settings, get_settings
from app.services.health_service import DatabaseHealth, check_database

router = APIRouter(tags=["health"])


def get_database_health() -> DatabaseHealth:
    """Dependency wrapper so tests can swap in a fake DB result (app.dependency_overrides)."""
    return check_database()


@router.get("/health", response_model=HealthResponse)
@router.head("/health", include_in_schema=False)  # uptime monitors; one documented operation only
def health(
    db_health: DatabaseHealth = Depends(get_database_health),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Report API and database health, today's business date (Boston), and how old the stock count is.

    Health never opens a request session, so it still answers when the database is down.
    """
    rules = rules_for(db_health.snapshot_date, server_today())
    healthy = db_health.db == "ok" and db_health.schema_ready
    return HealthResponse(
        status="ok" if healthy else "degraded",
        db=db_health.db,
        schema_ready=db_health.schema_ready,
        as_of=rules.as_of_date,
        snapshot_date=db_health.snapshot_date,
        data_date=rules.data_date if db_health.snapshot_date else None,
        days_since_count=(rules.as_of_date - db_health.snapshot_date).days
        if db_health.snapshot_date
        else None,
        stale_after_days=rules.stale_data_days,
        very_stale_after_days=rules.very_stale_data_days,
        last_load_at=db_health.last_load_at,
        version=(settings.git_commit[:7] or "local"),
    )
