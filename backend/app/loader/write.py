"""Store one load: raw rows, the rebuilt clean layer, data issues and the load_runs record.

Transaction design (all or nothing)
    1. A `load_runs` row is created first, in its own small transaction, with status
       "running". If anything later fails, it is marked "failed" with the error, so a failed
       attempt is visible on the Activity page instead of silently vanishing.
    2. Everything else happens in ONE transaction:
         raw_rows (new, kept per run) -> TRUNCATE the clean tables -> COPY clean rows
         -> seed vendor_settings ONLY where missing -> data_issues -> verify row counts
         -> mark the run "succeeded".
       If any step fails, Postgres rolls the whole thing back and the previous clean data
       stays exactly as it was.

Invariant #5: the loader NEVER truncates or overwrites app-layer tables (Dana's edits).
    The TRUNCATE below names the clean tables explicitly and uses no CASCADE. If someone ever
    adds a foreign key from an app table into a clean table, Postgres refuses the TRUNCATE
    and the load fails loudly instead of deleting Dana's data. tests/unit/test_invariants.py
    also blocks such a foreign key.

How to change this: a new clean table needs a line in `_CLEAN_INSERTS` (parents before
children) and its name in CLEAN_LAYER (app/db/models.py).
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, fields
from typing import Any

from psycopg.types.json import Jsonb
from sqlalchemy import Connection, Engine, Table, func, insert, select, text, update

from app.config.business_rules import BusinessRules
from app.db.models import (
    CLEAN_LAYER,
    Customer,
    DataIssue,
    EventLog,
    ExcludedOrder,
    InventoryLot,
    Item,
    ItemAlias,
    LoadRun,
    Location,
    Price,
    PurchaseOrderLine,
    RawRow,
    SalesLine,
    StockoutPeriod,
    Vendor,
    VendorSetting,
)
from app.db.sql import utc_now
from app.loader.types import LoadResult, SourceRef, VendorSettingSeed

logger = logging.getLogger("app.loader")

# Parents before children (the order write_load inserts the clean tables in).
CLEAN_LAYER_INSERT_ORDER = (
    "locations",
    "vendors",
    "customers",
    "items",
    "item_aliases",
    "excluded_orders",
    "inventory_lots",
    "sales_lines",
    "purchase_order_lines",
    "prices",
    "stockout_periods",
)
GENERAL_SOURCE = "(general)"  # data_issues.source_file for issues not tied to one CSV row
# Upper bound for any single statement during a load (Postgres interval syntax). Generous on purpose:
# a load is a rare, attended, all-or-nothing job, and a timeout just rolls it back.
LOAD_STATEMENT_TIMEOUT = "15min"


@dataclass(frozen=True)
class WriteSummary:
    load_run_id: int
    raw_rows: int
    clean_rows: dict[str, int]
    issues: int
    vendor_settings_seeded: list[str]
    vendor_settings_kept: list[str]


@contextmanager
def _timed(step: str) -> Iterator[None]:
    """Log how long each write step takes (a slow home connection shows up here first)."""
    started = time.perf_counter()
    yield
    logger.info(
        "write step done", extra={"step": step, "duration_ms": round((time.perf_counter() - started) * 1000)}
    )


def _copy_rows(conn: Connection, table: Table, rows: list[dict[str, Any]], use_copy: bool = True) -> None:
    """Bulk insert with Postgres COPY: thousands of rows in one stream, not one round trip each.

    The first successful load spent 3+ minutes sending raw and sales rows one at a time over a
    home connection. COPY sends them as a stream. It runs on the same connection, so it is
    inside the load's single transaction. It needs the Supabase *session* pooler (port 5432),
    which the loader uses; the transaction pooler doesn't support COPY.
    """
    if not rows:
        return
    if conn.dialect.name != "postgresql" or not use_copy:
        # Tests (SQLite has no COPY), and imports from the website: production connects through
        # Supabase's transaction pooler, which doesn't support COPY. SQLAlchemy batches these
        # inserts (insertmanyvalues), and the API runs next to the database, so it's quick.
        conn.execute(insert(table), rows)
        return
    columns = list(rows[0].keys())
    driver = conn.connection.driver_connection  # the psycopg connection under SQLAlchemy
    statement = f"COPY {table.name} ({', '.join(columns)}) FROM STDIN"
    with driver.cursor() as cursor, cursor.copy(statement) as copy:  # type: ignore[union-attr]
        for row in rows:
            copy.write_row([Jsonb(row[c]) if isinstance(row[c], dict | list) else row[c] for c in columns])


def _row(obj: Any, raw_ids: dict[tuple[str, int], int] | None = None) -> dict[str, Any]:
    """Dataclass -> insert dict. `source` becomes `raw_row_id` (traceability, ADR-003)."""
    out: dict[str, Any] = {}
    for f in fields(obj):
        value = getattr(obj, f.name)
        # Only a SourceRef is a file/line pointer. Seeds also have a text column called
        # "source" (where the fact came from), which must be stored as is.
        if isinstance(value, SourceRef):
            if raw_ids is not None:
                out["raw_row_id"] = raw_ids.get((value.file, value.line))
            continue
        out[f.name] = value
    return out


def start_load_run(
    engine: Engine,
    result: LoadResult,
    rules: BusinessRules,
    git_sha: str,
    reference: dict[str, str] | None = None,
) -> int:
    """Create the load_runs row (status "running") in its own transaction and return its id.

    `reference` is the data/reference/*.csv seeds as read (file name -> text), kept so a later
    import from the website can use them (the deployed API doesn't ship data/).
    """
    files = [
        {"name": f.file_name, "sha256": f.sha256, "rows": len(f.records), "slot": f.logical_name}
        for f in result.raw_files
    ]
    with engine.begin() as conn:
        run_id = conn.execute(
            insert(LoadRun.__table__)
            .values(
                status="running",
                as_of_date=rules.as_of_date,
                files=files,
                git_sha=git_sha,
                reference=reference,
            )
            .returning(LoadRun.__table__.c.id)
        ).scalar_one()
        conn.execute(
            insert(EventLog.__table__).values(
                level="INFO",
                source="loader",
                event="load_started",
                details={"load_run_id": run_id, "files": files},
            )
        )
    return int(run_id)


def fail_load_run(engine: Engine, run_id: int, error: BaseException) -> None:
    """Record a failed load (its own transaction, because the main one was rolled back)."""
    message = f"{type(error).__name__}: {error}"[:2000]
    with engine.begin() as conn:
        conn.execute(
            update(LoadRun.__table__)
            .where(LoadRun.__table__.c.id == run_id)
            .values(status="failed", finished_at=utc_now(), summary={"error": message})
        )
        conn.execute(
            insert(EventLog.__table__).values(
                level="ERROR",
                source="loader",
                event="load_failed",
                details={"load_run_id": run_id, "error": message},
            )
        )


def write_load(
    engine: Engine,
    run_id: int,
    result: LoadResult,
    vendor_seeds: tuple[VendorSettingSeed, ...],
    *,
    use_copy: bool = True,
) -> WriteSummary:
    """Write everything for one load in a single transaction (see module docstring).

    `vendor_seeds` come from data/reference/vendor_settings_seed.csv and are inserted only for
    vendors with no vendor_settings row yet, so Dana's edits survive every reload.
    """
    d = result.dataset
    with engine.begin() as conn:
        # Supabase cancels any statement running longer than 2 minutes. Streaming ~16,500 raw
        # rows from a slow home connection can take longer, so lift that limit for THIS
        # transaction only (SET LOCAL ends with the transaction). The API keeps the default.
        if conn.dialect.name == "postgresql":
            conn.execute(text(f"SET LOCAL statement_timeout = '{LOAD_STATEMENT_TIMEOUT}'"))

        # 1. Raw layer: every CSV row exactly as exported, kept per load run.
        raw_rows = [
            {
                "load_run_id": run_id,
                "source_file": r.source.file,
                "source_line_number": r.source.line,
                "data": r.data,
                "row_hash": r.row_hash,
            }
            for f in result.raw_files
            for r in f.records
        ]
        raw_table = RawRow.__table__
        with _timed("raw_rows"):
            _copy_rows(conn, raw_table, raw_rows, use_copy)
            returned = conn.execute(
                select(raw_table.c.id, raw_table.c.source_file, raw_table.c.source_line_number).where(
                    raw_table.c.load_run_id == run_id
                )
            ).all()
        raw_ids = {(file, line): row_id for row_id, file, line in returned}

        # 2. Clean layer: rebuilt from scratch (explicit list, no CASCADE; see module docstring).
        if conn.dialect.name == "postgresql":
            conn.execute(text("TRUNCATE TABLE " + ", ".join(CLEAN_LAYER)))
        else:  # tests on SQLite: same effect, children before parents
            for name in reversed(CLEAN_LAYER_INSERT_ORDER):
                conn.execute(text(f"DELETE FROM {name}"))
        clean_inserts: list[tuple[Table, list[dict[str, Any]]]] = [
            (Location.__table__, [_row(x) for x in d.locations]),
            (Vendor.__table__, [_row(x, raw_ids) for x in d.vendors]),
            (Customer.__table__, [_row(x, raw_ids) for x in d.customers]),
            (Item.__table__, [_row(x, raw_ids) for x in d.items]),
            (ItemAlias.__table__, [_row(x) for x in d.aliases]),
            (ExcludedOrder.__table__, [_row(x) for x in d.excluded_orders]),
            (InventoryLot.__table__, [_row(x, raw_ids) for x in d.lots]),
            (SalesLine.__table__, [_row(x, raw_ids) for x in d.sales]),
            (PurchaseOrderLine.__table__, [_row(x, raw_ids) for x in d.po_lines]),
            (Price.__table__, [_row(x, raw_ids) for x in d.prices]),
            (StockoutPeriod.__table__, [_row(x) for x in d.stockout_periods]),
        ]
        for table, rows in clean_inserts:
            if rows:
                with _timed(table.name):
                    _copy_rows(conn, table, rows, use_copy)

        # 3. App layer: seed Dana's lead times ONLY for vendors that have no row yet (§6.5).
        seeds = {s.vendor_code: s for s in vendor_seeds}
        existing = set(conn.execute(select(VendorSetting.__table__.c.vendor_code)).scalars())
        to_seed = [s for code, s in sorted(seeds.items()) if code not in existing]
        if to_seed:
            conn.execute(
                insert(VendorSetting.__table__),
                [
                    {
                        "vendor_code": s.vendor_code,
                        "lead_time_days": s.lead_time_days,
                        "safety_days": s.safety_days,
                        "order_cycle_days": s.order_cycle_days,
                        "source": f"seed: {s.source}",
                        "note": s.note or None,
                        "updated_by": "seed (data/reference/vendor_settings_seed.csv)",
                    }
                    for s in to_seed
                ],
            )

        # 4. Data issues (logging layer 2), each linked to its raw row when it has one.
        issue_rows = [
            {
                "load_run_id": run_id,
                "source_file": i.source.file if i.source else GENERAL_SOURCE,
                "source_line_number": i.source.line if i.source else None,
                "raw_row_id": raw_ids.get((i.source.file, i.source.line)) if i.source else None,
                "trap_id": i.trap_id,
                "rule_code": i.rule_code,
                "severity": i.severity,
                "action": i.action,
                "item_code": i.item_code,
                "field": i.field,
                "original_value": i.original_value,
                "new_value": i.new_value,
                "message": i.message,
            }
            for i in result.issues
        ]
        if issue_rows:
            with _timed("data_issues"):
                _copy_rows(conn, DataIssue.__table__, issue_rows)

        # 5. Reconcile: what's in the database must equal what the pipeline produced.
        clean_counts = {
            table.name: conn.execute(select(func.count()).select_from(table)).scalar_one()
            for table, _ in clean_inserts
        }
        expected = {table.name: len(rows) for table, rows in clean_inserts}
        if clean_counts != expected:
            raise RuntimeError(f"row counts don't reconcile: database {clean_counts} vs pipeline {expected}")

        summary = WriteSummary(
            load_run_id=run_id,
            raw_rows=len(raw_rows),
            clean_rows=clean_counts,
            issues=len(issue_rows),
            vendor_settings_seeded=[s.vendor_code for s in to_seed],
            vendor_settings_kept=sorted(code for code in seeds if code in existing),
        )
        conn.execute(
            update(LoadRun.__table__)
            .where(LoadRun.__table__.c.id == run_id)
            .values(status="succeeded", finished_at=utc_now(), summary=_summary_json(result, summary))
        )
        conn.execute(
            insert(EventLog.__table__).values(
                level="INFO",
                source="loader",
                event="load_succeeded",
                details={"load_run_id": run_id, "issues": len(issue_rows), "clean_rows": clean_counts},
            )
        )
    return summary


def _summary_json(result: LoadResult, summary: WriteSummary) -> dict[str, Any]:
    """JSON-safe summary stored on load_runs (shown on the Activity page)."""
    by_trap = Counter(i.trap_id or "row_error" for i in result.issues)
    return {
        "snapshot_date": result.dataset.snapshot_date.isoformat(),
        "raw_rows": summary.raw_rows,
        "clean_rows": summary.clean_rows,
        "issues": summary.issues,
        "issues_by_trap": dict(sorted(by_trap.items())),
        "errors": sum(1 for i in result.issues if i.severity == "error"),
        "vendor_settings_seeded": summary.vendor_settings_seeded,
        "vendor_settings_kept": summary.vendor_settings_kept,
    }
