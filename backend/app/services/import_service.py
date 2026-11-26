"""Imports from the website (ADR-029): Dana uploads BlueTide's export files every week.

Every import goes the same three steps, so nothing is ever loaded blind:
  1. upload files into slots (each file on its own request: Vercel caps a request at 4.5 MB),
  2. check: a dry run that writes nothing and reports what would change, what's wrong (blockers stop
     the load) and what looks odd (warnings),
  3. load, with the one-time code the check handed out.

BlueTide's files go through the real loader (loader/pipeline.build_dataset, loader/write.write_load),
in one transaction that never touches Dana's tables (invariant #5). Slots she doesn't fill reuse the
last load's file (rebuilt from raw_rows). The reference seeds come from the last load's stored copy
(the deployed API doesn't ship data/reference). Production connects through Supabase's transaction
pooler, so the writer uses plain batched inserts there (no COPY).

BlueTide owns every fact (ADR-032): the files are the only way stock, sales and POs get in.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.v1 import schemas as s
from app.config.business_rules import rules_for_snapshot
from app.config.settings import get_settings
from app.db import models as m
from app.db.sql import utc_now
from app.errors import AppError
from app.loader.accumulate import SalesMerge, merge_sales
from app.loader.history import raw_file_from_run
from app.loader.pipeline import build_dataset, snapshot_date_of
from app.loader.read_raw import RAW_FILES, RawFileError, read_raw_bytes
from app.loader.reference import REFERENCE_DIR, load_reference_from_texts, reference_texts
from app.loader.report import TRAP_TITLES
from app.loader.types import LoadResult, RawFile
from app.loader.write import fail_load_run, start_load_run, write_load
from app.planning.explain import day
from app.services.audit import current_actor, record_change
from app.services.planning_inputs import clear_cache

MAX_FILE_BYTES = 4_400_000  # just under Vercel's 4.5 MB request limit
STALE_RUN = timedelta(minutes=15)  # a "running" load older than this was cut off (e.g. a timeout)
BLUETIDE_LABELS = {
    "items": "Items",
    "inventory_on_hand": "Stock on hand",
    "sales_lines": "Sales lines",
    "purchase_orders": "Purchase orders",
    "vendors": "Suppliers",
    "customers": "Customers",
    "price_list": "Price list",
}


def _slots() -> list[s.ImportSlotOut]:
    return [
        s.ImportSlotOut(slot=slot, label=BLUETIDE_LABELS[slot], expected_name=name)
        for slot, name in RAW_FILES.items()
    ]


def _out(db: Session, up: m.Upload) -> s.ImportOut:
    files = db.scalars(select(m.UploadFile).where(m.UploadFile.upload_id == up.id)).all()
    report = up.report or None
    return s.ImportOut(
        id=up.id,
        kind=up.kind,  # type: ignore[arg-type]
        status=up.status,  # type: ignore[arg-type]
        created_at=up.created_at,
        created_by=up.created_by,
        slots=_slots(),
        files=[
            s.ImportFileOut(
                slot=f.slot, file_name=f.file_name, rows=f.rows, size_bytes=f.size_bytes, sha256=f.sha256
            )
            for f in files
        ],
        report=report,
        confirm_code=up.confirm_code if up.status == "checked" else None,
        load_run_id=up.load_run_id,
        error=up.error,
    )


def _get(db: Session, upload_id: int) -> m.Upload:
    up = db.get(m.Upload, upload_id)
    if up is None:
        raise AppError(404, "import_not_found", f"We couldn't find import #{upload_id}.")
    return up


def imports(db: Session) -> list[s.ImportOut]:
    rows = db.scalars(select(m.Upload).order_by(m.Upload.id.desc()).limit(30)).all()
    return [_out(db, up) for up in rows]


def import_detail(db: Session, upload_id: int) -> s.ImportOut:
    return _out(db, _get(db, upload_id))


def create_import(db: Session, kind: str = "bluetide") -> s.ImportOut:
    actor = current_actor()
    up = m.Upload(kind=kind, status="open", created_by=actor, updated_by=actor)
    db.add(up)
    db.flush()
    record_change(
        db,
        action="import.start",
        entity_type="import",
        entity_id=str(up.id),
        before=None,
        after={"kind": kind},
    )
    db.commit()
    return _out(db, up)


def _touch(up: m.Upload) -> None:
    up.updated_by = current_actor()
    up.updated_at = utc_now()  # type: ignore[assignment]


def put_file(db: Session, upload_id: int, slot: str, file_name: str, content: bytes) -> s.ImportOut:
    """Store one file in one slot, after checking it's the right kind of file (columns, rows)."""
    up = _get(db, upload_id)
    if up.status not in ("open", "checked"):
        raise AppError(409, "import_closed", f"Import #{upload_id} is {up.status}. Start a new one.")
    if len(content) > MAX_FILE_BYTES:
        raise AppError(
            413, "file_too_big", f"{file_name} is over 4.4 MB. Split it, or ask us to raise the limit."
        )
    if not content.strip():
        raise AppError(422, "file_empty", f"{file_name} is empty.")
    if slot not in RAW_FILES:
        raise AppError(404, "unknown_slot", f"There's no BlueTide file called {slot!r}.")
    try:
        rows = len(read_raw_bytes(content, RAW_FILES[slot], slot, check=True).records)
    except RawFileError as error:
        raise AppError(422, "wrong_file", str(error)) from error
    existing = db.execute(
        select(m.UploadFile).where(m.UploadFile.upload_id == up.id, m.UploadFile.slot == slot)
    ).scalar_one_or_none()
    if existing is not None:
        db.delete(existing)
        db.flush()
    db.add(
        m.UploadFile(
            upload_id=up.id,
            slot=slot,
            file_name=file_name[:200],
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            rows=rows,
            content=content,
        )
    )
    # A new file means the old check no longer describes what would be loaded.
    up.status, up.report, up.confirm_code = "open", None, None
    _touch(up)
    db.commit()
    return _out(db, up)


def discard(db: Session, upload_id: int) -> s.ImportOut:
    up = _get(db, upload_id)
    if up.status == "loaded":
        raise AppError(409, "already_loaded", "That import was loaded; load a newer one to replace it.")
    up.status, up.confirm_code = "discarded", None
    _touch(up)
    record_change(
        db, action="import.discard", entity_type="import", entity_id=str(up.id), before=None, after=None
    )
    db.commit()
    return _out(db, up)


# ---- BlueTide files: assemble, check, load ------------------------------------------------------


def _last_run(db: Session) -> m.LoadRun | None:
    return db.scalars(
        select(m.LoadRun).where(m.LoadRun.status == "succeeded").order_by(m.LoadRun.id.desc()).limit(1)
    ).first()


def _assemble(
    db: Session, up: m.Upload
) -> tuple[dict[str, RawFile], list[dict[str, Any]], dict[str, str] | None, list[str], SalesMerge | None]:
    """The seven files to load (uploaded, or the last load's), the seeds, anything blocking, and how
    the uploaded sales file merged with the sales history (ADR-032: sales accumulate)."""
    last = _last_run(db)
    uploaded = {
        f.slot: f for f in db.scalars(select(m.UploadFile).where(m.UploadFile.upload_id == up.id)).all()
    }
    raw: dict[str, RawFile] = {}
    files: list[dict[str, Any]] = []
    blockers: list[str] = []
    sales: SalesMerge | None = None
    for slot, name in RAW_FILES.items():
        previous = next((f for f in (last.files if last else []) or [] if f.get("name") == name), None)
        if slot in uploaded and uploaded[slot].content is None:
            blockers.append(
                f"{BLUETIDE_LABELS[slot]}: this upload is old and its file was cleared to save space. "
                "Start a new upload."
            )
            continue
        if slot in uploaded:
            raw[slot] = read_raw_bytes(uploaded[slot].content or b"", name, slot, check=True)
            source = "uploaded"
            if slot == "sales_lines":
                # Sales accumulate: this week's file wins line by line; older lines it no longer lists
                # are kept from the history the last load stored.
                history = raw_file_from_run(db, last.id, last.files, slot, name) if last else None
                raw[slot], sales = merge_sales(raw[slot], history)
        else:
            reused = raw_file_from_run(db, last.id, last.files, slot, name) if last else None
            if reused is None:
                blockers.append(f"{BLUETIDE_LABELS[slot]}: no file, and no earlier load to reuse. Upload it.")
                continue
            raw[slot] = reused
            source = "last load"
        files.append(
            {
                "slot": slot,
                "label": BLUETIDE_LABELS[slot],
                "file_name": uploaded[slot].file_name if slot in uploaded else name,
                "source": source,
                "rows": len(raw[slot].records),
                "previous_rows": previous.get("rows") if previous else None,
                "sha256": raw[slot].sha256,
                "same_as_last": bool(previous and previous.get("sha256") == raw[slot].sha256),
            }
        )
    texts = (last.reference if last else None) or (reference_texts() if REFERENCE_DIR.exists() else None)
    if not texts:
        blockers.append(
            "The reference seeds (buildings, pack sizes, lead-time seeds) aren't stored yet. "
            "Run the loader once from a laptop (python -m app.loader.run)."
        )
    return raw, files, texts, blockers, sales


def _notes_on_dropped_items(db: Session, result: LoadResult) -> list[str]:
    """Dana's open handled notes on items the new files no longer have (her note would point nowhere)."""
    known = {i.item_code for i in result.dataset.items}
    noted = set(db.scalars(select(m.HandledFlag.item_code).where(m.HandledFlag.cleared_at.is_(None))).all())
    dropped = sorted(noted - known)
    if not dropped:
        return []
    return [f"Your handled notes mention items the new files don't have: {', '.join(dropped)}."]


def _current_counts(db: Session) -> dict[str, int]:
    def n(q: Any) -> int:
        return int(db.execute(q).scalar_one())

    return {
        "items": n(select(func.count()).select_from(m.Item)),
        "lots": n(select(func.count()).select_from(m.InventoryLot)),
        "open_po_lines": n(
            select(func.count()).select_from(m.PurchaseOrderLine).where(m.PurchaseOrderLine.status == "open")
        ),
        "open_orders": n(select(func.count()).select_from(m.SalesLine).where(m.SalesLine.status == "OPEN")),
        "sales_lines": n(
            select(func.count()).select_from(m.SalesLine).where(m.SalesLine.demand_class == "real_demand")
        ),
        "customers": n(select(func.count()).select_from(m.Customer)),
        "suppliers": n(select(func.count()).select_from(m.Vendor)),
    }


def _check_bluetide(db: Session, up: m.Upload) -> dict[str, Any]:
    raw, files, texts, blockers, sales = _assemble(db, up)
    report: dict[str, Any] = {"kind": "bluetide", "files": files, "blockers": blockers, "warnings": []}
    if blockers:
        return report
    assert texts is not None
    # "Today" for these files is the day after their stock count (ADR-032): expiry, late POs and
    # dormant items are judged as of then, not as of the last load.
    rules = rules_for_snapshot(snapshot_date_of(raw))
    result = build_dataset(raw, load_reference_from_texts(texts), rules)
    d = result.dataset
    last = _last_run(db)
    current = (last.summary or {}).get("snapshot_date") if last else None
    report["today"] = rules.as_of_date.isoformat()
    if current and d.snapshot_date.isoformat() < current:
        blockers.append(
            f"The stock count in these files ({day(d.snapshot_date)}) is older than the one loaded now "
            f"({current}). Loading it would go back in time."
        )
    elif current and d.snapshot_date.isoformat() == current:
        report["warnings"].append(
            "The stock count in these files is the same night as the one loaded now "
            f"({day(d.snapshot_date)}). Fine if BlueTide was exported again; otherwise check you "
            "exported last night's report."
        )
    if sales is not None:
        months = sales.months_of_history(d.snapshot_date)
        report["sales"] = {
            "new": sales.new,
            "updated": sales.updated,
            "unchanged": sales.unchanged,
            "kept": sales.kept,
            "months_of_history": round(months, 1),
        }
        history_days = (d.snapshot_date - sales.first_order_date).days if sales.first_order_date else 0
        if history_days < rules.seasonal_window_days:  # the season pattern learns from a full year (§6.7)
            report["warnings"].append(
                f"Only {months:.1f} months of sales history in total. The season pattern needs a full "
                "year, so the seasonal adjustment will be weaker until more weeks are uploaded."
            )
    for f in files:
        prev = f["previous_rows"]
        if prev and f["rows"] < prev * 0.5:
            report["warnings"].append(
                f"{f['label']}: {f['rows']:,} rows, less than half of last time ({prev:,}). "
                "Is it the full export?"
            )
    if all(f["same_as_last"] for f in files):
        report["warnings"].append("These are the same files as the last load: nothing will change.")
    errors = sum(1 for i in result.issues if i.severity == "error")
    if errors:
        report["warnings"].append(
            f"{errors:,} rows have errors and will be left out (see the data notes after loading)."
        )
    now = _current_counts(db)
    after = {
        "items": len(d.items),
        "lots": len(d.lots),
        "open_po_lines": sum(1 for p in d.po_lines if p.status == "open"),
        "open_orders": sum(1 for x in d.sales if x.status == "OPEN"),
        "sales_lines": sum(1 for x in d.sales if x.demand_class == "real_demand"),
        "customers": len(d.customers),
        "suppliers": len(d.vendors),
    }
    words = {
        "items": "Items",
        "lots": "Lots in stock",
        "open_po_lines": "Open PO lines",
        "open_orders": "Open customer order lines",
        "sales_lines": "Sales lines (real demand)",
        "customers": "Customers",
        "suppliers": "Suppliers",
    }
    report["changes"] = [{"what": words[k], "now": now[k], "after": after[k]} for k in words]
    report["snapshot_date"] = d.snapshot_date.isoformat()
    report["current_snapshot_date"] = current
    by_trap: dict[str, int] = {}
    for issue in result.issues:
        by_trap[issue.trap_id or "-"] = by_trap.get(issue.trap_id or "-", 0) + 1
    report["notes"] = {
        "total": len(result.issues),
        "by_problem": [
            {"trap_id": k, "title": TRAP_TITLES.get(k, "Row error"), "count": v}
            for k, v in sorted(by_trap.items())
        ],
    }
    report["warnings"].extend(_notes_on_dropped_items(db, result))
    return report


def check(db: Session, upload_id: int) -> s.ImportOut:
    """The dry run: nothing is written except this report."""
    up = _get(db, upload_id)
    if up.status not in ("open", "checked"):
        raise AppError(409, "import_closed", f"Import #{upload_id} is {up.status}.")
    has_files = db.execute(select(m.UploadFile.id).where(m.UploadFile.upload_id == up.id)).first()
    if not has_files:
        raise AppError(422, "no_files", "Upload at least one file first.")
    try:
        report = _check_bluetide(db, up)
    except RawFileError as error:
        raise AppError(422, "wrong_file", str(error)) from error
    up.report = report
    up.status = "checked"
    up.confirm_code = None if report["blockers"] else secrets.token_hex(4)
    _touch(up)
    db.commit()
    return _out(db, up)


def _fail_stale_runs(db: Session) -> None:
    """A load cut off by a timeout stays "running" forever; mark old ones failed before a new load."""
    cutoff = datetime.now(UTC) - STALE_RUN  # clock-ok: a log timestamp, not a business date
    db.execute(
        update(m.LoadRun)
        .where(m.LoadRun.status == "running", m.LoadRun.started_at < cutoff)
        .values(status="failed", finished_at=utc_now(), summary={"error": "Cut off before it finished"})
    )


def load(db: Session, upload_id: int, confirm_code: str) -> s.ImportOut:
    up = _get(db, upload_id)
    if up.status != "checked" or not up.confirm_code:
        raise AppError(409, "not_checked", "Check the files first (and fix anything that blocks the load).")
    if not secrets.compare_digest(confirm_code, up.confirm_code):
        raise AppError(422, "wrong_code", "That confirmation code doesn't match this import's check.")
    _fail_stale_runs(db)
    raw, _, texts, blockers, _ = _assemble(db, up)
    if blockers or not texts:
        raise AppError(409, "blocked", "Something changed since the check. Check the files again.")
    reference = load_reference_from_texts(texts)
    rules = rules_for_snapshot(snapshot_date_of(raw))  # "today" = the day after these files' stock count
    result = build_dataset(raw, reference, rules)
    engine = db.get_bind()
    db.commit()  # the load runs in its own single transaction (loader/write.py)
    run_id = start_load_run(engine, result, rules, get_settings().git_commit or "web import", texts)  # type: ignore[arg-type]
    try:
        written = write_load(
            engine,  # type: ignore[arg-type]
            run_id,
            result,
            reference.vendor_settings,
            use_copy=False,
            keep_loads=rules.raw_rows_keep_loads,
        )
    except Exception as error:
        fail_load_run(engine, run_id, error)  # type: ignore[arg-type]
        up = _get(db, upload_id)
        up.status, up.error, up.load_run_id = "failed", f"{type(error).__name__}: {error}"[:500], run_id
        _touch(up)
        db.commit()
        raise AppError(
            500, "load_failed", "The load failed and nothing was changed. The error is on the Activity page."
        ) from error
    clear_cache()
    up = _get(db, upload_id)
    summary = {
        "load_run_id": run_id,
        "raw_rows": written.raw_rows,
        "notes": written.issues,
        "snapshot_date": result.dataset.snapshot_date.isoformat(),
    }
    up.status, up.confirm_code, up.load_run_id = "loaded", None, run_id
    up.report = {**(up.report or {}), "loaded": summary}
    _touch(up)
    record_change(
        db, action="import.load", entity_type="import", entity_id=str(up.id), before=None, after=summary
    )
    db.commit()
    return _out(db, up)
