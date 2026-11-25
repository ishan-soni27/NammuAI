"""Guards for how Vercel builds and runs the API (ADR-002).

Each test pins down a trap found by reading Vercel's Python builder source
(github.com/vercel/vercel, packages/python and packages/python-analysis) on 2026-11-25.
All of them fail silently at deploy time, so we catch them here instead.
"""

from __future__ import annotations

import json
import re

import pytest

from app.config.settings import BACKEND_DIR, Settings
from app.db.session import make_engine
from tests.conftest import clear_config_caches

# Vercel looks for these files, in this order of folders, and uses the first that defines `app`.
_VERCEL_ENTRYPOINT_NAMES = ("app", "index", "server", "main", "wsgi", "asgi")


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


def test_vercel_finds_app_main_as_the_entrypoint() -> None:
    # Root-level candidates (app.py, index.py, main.py...) and src/ would be picked before
    # app/main.py. None must exist, and app/main.py must define a top-level `app`.
    for folder in ("", "src"):
        for name in _VERCEL_ENTRYPOINT_NAMES:
            assert not (BACKEND_DIR / folder / f"{name}.py").exists(), (
                f"{folder}/{name}.py would shadow app/main.py"
            )
    source = (BACKEND_DIR / "app" / "main.py").read_text()
    assert re.search(r"^app = ", source, re.MULTILINE)


def test_vercel_cron_hits_a_real_route_at_most_daily() -> None:
    config = json.loads((BACKEND_DIR / "vercel.json").read_text())
    assert config["regions"] == ["iad1"]  # Washington, D.C., next to Supabase us-east-1
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as client:
        for cron in config["crons"]:
            assert client.get(cron["path"]).status_code == 200, cron["path"]  # Vercel cron sends GET
    for cron in config["crons"]:
        minute, hour, *_ = cron["schedule"].split()
        # Hobby plan: once a day at most. A "*" or "*/n" in minute or hour would fail the deploy.
        assert minute.isdigit() and hour.isdigit(), cron["schedule"]


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
