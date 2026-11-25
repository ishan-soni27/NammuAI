"""Request id, actor and the error envelope (BUILD_PROMPT §8.5 conventions)."""

from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.testclient import TestClient

from app.errors import AppError
from app.middleware import clean_actor, clean_request_id


def _envelope(body: dict) -> dict:
    assert set(body) == {"error"}, body
    err = body["error"]
    assert {"code", "message", "request_id"} <= set(err)
    return err


# ---- Request id -----------------------------------------------------------------------


def test_every_response_has_a_request_id_header(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert len(r.headers["X-Request-ID"]) >= 8


def test_safe_incoming_request_id_is_reused(client: TestClient) -> None:
    r = client.get("/api/v1/health", headers={"X-Request-ID": "web-1234abcd"})
    assert r.headers["X-Request-ID"] == "web-1234abcd"


def test_unsafe_incoming_request_id_is_replaced(client: TestClient) -> None:
    r = client.get("/api/v1/health", headers={"X-Request-ID": "bad id; DROP TABLE"})
    assert r.headers["X-Request-ID"] != "bad id; DROP TABLE"


def test_clean_request_id_generates_when_missing() -> None:
    assert len(clean_request_id(None)) == 32


# ---- Actor ----------------------------------------------------------------------------


def test_actor_defaults_to_dana() -> None:
    assert clean_actor(None) == "Dana"
    assert clean_actor("   ") == "Dana"


def test_actor_is_trimmed_and_capped() -> None:
    assert clean_actor("  Ishan   Soni ") == "Ishan Soni"
    assert len(clean_actor("x" * 500)) == 80


# ---- Error envelope -------------------------------------------------------------------


def test_unknown_route_returns_plain_english_404_envelope(client: TestClient) -> None:
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    err = _envelope(r.json())
    assert err["code"] == "not_found"
    assert err["request_id"] == r.headers["X-Request-ID"]


def test_app_error_uses_its_code_and_message(app: FastAPI) -> None:
    @app.get("/boom-expected")
    def _raise() -> None:
        raise AppError(404, "item_not_found", "We couldn't find item SHR-9999.")

    with TestClient(app) as c:
        r = c.get("/boom-expected")
    assert r.status_code == 404
    err = _envelope(r.json())
    assert err == {**err, "code": "item_not_found", "message": "We couldn't find item SHR-9999."}


def test_validation_error_names_the_field(app: FastAPI) -> None:
    @app.get("/needs-int")
    def _needs_int(days: int = Query(...)) -> dict:
        return {"days": days}

    with TestClient(app) as c:
        r = c.get("/needs-int", params={"days": "soon"})
    assert r.status_code == 422
    err = _envelope(r.json())
    assert err["code"] == "invalid_request"
    assert "days" in err["message"]
    assert err["details"][0]["field"].endswith("days")


def test_unexpected_crash_returns_500_envelope_with_cors_headers(app: FastAPI) -> None:
    """The middleware safety net: a bug becomes a readable 500 the browser can see.

    If this came from a FastAPI `Exception` handler instead, it would run outside CORS and
    the browser would report a CORS failure instead of our message (§16).
    """

    @app.get("/boom")
    def _crash() -> None:
        raise RuntimeError("simulated bug")

    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/boom", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 500
    err = _envelope(r.json())
    assert err["code"] == "internal_error"
    assert "simulated bug" not in err["message"]  # internals never leak to Dana
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert r.headers["X-Request-ID"] == err["request_id"]


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    r = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_cors_exposes_request_id_to_the_browser(client: TestClient) -> None:
    r = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert "x-request-id" in r.headers["access-control-expose-headers"].lower()
