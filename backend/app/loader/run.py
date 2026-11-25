"""Command line: load the BlueTide exports into the database.

    cd backend
    python -m app.loader.run             # full load into DATABASE_URL (from backend/.env)
    python -m app.loader.run --dry-run   # run every rule and write the report; touch nothing

Safe to re-run: the clean layer is rebuilt identically, each run gets its own load_runs
row, raw rows and data issues, and Dana's settings are never overwritten (invariant #5).
Uses an unpooled connection (one-off process) through the Supabase *session* pooler.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from app.config.business_rules import get_business_rules
from app.config.settings import REPO_ROOT, get_settings
from app.db.session import make_engine
from app.loader.pipeline import build_dataset
from app.loader.read_raw import read_all_raw
from app.loader.reference import load_reference
from app.loader.report import render_report
from app.loader.write import fail_load_run, start_load_run, write_load
from app.logging_setup import configure_logging, redact_database_url

logger = logging.getLogger("app.loader")

DEFAULT_REPORT = REPO_ROOT / "docs" / "DATA_LOAD_REPORT.md"
# The loader runs from a laptop; a home connection to Supabase can take several seconds.
LAPTOP_CONNECT_TIMEOUT_S = 30


def _git_sha() -> str:
    """Short commit of the code doing the load, with "+dirty" if there are uncommitted changes."""
    configured = get_settings().git_commit
    if configured:
        return configured[:7]
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        return f"{sha}+dirty" if dirty else sha
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load the BlueTide CSV exports into the database.")
    parser.add_argument(
        "--dry-run", action="store_true", help="run all rules and write the report; no database"
    )
    parser.add_argument(
        "--report", type=Path, default=DEFAULT_REPORT, help="where to write the Markdown report"
    )
    parser.add_argument("--no-report", action="store_true", help="don't write the report file")
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level)
    rules = get_business_rules()
    started = time.perf_counter()
    git_sha = _git_sha()

    raw = read_all_raw()
    reference = load_reference()
    result = build_dataset(raw, reference, rules)
    d = result.dataset
    logger.info(
        "rules applied",
        extra={
            "items": len(d.items),
            "lots": len(d.lots),
            "sales": len(d.sales),
            "po_lines": len(d.po_lines),
            "issues": len(result.issues),
            "errors": sum(1 for i in result.issues if i.severity == "error"),
            "duration_ms": round((time.perf_counter() - started) * 1000),
        },
    )

    summary = None
    if not args.dry_run:
        engine = make_engine(settings.database_url, pooled=False, connect_timeout=LAPTOP_CONNECT_TIMEOUT_S)
        logger.info("writing to database", extra={"database": redact_database_url(settings.database_url)})
        run_id = start_load_run(engine, result, rules, git_sha)
        try:
            summary = write_load(engine, run_id, result, reference.vendor_settings)
        except Exception as error:
            logger.exception("load failed; nothing was changed", extra={"load_run_id": run_id})
            fail_load_run(engine, run_id, error)
            return 1
        logger.info(
            "load succeeded",
            extra={
                "load_run_id": run_id,
                "raw_rows": summary.raw_rows,
                "issues": summary.issues,
                "vendor_settings_seeded": summary.vendor_settings_seeded,
                "vendor_settings_kept": summary.vendor_settings_kept,
            },
        )

    if not args.no_report:
        # Real UTC time is right here: it's when the report was generated, not a business date.
        generated_at = datetime.now(UTC)  # clock-ok
        args.report.write_text(render_report(result, rules, generated_at, git_sha, summary))
        logger.info("report written", extra={"path": str(args.report)})

    logger.info(
        "done", extra={"duration_ms": round((time.perf_counter() - started) * 1000), "dry_run": args.dry_run}
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
