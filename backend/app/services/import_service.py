"""Imports from the website (Phase 6 step 3; ADR-029): BlueTide's export files, or Dana's own templates.

Every import goes the same three steps, so nothing is ever loaded blind:
  1. upload files into slots (each file on its own request: Vercel caps a request at 4.5 MB),
  2. check: a dry run that writes nothing and reports what would change, what's wrong (blockers stop
     the load), what looks odd (warnings), and how Dana's own records are affected,
  3. load, with the one-time code the check handed out.

BlueTide's files go through the real loader (loader/pipeline.build_dataset, loader/write.write_load),
in one transaction that never touches Dana's tables (invariant #5). Slots she doesn't fill reuse the
last load's file (rebuilt from raw_rows). The reference seeds come from the last load's stored copy
(the deployed API doesn't ship data/reference). Production connects through Supabase's transaction
pooler, so the writer uses plain batched inserts there (no COPY).

Dana's own templates (suppliers, items, customers, stock count, POs, sales history) are handled by
services/template_import.py with the same check-then-load flow.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.v1 import schemas as s
from app.config.business_rules import BusinessRules
from app.config.settings import get_settings
from app.db import models as m
from app.db.sql import utc_now
from app.errors import AppError
from app.loader.convert import to_sell_uom
from app.loader.pipeline import build_dataset
from app.loader.read_raw import RAW_FILES, RawFileError, read_raw_bytes
from app.loader.reference import REFERENCE_DIR, load_reference_from_texts, reference_texts
from app.loader.report import TRAP_TITLES
from app.loader.types import LoadResult, RawFile, RawRecord, SourceRef
from app.loader.write import fail_load_run, start_load_run, write_load
from app.planning.explain import day
from app.planning.records import AppPOLine, BlueTidePOLine, reconcile_pos
from app.services import template_import
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


def _slots(kind: str) -> list[s.ImportSlotOut]:
    if kind == "bluetide":
        return [
            s.ImportSlotOut(slot=slot, label=BLUETIDE_LABELS[slot], expected_name=name, columns=[])
            for slot, name in RAW_FILES.items()
        ]
    return [
        s.ImportSlotOut(slot=t.slot, label=t.label, expected_name=f"{t.slot}.csv", columns=list(t.columns))
        for t in template_import.TEMPLATES.values()
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
        slots=_slots(up.kind),
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


def create_import(db: Session, kind: str) -> s.ImportOut:
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
    if up.kind == "bluetide":
        if slot not in RAW_FILES:
            raise AppError(404, "unknown_slot", f"There's no BlueTide file called {slot!r}.")
        try:
            rows = len(read_raw_bytes(content, RAW_FILES[slot], slot, check=True).records)
        except RawFileError as error:
            raise AppError(422, "wrong_file", str(error)) from error
    else:
        if slot not in template_import.TEMPLATES:
            raise AppError(404, "unknown_slot", f"There's no template called {slot!r}.")
        rows = template_import.count_rows(slot, content)
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


def _raw_from_run(db: Session, run: m.LoadRun, slot: str, file_name: str) -> RawFile | None:
    """The file a previous load read, rebuilt from its raw rows (values exactly as exported)."""
    meta = next((f for f in run.files or [] if f.get("name") == file_name), None)
    if meta is None:
        return None
    rows = db.execute(
        select(m.RawRow.source_line_number, m.RawRow.data, m.RawRow.row_hash)
        .where(m.RawRow.load_run_id == run.id, m.RawRow.source_file == file_name)
        .order_by(m.RawRow.source_line_number)
    ).all()
    records = tuple(
        RawRecord(
            source=SourceRef(file=file_name, line=line), data={k: str(v) for k, v in data.items()}, row_hash=h
        )
        for line, data, h in rows
    )
    return RawFile(logical_name=slot, file_name=file_name, sha256=meta.get("sha256", ""), records=records)


def _assemble(
    db: Session, up: m.Upload
) -> tuple[dict[str, RawFile], list[dict[str, Any]], dict[str, str] | None, list[str]]:
    """The seven files to load (uploaded, or the last load's), the seeds, and anything blocking."""
    last = _last_run(db)
    uploaded = {
        f.slot: f for f in db.scalars(select(m.UploadFile).where(m.UploadFile.upload_id == up.id)).all()
    }
    raw: dict[str, RawFile] = {}
    files: list[dict[str, Any]] = []
    blockers: list[str] = []
    for slot, name in RAW_FILES.items():
        previous = next((f for f in (last.files if last else []) or [] if f.get("name") == name), None)
        if slot in uploaded:
            raw[slot] = read_raw_bytes(uploaded[slot].content, name, slot, check=True)
            source = "uploaded"
        else:
            reused = _raw_from_run(db, last, slot, name) if last else None
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
    return raw, files, texts, blockers


def _bluetide_po_lines(result: LoadResult) -> list[BlueTidePOLine]:
    units = {i.item_code: (i.sell_uom, i.lb_per_case) for i in result.dataset.items}
    out = []
    for p in result.dataset.po_lines:
        sell_uom, lb = units.get(p.item_code, (p.uom, None))
        ordered = to_sell_uom(p.qty_ordered, p.uom, sell_uom, lb)
        received = to_sell_uom(p.qty_received, p.uom, sell_uom, lb)
        out.append(
            BlueTidePOLine(
                p.po_no,
                p.line_no,
                p.item_code,
                p.vendor_code,
                p.order_date,
                p.expected_date_system,
                float(ordered) if ordered is not None else None,
                float(received) if received is not None else 0.0,
                float(p.qty_remaining_sell_uom)
                if p.status == "open" and p.qty_remaining_sell_uom is not None
                else 0.0,
                p.status,
            )
        )
    return out


def _effect_on_danas_records(db: Session, result: LoadResult) -> tuple[list[str], list[str]]:
    """(conflicts the new files would flag on her records, her records pointing at items they drop)."""
    conflicts: list[str] = []
    app_lines = [
        AppPOLine(
            po.po_no, line.line_no, line.item_code, po.vendor_code, po.order_date, float(line.qty_ordered)
        )
        for po, line in db.execute(
            select(m.PurchaseOrder, m.PurchaseOrderLineApp).join(
                m.PurchaseOrderLineApp, m.PurchaseOrderLineApp.po_id == m.PurchaseOrder.id
            )
        ).all()
    ]
    if app_lines:
        mine = {(a.po_no, a.line_no) for a in app_lines}
        for line in reconcile_pos(_bluetide_po_lines(result), app_lines, [], []).lines:
            if (line.po_no, line.line_no) in mine and line.flags:
                conflicts.append(f"{line.po_no} line {line.line_no}: {'; '.join(line.flags)}")
    orders = {(x.order_no, x.item_code): x.status for x in result.dataset.sales}
    for sh, line in db.execute(
        select(m.Shipment, m.ShipmentLine).join(m.ShipmentLine, m.ShipmentLine.shipment_id == m.Shipment.id)
    ).all():
        if sh.status == "open" and orders.get((sh.order_no, line.item_code)) == "INVOICED":
            conflicts.append(
                f"Order {sh.order_no}: the new files show it invoiced (shipped) while it's open here"
            )

    known = {i.item_code for i in result.dataset.items} | set(db.scalars(select(m.AppItem.item_code)).all())
    used = (
        set(db.scalars(select(m.PurchaseOrderLineApp.item_code)).all())
        | set(db.scalars(select(m.ShipmentLine.item_code)).all())
        | set(db.scalars(select(m.StockMovement.item_code)).all())
        | set(db.scalars(select(m.HandledFlag.item_code).where(m.HandledFlag.cleared_at.is_(None))).all())
    )
    orphans = sorted(used - known)
    orphan_notes = (
        [
            f"Your records mention items the new files don't have: {', '.join(orphans)}. "
            "Add them on the Items page."
        ]
        if orphans
        else []
    )
    return conflicts, orphan_notes


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


def _check_bluetide(db: Session, rules: BusinessRules, up: m.Upload) -> dict[str, Any]:
    raw, files, texts, blockers = _assemble(db, up)
    report: dict[str, Any] = {"kind": "bluetide", "files": files, "blockers": blockers, "warnings": []}
    if blockers:
        return report
    assert texts is not None
    result = build_dataset(raw, load_reference_from_texts(texts), rules)
    d = result.dataset
    last = _last_run(db)
    current = (last.summary or {}).get("snapshot_date") if last else None
    if d.snapshot_date > rules.as_of_date:
        blockers.append(
            f"The stock count in these files is dated {day(d.snapshot_date)}, "
            f"after today ({day(rules.as_of_date)}). "
            "The checks for expiry and late POs use today, so this can't be loaded yet."
        )
    if current and d.snapshot_date.isoformat() < current:
        blockers.append(
            f"The stock count in these files ({day(d.snapshot_date)}) is older than the one loaded now "
            f"({current}). Loading it would go back in time."
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
    report["conflicts"], report["orphans"] = _effect_on_danas_records(db, result)
    return report


def check(db: Session, rules: BusinessRules, upload_id: int) -> s.ImportOut:
    """The dry run: nothing is written except this report."""
    up = _get(db, upload_id)
    if up.status not in ("open", "checked"):
        raise AppError(409, "import_closed", f"Import #{upload_id} is {up.status}.")
    has_files = db.execute(select(m.UploadFile.id).where(m.UploadFile.upload_id == up.id)).first()
    if not has_files:
        raise AppError(422, "no_files", "Upload at least one file first.")
    try:
        report = (
            _check_bluetide(db, rules, up) if up.kind == "bluetide" else template_import.check(db, rules, up)
        )
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


def load(db: Session, rules: BusinessRules, upload_id: int, confirm_code: str) -> s.ImportOut:
    up = _get(db, upload_id)
    if up.status != "checked" or not up.confirm_code:
        raise AppError(409, "not_checked", "Check the files first (and fix anything that blocks the load).")
    if not secrets.compare_digest(confirm_code, up.confirm_code):
        raise AppError(422, "wrong_code", "That confirmation code doesn't match this import's check.")
    if up.kind == "template":
        summary = template_import.load(db, rules, up)
        up.status, up.confirm_code = "loaded", None
        up.report = {**(up.report or {}), "loaded": summary}
        _touch(up)
        record_change(
            db, action="import.load", entity_type="import", entity_id=str(up.id), before=None, after=summary
        )
        db.commit()
        return _out(db, up)

    _fail_stale_runs(db)
    raw, _, texts, blockers = _assemble(db, up)
    if blockers or not texts:
        raise AppError(409, "blocked", "Something changed since the check. Check the files again.")
    reference = load_reference_from_texts(texts)
    result = build_dataset(raw, reference, rules)
    engine = db.get_bind()
    db.commit()  # the load runs in its own single transaction (loader/write.py)
    run_id = start_load_run(engine, result, rules, get_settings().git_commit or "web import", texts)  # type: ignore[arg-type]
    try:
        written = write_load(engine, run_id, result, reference.vendor_settings, use_copy=False)  # type: ignore[arg-type]
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
