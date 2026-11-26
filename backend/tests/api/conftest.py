"""API test database: the REAL BlueTide exports, loaded by the REAL loader writer, into SQLite.

There is no local Postgres (no Docker daemon), and tests must never touch Supabase. So:
  1. once per test session, run the loader pipeline on data/raw and write it into an in-memory
     SQLite "template" with app.loader.write (the same code that loads Supabase; it uses COPY on
     Postgres and plain inserts on SQLite, ADR-023);
  2. for each test, copy the template into a fresh in-memory database (sqlite3 backup, fast), and
     point the whole app at it with app.db.session.use_engine.
Every test therefore starts from the same loaded data, and edits never leak between tests.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.pool import StaticPool

from app.config.business_rules import BusinessRules
from app.db.models import Base
from app.db.session import use_engine
from app.loader.pipeline import build_dataset
from app.loader.read_raw import read_all_raw
from app.loader.reference import load_reference
from app.loader.write import start_load_run, write_load
from app.services.planning_inputs import clear_cache


def _sqlite_engine(connection: sqlite3.Connection) -> Engine:
    engine = create_engine("sqlite://", creator=lambda: connection, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _record) -> None:  # noqa: ANN001
        dbapi_conn.execute("PRAGMA foreign_keys = ON")

    return engine


@pytest.fixture(scope="session")
def template_db() -> sqlite3.Connection:
    """The loaded real data, built once per test session (~2 s)."""
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    engine = _sqlite_engine(connection)
    Base.metadata.create_all(engine)
    rules = BusinessRules()
    reference = load_reference()
    result = build_dataset(read_all_raw(), reference, rules)
    run_id = start_load_run(engine, result, rules, "test")
    write_load(engine, run_id, result, reference.vendor_settings)
    return connection


@pytest.fixture
def db_engine(template_db: sqlite3.Connection) -> Iterator[Engine]:
    """A private copy of the loaded data for one test."""
    copy = sqlite3.connect(":memory:", check_same_thread=False)
    template_db.backup(copy)
    engine = _sqlite_engine(copy)
    use_engine(engine)
    clear_cache()
    yield engine
    use_engine(None)
    clear_cache()
    copy.close()


@pytest.fixture
def api(app: FastAPI, db_engine: Engine) -> Iterator[TestClient]:
    """A client for the app wired to this test's database. Sends X-Actor like the website does."""
    with TestClient(app, headers={"X-Actor": "Dana"}) as client:
        yield client
