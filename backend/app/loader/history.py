"""Read an earlier load's files back from raw_rows (ADR-029, ADR-032).

Used by the website's import (a file Dana leaves out reuses the last load's copy) and by every load
that accumulates sales history (the previous load's sales lines). Rows keep the load they first came
from (raw_rows.origin_load_run_id -> SourceRef.origin), so traceability survives being carried over.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.db import models as m
from app.loader.types import RawFile, RawRecord, SourceRef


def last_succeeded_run(conn: Connection | Session) -> Any:
    """(id, files) of the newest successful load, or None."""
    return conn.execute(
        select(m.LoadRun.id, m.LoadRun.files)
        .where(m.LoadRun.status == "succeeded")
        .order_by(m.LoadRun.id.desc())
        .limit(1)
    ).first()


def raw_file_from_run(
    conn: Connection | Session, run_id: int, files: list[dict[str, Any]] | None, slot: str, file_name: str
) -> RawFile | None:
    """The file that load read (values exactly as exported), or None if it didn't have one."""
    meta = next((f for f in files or [] if f.get("name") == file_name), None)
    if meta is None:
        return None
    rows = conn.execute(
        select(m.RawRow.source_line_number, m.RawRow.data, m.RawRow.row_hash, m.RawRow.origin_load_run_id)
        .where(m.RawRow.load_run_id == run_id, m.RawRow.source_file == file_name)
        .order_by(m.RawRow.id)
    ).all()
    if not rows:
        return None  # its raw rows were pruned (older than raw_rows_keep_loads)
    records = tuple(
        RawRecord(
            source=SourceRef(file=file_name, line=line, origin=origin or run_id),
            data={k: str(v) for k, v in data.items()},
            row_hash=h,
        )
        for line, data, h, origin in rows
    )
    return RawFile(logical_name=slot, file_name=file_name, sha256=meta.get("sha256", ""), records=records)
