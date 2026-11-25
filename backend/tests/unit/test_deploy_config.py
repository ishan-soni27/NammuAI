"""Guards for how Vercel builds and runs the app (ADR-002: one project, two services).

The repo root `vercel.json` declares two Vercel Services in one project: `web` (frontend/)
and `api` (backend/, FastAPI). `/api/*` goes to the API with the path intact, and
everything else goes to the website. Each test pins down a trap found by reading Vercel's
docs and its builder source (github.com/vercel/vercel) on 2026-11-25. All of them fail
silently at deploy time, so we catch them here instead.
"""

from __future__ import annotations

import importlib
import json
import re

import pytest
from fastapi import FastAPI

from app.config.settings import BACKEND_DIR, REPO_ROOT, Settings
from app.db.session import make_engine
from tests.conftest import clear_config_caches


def _vercel_config() -> dict:
    return json.loads((REPO_ROOT / "vercel.json").read_text())


def test_only_one_vercel_json_at_the_repo_root() -> None:
    # Nested vercel.json files would be ignored (or conflict) once services are declared.
    assert not (BACKEND_DIR / "vercel.json").exists()
    assert not (REPO_ROOT / "frontend" / "vercel.json").exists()


def test_api_service_entrypoint_resolves_to_our_fastapi_app() -> None:
    api = _vercel_config()["services"]["api"]
    assert api["root"].rstrip("/") == "backend"
    module_name, _, attr = api["entrypoint"].partition(":")  # "app.main:app", relative to backend/
    app = getattr(importlib.import_module(module_name), attr)
    assert isinstance(app, FastAPI)


def test_api_rewrite_comes_first_and_keeps_the_path() -> None:
    # Vercel sends a request to the FIRST matching rewrite and never falls back, so /api must
    # precede the catch-all. The service receives the original path (/api/v1/health), which
    # is why our routes are mounted at /api/v1 (app/main.py API_PREFIX).
    from app.main import API_PREFIX

    rewrites = _vercel_config()["rewrites"]
    assert rewrites[0] == {"source": "/api/(.*)", "destination": {"service": "api"}}
    assert rewrites[-1]["destination"] == {"service": "web"}
    assert API_PREFIX.startswith("/api/")


def test_web_service_serves_index_html_for_deep_links() -> None:
    web = _vercel_config()["services"]["web"]
    assert web["root"].rstrip("/") == "frontend"
    assert {"source": "/(.*)", "destination": "/index.html"} in web["rewrites"]


def test_cron_hits_a_real_route_at_most_daily() -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    config = _vercel_config()
    assert config["regions"] == ["iad1"]  # Washington, D.C., next to Supabase us-east-1
    with TestClient(create_app()) as client:
        for cron in config["crons"]:
            assert client.get(cron["path"]).status_code == 200, cron["path"]  # cron sends GET
    for cron in config["crons"]:
        minute, hour, *_ = cron["schedule"].split()
        # Hobby plan: once a day at most. A "*" or "*/n" in minute or hour fails the deploy.
        assert minute.isdigit() and hour.isdigit(), cron["schedule"]


def test_no_pyproject_toml_that_would_hide_requirements_txt() -> None:
    # Vercel treats ANY backend/pyproject.toml as the dependency list and then ignores
    # requirements.txt. A pyproject.toml holding only tool settings would deploy with no packages.
    pyproject = BACKEND_DIR / "pyproject.toml"
    if pyproject.exists():
        assert "[project]" in pyproject.read_text(), (
            "backend/pyproject.toml without a [project] table makes Vercel skip requirements.txt. "
            "Put tool settings in pytest.ini / ruff.toml instead."
        )


def test_python_version_is_major_minor_only() -> None:
    # Vercel supports 3.12 / 3.13 / 3.14. A patch pin like 3.12.12 may not match its builds.
    version = (BACKEND_DIR / ".python-version").read_text().strip()
    assert re.fullmatch(r"3\.1[234]", version), version


def test_requirements_have_no_trailing_comments() -> None:
    # Comments live on their own lines so every requirements parser reads the pins identically.
    for line in (BACKEND_DIR / "requirements.txt").read_text().splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            assert "#" not in stripped, f"move the comment onto its own line: {line!r}"


def test_git_commit_comes_from_vercel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "abc1234def5678")
    assert Settings().git_commit == "abc1234def5678"


@pytest.mark.parametrize(("vercel_env", "pool_size"), [("1", 1), ("", 5)])
def test_pool_is_small_on_serverless(
    monkeypatch: pytest.MonkeyPatch, vercel_env: str, pool_size: int
) -> None:
    # Many serverless instances can run at once, each with its own pool (see db/session.py).
    monkeypatch.setenv("VERCEL", vercel_env)
    clear_config_caches()
    engine = make_engine("postgresql+psycopg://user:pw@127.0.0.1:1/nothing")  # never connects
    assert engine.pool.size() == pool_size  # type: ignore[attr-defined]
