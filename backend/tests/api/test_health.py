"""GET /api/v1/health: always answers, reports DB state honestly, uses AS_OF_DATE."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.health import get_database_health
from app.services.health_service import DatabaseHealth, check_database


def _override_db(app: FastAPI, health: DatabaseHealth) -> None:
    app.dependency_overrides[get_database_health] = lambda: health


def test_health_without_database_url_is_degraded_not_crashing(client: TestClient) -> None:
    # conftest sets DATABASE_URL="" so this exercises the real "not configured" path.
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert body["db"] == "not_configured"
    assert body["schema_ready"] is False
    assert body["last_load_at"] is None


def test_health_ok_when_db_reachable_and_migrated(app: FastAPI) -> None:
    loaded = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
    _override_db(app, DatabaseHealth(db="ok", schema_ready=True, last_load_at=loaded))
    with TestClient(app) as c:
        body = c.get("/api/v1/health").json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["last_load_at"].startswith("2026-11-25T12:00:00")


def test_health_degraded_when_db_down(app: FastAPI) -> None:
    _override_db(app, DatabaseHealth(db="down", schema_ready=False, last_load_at=None))
    with TestClient(app) as c:
        r = c.get("/api/v1/health")
    # Still 200 on purpose: Render must not restart a healthy API because Supabase is waking up.
    assert r.status_code == 200
    assert r.json()["status"] == "degraded"
    assert r.json()["db"] == "down"


def test_health_degraded_when_schema_missing(app: FastAPI) -> None:
    _override_db(app, DatabaseHealth(db="ok", schema_ready=False, last_load_at=None))
    with TestClient(app) as c:
        assert c.get("/api/v1/health").json()["status"] == "degraded"


def test_check_database_reports_down_for_unreachable_server(monkeypatch: pytest.MonkeyPatch) -> None:
    # Port 1 on localhost refuses connections immediately: a real "database is down" case.
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@127.0.0.1:1/nothing")
    from tests.conftest import clear_config_caches

    clear_config_caches()
    result = check_database()
    assert result.db == "down"
    assert result.schema_ready is False


def test_health_as_of_is_the_business_date(client: TestClient) -> None:
    assert client.get("/api/v1/health").json()["as_of"] == "2026-11-16"


def test_health_answers_head_for_uptime_monitors(client: TestClient) -> None:
    # The keep-warm monitor (§15) may send HEAD; a 405 would look like an outage.
    assert client.head("/api/v1/health").status_code == 200
