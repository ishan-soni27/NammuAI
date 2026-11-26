"""Guards for the project invariants in CLAUDE.md. These fail loudly if someone breaks a rule."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import logging
import re
from pathlib import Path

import pytest

from app.config.settings import BACKEND_DIR, REPO_ROOT
from app.db.models import APP_LAYER, CLEAN_LAYER, LOGGING_LAYER, RAW_LAYER, Base
from app.logging_setup import ContextFilter, configure_logging, redact_database_url, request_id_var

# ---- Invariant #5: the loader can rebuild CLEAN tables without touching Dana's edits -------


def test_app_layer_tables_have_no_foreign_keys_into_the_clean_layer() -> None:
    # A FK from vendor_settings -> vendors would make "rebuild vendors" either fail or
    # CASCADE-delete Dana's lead times. See app/db/models.py module docstring.
    offenders = [
        (table, fk.target_fullname)
        for table in APP_LAYER
        for fk in Base.metadata.tables[table].foreign_keys
        if fk.column.table.name in CLEAN_LAYER
    ]
    assert offenders == []


def test_every_table_belongs_to_exactly_one_layer() -> None:
    layers = RAW_LAYER + CLEAN_LAYER + APP_LAYER + LOGGING_LAYER
    assert len(layers) == len(set(layers))
    assert set(layers) == set(Base.metadata.tables)


# ---- ADR-015: RLS on every table --------------------------------------------------------


def test_migrations_enable_rls_on_every_table() -> None:
    # Each migration lists the tables it creates in ALL_TABLES and enables RLS on them. Together
    # they must cover every model table (plus Alembic's own), or a new table is exposed.
    covered: set[str] = set()
    for path in sorted((BACKEND_DIR / "migrations" / "versions").glob("[0-9][0-9][0-9][0-9]_*.py")):
        spec = importlib.util.spec_from_file_location(f"migration_{path.stem}", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert "ENABLE ROW LEVEL SECURITY" in path.read_text(), f"{path.name} enables no RLS"
        covered |= set(module.ALL_TABLES)
    assert covered == set(Base.metadata.tables) | {"alembic_version"}


# ---- Invariant #1: business logic never reads the system clock -------------------------

_CLOCK_CALLS = re.compile(r"\b(date\.today|datetime\.(now|utcnow|today))\s*\(")
_BUSINESS_DIRS = ("planning", "loader", "services", "api")


def test_business_code_never_reads_the_system_clock() -> None:
    offenders = []
    for folder in _BUSINESS_DIRS:
        for path in (BACKEND_DIR / "app" / folder).rglob("*.py"):
            for n, line in enumerate(path.read_text().splitlines(), start=1):
                if _CLOCK_CALLS.search(line) and "# clock-ok" not in line:
                    offenders.append(f"{path.relative_to(BACKEND_DIR)}:{n}: {line.strip()}")
    assert offenders == [], "Use rules.as_of_date instead of the clock:\n" + "\n".join(offenders)


# ---- Invariant #2: raw exports are byte-identical to what Kestrel Bay sent --------------


def _manifest() -> list[tuple[str, str]]:
    lines = (REPO_ROOT / "data" / "raw_checksums.sha256").read_text().splitlines()
    return [tuple(line.split(maxsplit=1)) for line in lines if line and not line.startswith("#")]  # type: ignore[misc]


@pytest.mark.parametrize(("expected", "rel_path"), _manifest())
def test_raw_files_match_the_checksum_manifest(expected: str, rel_path: str) -> None:
    actual = hashlib.sha256((REPO_ROOT / rel_path).read_bytes()).hexdigest()
    assert actual == expected, f"{rel_path} changed. Never modify data/raw or kestrel-bay."


# ---- Logging layer 1 --------------------------------------------------------------------


def test_redact_database_url_never_shows_the_password() -> None:
    url = "postgresql+psycopg://postgres.abc:s3cret@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    redacted = redact_database_url(url)
    assert "s3cret" not in redacted and "postgres.abc" not in redacted
    assert redacted == "postgresql+psycopg://aws-0-us-east-1.pooler.supabase.com:5432/postgres"


def test_log_lines_are_json_and_carry_the_request_id() -> None:
    configure_logging("INFO")
    root = logging.getLogger()
    buffer = io.StringIO()
    formatter = root.handlers[0].formatter
    capture = logging.StreamHandler(buffer)
    capture.setFormatter(formatter)
    capture.addFilter(ContextFilter())
    root.addHandler(capture)
    token = request_id_var.set("req-test-1234")
    try:
        logging.getLogger("app.test").info("hello", extra={"items": 30})
    finally:
        request_id_var.reset(token)
        root.removeHandler(capture)
    line = json.loads(buffer.getvalue().strip().splitlines()[-1])
    assert line["message"] == "hello"
    assert line["request_id"] == "req-test-1234"
    assert line["items"] == 30
    assert line["level"] == "INFO"
    assert "timestamp" in line


def test_env_example_documents_every_setting() -> None:
    from app.config.settings import Settings

    example = (BACKEND_DIR / ".env.example").read_text()
    documented = {m.group(1).lower() for m in re.finditer(r"^([A-Z_]+)=", example, re.MULTILINE)}
    # Set by the hosting platform itself (Vercel), not by us.
    expected = set(Settings.model_fields) - {"git_commit", "vercel"}
    assert expected <= documented, f"Missing from .env.example: {expected - documented}"


def test_repo_paths_point_at_real_folders() -> None:
    assert (REPO_ROOT / "data" / "raw").is_dir()
    assert (REPO_ROOT / "data" / "reference").is_dir()
    assert Path(BACKEND_DIR / "app").is_dir()
