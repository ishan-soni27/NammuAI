"""Dana's own records: POs, receipts, items and suppliers (Phase 6 step 1; ADR-026, ADR-027).

The app is becoming the main record, so Dana can create POs, mark lines shipped or cancelled,
receive stock (building, lot, expiry, cost) and undo a receipt, and add her own items and
suppliers, all without BlueTide. Every write is audited in the same transaction, and every
rule a person could trip over gets a plain-English message (AppError).

Reading goes through services/planning_inputs.build_context, so the PO page, the Monday screen and
the item page all use the same matched records (planning/records.py, rules R1-R6).
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import schemas as s
from app.config.business_rules import BusinessRules
from app.db import models as m
from app.db.sql import utc_now
from app.errors import AppError
from app.loader.convert import cost_to_sell_uom
from app.loader.normalize import canonical_code, normalize_category
from app.planning.explain import day
from app.planning.records import EPSILON, POLineRecord
from app.planning.supply import po_arrival, vendor_terms
from app.services.audit import current_actor, record_change
from app.services.planning_inputs import PlanningContext, build_context

OPEN_STATUSES = {"open", "shipped", "late", "partly_received"}


def _f(value: Decimal | float | None) -> float | None:
    return float(value) if value is not None else None


# ---- Reading: the purchase-order list ------------------------------------------------------


def _receipts_by_line(db: Session, ctx: PlanningContext) -> dict[tuple[str, int], list[s.ReceiptOut]]:
    locations = {loc.code: loc.name for loc in db.scalars(select(m.Location)).all()}
    moves = db.scalars(select(m.StockMovement).where(m.StockMovement.kind == "receipt")).all()
    reversed_ids = {mv.reverses_id for mv in moves if mv.reverses_id is not None}
    added = {r.movement_id for r in ctx.reconciled.received_lots}
    why_not = dict(ctx.reconciled.skipped_receipts)
    out: dict[tuple[str, int], list[s.ReceiptOut]] = defaultdict(list)
    for mv in moves:
        if mv.reverses_id is not None or mv.id in reversed_ids or mv.po_no is None:
            continue
        out[(mv.po_no, mv.po_line_no or 0)].append(
            s.ReceiptOut(
                movement_id=mv.id,
                received_on=mv.movement_date,
                qty=float(mv.qty),
                location_code=mv.location_code,
                location_name=locations.get(mv.location_code, mv.location_code),
                lot_no=mv.lot_no,
                expiry_date=mv.expiry_date,
                unit_cost=_f(mv.unit_cost),
                created_by=mv.created_by,
                added_to_stock=mv.id in added,
                why_not=why_not.get(mv.id),
            )
        )
    return out


def _line_out(
    line: POLineRecord, ctx: PlanningContext, rules: BusinessRules, receipts: list[s.ReceiptOut]
) -> s.POLineOut:
    inputs = ctx.inputs
    items = {i.item_code: i for i in inputs.items}
    item = items.get(line.item_code)
    overrides = {(o.po_no, o.line_no): o for o in inputs.eta_overrides}
    override = overrides.get((line.po_no, line.line_no))
    eta, eta_source, flags, late = (override.eta if override else None), None, list(line.flags), False
    if line.counted:
        po_input = next(p for p in inputs.po_lines if (p.po_no, p.line_no) == (line.po_no, line.line_no))
        vendor_code = item.vendor_code if item else line.vendor_code
        lead, _, _, _ = vendor_terms(
            next((v for v in inputs.vendors if v.vendor_code == vendor_code), None),
            next((v for v in inputs.vendor_settings if v.vendor_code == vendor_code), None),
            next((x for x in inputs.item_settings if x.item_code == line.item_code), None),
            rules,
        )
        arrival = po_arrival(po_input, lead, override, rules)
        eta, eta_source, flags, late = arrival.eta, arrival.eta_source, list(arrival.flags), arrival.is_late
    status = "late" if late else line.status
    return s.POLineOut(
        po_no=line.po_no,
        line_no=line.line_no,
        item_code=line.item_code,
        description=item.description if item else line.item_code,
        sell_uom=item.sell_uom if item else "CS",
        source=line.source,
        ordered=line.ordered,
        received=line.received,
        remaining=line.remaining,
        status=status,  # type: ignore[arg-type]
        counted=line.counted,
        eta=eta,
        eta_source=eta_source,
        bluetide_date=line.expected_date_system,
        shipped_on=line.shipped_on,
        container_no=line.container_no,
        cancel_reason=line.cancel_reason,
        unit_cost=line.unit_cost,
        flags=flags,
        receipts=receipts,
    )


def _po_status(lines: list[s.POLineOut]) -> str:
    statuses = {x.status for x in lines}
    if statuses == {"cancelled"}:
        return "cancelled"
    if statuses <= {"received", "cancelled"}:
        return "received"
    if "late" in statuses:
        return "late"
    if any(x.received >= EPSILON for x in lines):
        return "partly_received"
    if "shipped" in statuses:
        return "shipped"
    return "open"


def purchase_orders(
    db: Session, rules: BusinessRules, status: str = "open", q: str | None = None
) -> list[s.POOut]:
    """Every PO, BlueTide's and Dana's, as one list (R1-R6). status: open/late/received/cancelled/all."""
    ctx = build_context(db, rules)
    vendors = {v.vendor_code: v.name for v in ctx.inputs.vendors}
    headers = {po.po_no: po for po in db.scalars(select(m.PurchaseOrder)).all()}
    receipts = _receipts_by_line(db, ctx)
    by_po: dict[str, list[POLineRecord]] = defaultdict(list)
    for line in ctx.reconciled.lines:
        by_po[line.po_no].append(line)

    out = []
    for po_no, records in by_po.items():
        lines = [_line_out(r, ctx, rules, receipts.get((r.po_no, r.line_no), [])) for r in records]
        sources = {r.source for r in records}
        source = "both" if "both" in sources or len(sources) > 1 else sources.pop()
        header = headers.get(po_no)
        po_status = _po_status(lines)
        etas = [x.eta for x in lines if x.counted and x.eta is not None]
        out.append(
            s.POOut(
                po_no=po_no,
                vendor_code=header.vendor_code if header else records[0].vendor_code,
                vendor_name=vendors.get(header.vendor_code if header else records[0].vendor_code, po_no),
                order_date=header.order_date if header else min(r.order_date for r in records),
                source=source,  # type: ignore[arg-type]
                status=po_status,  # type: ignore[arg-type]
                expected_date=min(etas) if etas else None,
                note=header.note if header else None,
                created_by=header.created_by if header else None,
                lines=lines,
            )
        )

    if status == "open":
        out = [p for p in out if p.status in OPEN_STATUSES]
    elif status != "all":
        out = [p for p in out if p.status == status]
    if q:
        needle = q.strip().lower()
        out = [
            p
            for p in out
            if needle in p.po_no.lower()
            or needle in p.vendor_name.lower()
            or any(needle in x.item_code.lower() or needle in x.description.lower() for x in p.lines)
        ]
    rank = {"late": 0, "open": 1, "shipped": 1, "partly_received": 1, "received": 2, "cancelled": 3}
    out.sort(key=lambda p: (rank[p.status], p.expected_date or date.max, p.po_no))
    return out


def purchase_order(db: Session, rules: BusinessRules, po_no: str) -> s.POOut:
    found = next((p for p in purchase_orders(db, rules, "all") if p.po_no == po_no), None)
    if found is None:
        raise AppError(404, "po_not_found", f"We couldn't find PO {po_no}.")
    return found


# ---- Writing: POs ----------------------------------------------------------------------------


def _next_po_no(db: Session, rules: BusinessRules) -> str:
    prefix = rules.app_po_prefix
    numbers = [
        int(n[len(prefix) :])
        for n in db.scalars(select(m.PurchaseOrder.po_no).where(m.PurchaseOrder.po_no.startswith(prefix)))
        if n[len(prefix) :].isdigit()
    ]
    return f"{prefix}{max(numbers, default=0) + 1:05d}"


def last_cost(db: Session, item_code: str) -> float | None:
    """The most recent cost per selling unit: Dana's last PO, then BlueTide's last PO, then a lot's cost."""
    app = db.execute(
        select(m.PurchaseOrderLineApp.unit_cost)
        .join(m.PurchaseOrder, m.PurchaseOrder.id == m.PurchaseOrderLineApp.po_id)
        .where(m.PurchaseOrderLineApp.item_code == item_code, m.PurchaseOrderLineApp.unit_cost.is_not(None))
        .order_by(m.PurchaseOrder.order_date.desc(), m.PurchaseOrder.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if app is not None:
        return float(app)
    item = db.get(m.Item, item_code)
    if item is not None:
        line = db.scalars(
            select(m.PurchaseOrderLine)
            .where(m.PurchaseOrderLine.item_code == item_code, m.PurchaseOrderLine.unit_cost.is_not(None))
            .order_by(m.PurchaseOrderLine.order_date.desc())
            .limit(1)
        ).first()
        if line is not None:
            cost = cost_to_sell_uom(line.unit_cost, line.uom, item.sell_uom, item.lb_per_case)
            if cost is not None:
                return float(cost)
    lot_cost = db.execute(
        select(m.InventoryLot.unit_cost_sell_uom)
        .where(m.InventoryLot.item_code == item_code, m.InventoryLot.unit_cost_sell_uom.is_not(None))
        .limit(1)
    ).scalar_one_or_none()
    return float(lot_cost) if lot_cost is not None else None


def create_purchase_order(db: Session, rules: BusinessRules, body: s.POCreateIn) -> s.POOut:
    ctx = build_context(db, rules)
    as_of = rules.as_of_date
    vendors = {v.vendor_code: v for v in ctx.inputs.vendors}
    items = {i.item_code: i for i in ctx.inputs.items}
    vendor_code = canonical_code(body.vendor_code)
    if vendor_code not in vendors:
        raise AppError(404, "vendor_not_found", f"We couldn't find supplier {body.vendor_code!r}.")
    order_date = body.order_date or as_of
    if order_date > as_of:
        raise AppError(422, "date_in_future", "The order date can't be after today.")

    codes = [canonical_code(line.item_code) for line in body.lines]
    for raw, code in zip(body.lines, codes, strict=True):
        if code not in items:
            raise AppError(404, "item_not_found", f"We couldn't find item {raw.item_code!r}.")
    duplicates = {c for c in codes if codes.count(c) > 1}
    if duplicates:
        raise AppError(422, "duplicate_item", f"{', '.join(sorted(duplicates))} is on this PO twice.")

    setting = next((x for x in ctx.inputs.vendor_settings if x.vendor_code == vendor_code), None)
    lead, _, _, _ = vendor_terms(vendors[vendor_code], setting, None, rules)
    expected = body.expected_date or order_date + timedelta(days=lead)
    if expected < as_of:
        raise AppError(
            422,
            "date_in_past",
            f"Ordered {day(order_date)} with {lead} days to arrive, this PO should already be here. "
            "Type the arrival date the supplier gave you.",
        )

    po_no = canonical_code(body.po_no) if body.po_no and body.po_no.strip() else _next_po_no(db, rules)
    if db.execute(select(m.PurchaseOrder).where(m.PurchaseOrder.po_no == po_no)).first() is not None:
        raise AppError(409, "po_exists", f"There's already a PO {po_no} in the app.")

    actor = current_actor()
    po = m.PurchaseOrder(
        po_no=po_no,
        vendor_code=vendor_code,
        order_date=order_date,
        note=body.note,
        created_by=actor,
        updated_by=actor,
    )
    db.add(po)
    db.flush()
    lines_after = []
    for n, (line, code) in enumerate(zip(body.lines, codes, strict=True), start=1):
        cost = line.unit_cost if line.unit_cost is not None else last_cost(db, code)
        db.add(
            m.PurchaseOrderLineApp(
                po_id=po.id,
                line_no=n,
                item_code=code,
                qty_ordered=Decimal(str(line.qty)),
                unit_cost=Decimal(str(cost)) if cost is not None else None,
            )
        )
        override = db.get(m.PoEtaOverride, (po_no, n))
        if override is None:
            db.add(
                m.PoEtaOverride(
                    po_no=po_no, line_no=n, eta=expected, note="Entered with the PO", updated_by=actor
                )
            )
        else:
            override.eta, override.updated_by = expected, actor
        lines_after.append({"line_no": n, "item_code": code, "qty": line.qty, "unit_cost": cost})

    cleared = []
    if body.clear_handled_notes:
        for note in db.scalars(
            select(m.HandledFlag).where(
                m.HandledFlag.item_code.in_(codes), m.HandledFlag.cleared_at.is_(None)
            )
        ).all():
            before = {"cleared_at": None}
            note.cleared_at = utc_now()  # type: ignore[assignment]
            note.cleared_by = actor
            note.clear_reason = f"Replaced by {po_no}"
            cleared.append(note.id)
            record_change(
                db,
                action="handled.clear",
                entity_type="handled_flag",
                entity_id=str(note.id),
                before=before,
                after={"cleared_by": actor, "clear_reason": note.clear_reason},
            )
    record_change(
        db,
        action="purchase_order.create",
        entity_type="purchase_order",
        entity_id=po_no,
        before=None,
        after={
            "vendor_code": vendor_code,
            "order_date": order_date,
            "expected_date": expected,
            "lines": lines_after,
            "note": body.note,
            "cleared_handled_notes": cleared,
        },
    )
    db.commit()
    return purchase_order(db, rules, po_no)


def _line(
    db: Session, rules: BusinessRules, po_no: str, line_no: int
) -> tuple[POLineRecord, PlanningContext]:
    ctx = build_context(db, rules)
    line = next((x for x in ctx.reconciled.lines if (x.po_no, x.line_no) == (po_no, line_no)), None)
    if line is None:
        raise AppError(404, "po_line_not_found", f"We couldn't find {po_no} line {line_no}.")
    return line, ctx


def _status_dict(row: m.PoLineStatus | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "status": row.status,
        "shipped_on": row.shipped_on,
        "container_no": row.container_no,
        "cancel_reason": row.cancel_reason,
        "note": row.note,
    }


def _set_status(db: Session, po_no: str, line_no: int, **values: Any) -> tuple[dict | None, m.PoLineStatus]:
    row = db.get(m.PoLineStatus, (po_no, line_no))
    before = _status_dict(row)
    actor = current_actor()
    if row is None:
        row = m.PoLineStatus(po_no=po_no, line_no=line_no, updated_by=actor, **values)
        db.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_by = actor
        row.updated_at = utc_now()  # type: ignore[assignment]
    db.flush()
    return before, row


def ship_line(db: Session, rules: BusinessRules, po_no: str, line_no: int, body: s.POShipIn) -> s.POOut:
    line, _ = _line(db, rules, po_no, line_no)
    if line.status in ("cancelled", "received"):
        raise AppError(
            409, "line_closed", f"{po_no} line {line_no} is {line.status}, so it can't be shipped."
        )
    shipped_on = body.shipped_on or rules.as_of_date
    if shipped_on > rules.as_of_date:
        raise AppError(422, "date_in_future", "The shipped date can't be after today.")
    if body.eta is not None and body.eta < rules.as_of_date:
        raise AppError(422, "date_in_past", "The new arrival date has already passed.")
    before, row = _set_status(
        db,
        po_no,
        line_no,
        status="shipped",
        shipped_on=shipped_on,
        container_no=body.container_no,
        cancel_reason=None,
        note=body.note,
    )
    if body.eta is not None:
        override = db.get(m.PoEtaOverride, (po_no, line_no))
        if override is None:
            db.add(m.PoEtaOverride(po_no=po_no, line_no=line_no, eta=body.eta, updated_by=current_actor()))
        else:
            override.eta, override.updated_by = body.eta, current_actor()
            override.updated_at = utc_now()  # type: ignore[assignment]
    after = _status_dict(row) or {}
    after["eta"] = body.eta
    record_change(
        db,
        action="po_line.ship",
        entity_type="po_line",
        entity_id=f"{po_no}/{line_no}",
        before=before,
        after=after,
    )
    db.commit()
    return purchase_order(db, rules, po_no)


def cancel_line(db: Session, rules: BusinessRules, po_no: str, line_no: int, body: s.POCancelIn) -> s.POOut:
    line, _ = _line(db, rules, po_no, line_no)
    if line.status == "cancelled":
        raise AppError(409, "already_cancelled", f"{po_no} line {line_no} is already cancelled.")
    if line.status == "received":
        raise AppError(
            409, "line_closed", f"{po_no} line {line_no} has been received, so it can't be cancelled."
        )
    before, row = _set_status(
        db, po_no, line_no, status="cancelled", cancel_reason=body.reason, shipped_on=None, container_no=None
    )
    record_change(
        db,
        action="po_line.cancel",
        entity_type="po_line",
        entity_id=f"{po_no}/{line_no}",
        before=before,
        after=_status_dict(row),
    )
    db.commit()
    return purchase_order(db, rules, po_no)


def reopen_line(db: Session, rules: BusinessRules, po_no: str, line_no: int) -> s.POOut:
    """Undo "shipped" or "cancelled" on a line."""
    _line(db, rules, po_no, line_no)
    row = db.get(m.PoLineStatus, (po_no, line_no))
    if row is None:
        raise AppError(409, "nothing_to_undo", f"{po_no} line {line_no} isn't marked shipped or cancelled.")
    before = _status_dict(row)
    db.delete(row)
    record_change(
        db,
        action="po_line.reopen",
        entity_type="po_line",
        entity_id=f"{po_no}/{line_no}",
        before=before,
        after=None,
    )
    db.commit()
    return purchase_order(db, rules, po_no)


def receive_line(db: Session, rules: BusinessRules, po_no: str, line_no: int, body: s.POReceiveIn) -> s.POOut:
    line, ctx = _line(db, rules, po_no, line_no)
    as_of = rules.as_of_date
    if line.status == "cancelled":
        raise AppError(409, "line_closed", f"{po_no} line {line_no} is cancelled. Reopen it first.")
    location = db.get(m.Location, canonical_code(body.location_code))
    if location is None:
        raise AppError(404, "location_not_found", f"We couldn't find the building {body.location_code!r}.")
    if not (location.is_sellable or location.may_return_to_stock):
        raise AppError(422, "location_not_allowed", f"Stock can't be received into {location.name}.")
    received_on = body.received_on or as_of
    if received_on > as_of:
        raise AppError(422, "date_in_future", "The received date can't be after today.")
    if received_on < line.order_date:
        raise AppError(422, "date_before_order", "The received date can't be before the order date.")
    if body.expiry_date <= received_on:
        raise AppError(422, "already_expired", "The expiry date must be after the day it arrived.")
    unit = next((i.sell_uom for i in ctx.inputs.items if i.item_code == line.item_code), "CS")
    word = "cases" if unit == "CS" else "lb"
    if body.qty > line.remaining + EPSILON and not body.allow_over_receipt:
        raise AppError(
            422,
            "more_than_ordered",
            f"Only {round(line.remaining):,} {word} are still to come on this line. "
            'If more really arrived, tick "More than ordered".',
        )
    cost = body.unit_cost if body.unit_cost is not None else (line.unit_cost or last_cost(db, line.item_code))
    move = m.StockMovement(
        movement_date=received_on,
        kind="receipt",
        item_code=line.item_code,
        location_code=location.code,
        lot_no=body.lot_no.strip(),
        qty=Decimal(str(body.qty)),
        expiry_date=body.expiry_date,
        unit_cost=Decimal(str(cost)) if cost is not None else None,
        po_no=po_no,
        po_line_no=line_no,
        note=body.note,
        created_by=current_actor(),
    )
    db.add(move)
    db.flush()
    record_change(
        db,
        action="stock.receive",
        entity_type="stock_movement",
        entity_id=str(move.id),
        before=None,
        after={
            "po": f"{po_no}/{line_no}",
            "item_code": line.item_code,
            "qty": body.qty,
            "location": location.code,
            "lot_no": move.lot_no,
            "expiry_date": body.expiry_date,
            "received_on": received_on,
        },
    )
    db.commit()
    return purchase_order(db, rules, po_no)


def undo_movement(db: Session, movement_id: int, body: s.UndoIn) -> s.MovementOut:
    """Reverse a receipt (or, later, any movement) with a new row. The original stays in the history."""
    move = db.get(m.StockMovement, movement_id)
    if move is None:
        raise AppError(404, "movement_not_found", f"We couldn't find stock change #{movement_id}.")
    if move.reverses_id is not None:
        raise AppError(409, "is_an_undo", "That entry is itself an undo.")
    if db.execute(select(m.StockMovement.id).where(m.StockMovement.reverses_id == move.id)).first():
        raise AppError(409, "already_undone", "That has already been undone.")
    if move.shipment_id is not None:
        raise AppError(
            409, "is_a_pick", 'That\'s part of a shipment. Use "Undo shipped" on the order instead.'
        )
    # A move has two halves (out of one building, into another): undo both together.
    partner = None
    if move.kind in ("move_out", "move_in"):
        partner = db.execute(
            select(m.StockMovement).where(
                (m.StockMovement.id == move.pair_id) | (m.StockMovement.pair_id == move.id),
                m.StockMovement.id != move.id,
            )
        ).scalar_one_or_none()
    if partner is not None:
        db.add(
            m.StockMovement(
                movement_date=partner.movement_date,
                kind=partner.kind,
                item_code=partner.item_code,
                location_code=partner.location_code,
                lot_no=partner.lot_no,
                qty=-partner.qty,
                expiry_date=partner.expiry_date,
                unit_cost=partner.unit_cost,
                reverses_id=partner.id,
                note=body.reason,
                created_by=current_actor(),
            )
        )
    rev = m.StockMovement(
        movement_date=move.movement_date,
        kind=move.kind,
        item_code=move.item_code,
        location_code=move.location_code,
        lot_no=move.lot_no,
        qty=-move.qty,
        expiry_date=move.expiry_date,
        unit_cost=move.unit_cost,
        po_no=move.po_no,
        po_line_no=move.po_line_no,
        reverses_id=move.id,
        note=body.reason,
        created_by=current_actor(),
    )
    db.add(rev)
    db.flush()
    record_change(
        db,
        action="stock.undo",
        entity_type="stock_movement",
        entity_id=str(move.id),
        before={
            "qty": float(move.qty),
            "kind": move.kind,
            "lot_no": move.lot_no,
            "pair": partner.id if partner else None,
        },
        after={"undone_by_movement": rev.id, "reason": body.reason},
    )
    db.commit()
    return s.MovementOut(
        id=rev.id,
        movement_date=rev.movement_date,
        kind=rev.kind,
        item_code=rev.item_code,
        location_code=rev.location_code,
        lot_no=rev.lot_no,
        qty=float(rev.qty),
        reverses_id=rev.reverses_id,
        created_by=rev.created_by,
    )


# ---- Writing: suppliers and items --------------------------------------------------------


def _vendor_codes(db: Session) -> set[str]:
    return set(db.scalars(select(m.Vendor.vendor_code)).all()) | set(
        db.scalars(select(m.AppVendor.vendor_code)).all()
    )


def _code_from_name(name: str, taken: set[str]) -> str:
    words = re.findall(r"[A-Za-z0-9]+", name)
    base = "".join(w[0] for w in words).upper()[:4] or "SUP"
    if len(base) < 3:
        base = (words[0][:3] if words else "SUP").upper()
    code, n = base, 2
    while code in taken:
        code, n = f"{base}{n}", n + 1
    return code


def _check_days(value: int, label: str, rules: BusinessRules) -> None:
    if not (rules.setting_days_min <= value <= rules.setting_days_max):
        raise AppError(
            422,
            "out_of_range",
            f"The {label} must be between {rules.setting_days_min} and {rules.setting_days_max} days.",
        )


def create_vendor(db: Session, rules: BusinessRules, body: s.VendorCreateIn) -> str:
    taken = _vendor_codes(db)
    name = body.name.strip()
    same_name = next(
        (
            code
            for code, existing in [
                *db.execute(select(m.Vendor.vendor_code, m.Vendor.name)).all(),
                *db.execute(select(m.AppVendor.vendor_code, m.AppVendor.name)).all(),
            ]
            if existing.strip().lower() == name.lower()
        ),
        None,
    )
    if same_name is not None:
        raise AppError(409, "vendor_exists", f"There's already a supplier called {name} (code {same_name}).")
    code = (
        canonical_code(body.vendor_code)
        if body.vendor_code and body.vendor_code.strip()
        else _code_from_name(body.name, taken)
    )
    if code in taken:
        raise AppError(409, "vendor_exists", f"There's already a supplier with the code {code}.")
    cycle = body.order_cycle_days if body.order_cycle_days is not None else rules.default_order_cycle_days
    _check_days(body.lead_time_days, "time to arrive", rules)
    _check_days(body.cushion_days, "cushion", rules)
    _check_days(cycle, "order cycle", rules)
    actor = current_actor()
    db.add(
        m.AppVendor(
            vendor_code=code,
            name=body.name.strip(),
            country=(body.country or "").strip() or None,
            note=body.note,
            created_by=actor,
            updated_by=actor,
        )
    )
    db.add(
        m.VendorSetting(
            vendor_code=code,
            lead_time_days=body.lead_time_days,
            safety_days=body.cushion_days,
            order_cycle_days=cycle,
            source=f"Set by {actor}",
            note=body.note,
            updated_by=actor,
        )
    )
    record_change(
        db,
        action="vendor.create",
        entity_type="vendor",
        entity_id=code,
        before=None,
        after={
            "name": body.name.strip(),
            "country": body.country,
            "lead_time_days": body.lead_time_days,
            "cushion_days": body.cushion_days,
            "order_cycle_days": cycle,
        },
    )
    db.commit()
    return code


def _item_dict(item: m.AppItem) -> dict[str, Any]:
    return {
        "description": item.description,
        "category": item.category,
        "sell_uom": item.sell_uom,
        "lb_per_case": _f(item.lb_per_case),
        "vendor_code": item.vendor_code,
        "status": item.status,
        "note": item.note,
    }


def _validate_item(db: Session, sell_uom: str, lb_per_case: float | None, vendor_code: str) -> None:
    if vendor_code not in _vendor_codes(db):
        raise AppError(404, "vendor_not_found", f"We couldn't find supplier {vendor_code!r}. Add it first.")
    if sell_uom == "CS" and not lb_per_case:
        raise AppError(
            422,
            "lb_per_case_needed",
            "How many pounds are in a case? It's needed to compare this item with others in its category.",
        )


def create_item(db: Session, body: s.ItemCreateIn) -> s.AppItemOut:
    code = canonical_code(body.item_code)
    if db.get(m.Item, code) is not None or db.get(m.AppItem, code) is not None or db.get(m.ItemAlias, code):
        raise AppError(409, "item_exists", f"There's already an item {code}. Open it to change its details.")
    vendor_code = canonical_code(body.vendor_code)
    _validate_item(db, body.sell_uom, body.lb_per_case, vendor_code)
    actor = current_actor()
    item = m.AppItem(
        item_code=code,
        description=body.description.strip(),
        category=normalize_category(body.category),
        sell_uom=body.sell_uom,
        lb_per_case=Decimal(str(body.lb_per_case)) if body.lb_per_case else None,
        vendor_code=vendor_code,
        status=body.status,
        note=body.note,
        created_by=actor,
        updated_by=actor,
    )
    db.add(item)
    db.flush()
    record_change(
        db, action="item.create", entity_type="item", entity_id=code, before=None, after=_item_dict(item)
    )
    db.commit()
    return item_details(db, code)


def update_item_details(db: Session, code: str, body: s.ItemDetailsPatchIn) -> s.AppItemOut:
    """Dana's version of an item's details. For a BlueTide item, her copy wins from now on."""
    sent = body.model_fields_set
    if not sent:
        raise AppError(422, "nothing_to_change", "Send at least one value to change.")
    app_item = db.get(m.AppItem, code)
    bluetide = db.get(m.Item, code)
    if app_item is None and bluetide is None:
        raise AppError(404, "item_not_found", f"We couldn't find item {code}.")
    actor = current_actor()
    before = _item_dict(app_item) if app_item is not None else None
    if app_item is None:
        assert bluetide is not None
        app_item = m.AppItem(
            item_code=code,
            description=bluetide.description,
            category=bluetide.category,
            sell_uom=bluetide.sell_uom,
            lb_per_case=bluetide.lb_per_case,
            vendor_code=bluetide.vendor_code,
            status="discontinued" if bluetide.lifecycle_status == "discontinued" else "active",
            note=None,
            created_by=actor,
            updated_by=actor,
        )
        db.add(app_item)
        before = {"source": "BlueTide", **_item_dict(app_item)}
    for field in sent:
        value = getattr(body, field)
        if field in ("description", "category", "sell_uom", "vendor_code", "status") and value is None:
            raise AppError(422, "missing_value", f"The {field.replace('_', ' ')} can't be blank.")
        if field == "category":
            value = normalize_category(value)
        if field == "vendor_code":
            value = canonical_code(value)
        if field == "lb_per_case":
            value = Decimal(str(value)) if value else None
        setattr(app_item, field, value)
    _validate_item(db, app_item.sell_uom, _f(app_item.lb_per_case), app_item.vendor_code)
    app_item.updated_by = actor
    app_item.updated_at = utc_now()  # type: ignore[assignment]
    db.flush()
    record_change(
        db,
        action="item.update",
        entity_type="item",
        entity_id=code,
        before=before,
        after=_item_dict(app_item),
    )
    db.commit()
    return item_details(db, code)


def item_details(db: Session, code: str) -> s.AppItemOut:
    found = next((x for x in all_item_details(db) if x.item_code == code), None)
    if found is None:
        raise AppError(404, "item_not_found", f"We couldn't find item {code}.")
    return found


def all_item_details(db: Session) -> list[s.AppItemOut]:
    """Every item, BlueTide's and Dana's, with where its details come from."""
    mine = {a.item_code: a for a in db.scalars(select(m.AppItem)).all()}
    out = []
    for i in db.scalars(select(m.Item)).all():
        a = mine.pop(i.item_code, None)
        if a is not None:
            out.append(_app_item_out(a, "both"))
        else:
            out.append(
                s.AppItemOut(
                    item_code=i.item_code,
                    description=i.description,
                    category=i.category,
                    sell_uom=i.sell_uom,
                    lb_per_case=_f(i.lb_per_case),
                    vendor_code=i.vendor_code,
                    status="discontinued" if i.lifecycle_status == "discontinued" else "active",
                    source="bluetide",
                    note=None,
                    updated_at=None,
                    updated_by=None,
                )
            )
    out.extend(_app_item_out(a, "app") for a in mine.values())
    return sorted(out, key=lambda x: x.item_code)


def _app_item_out(a: m.AppItem, source: str) -> s.AppItemOut:
    return s.AppItemOut(
        item_code=a.item_code,
        description=a.description,
        category=a.category,
        sell_uom=a.sell_uom,
        lb_per_case=_f(a.lb_per_case),
        vendor_code=a.vendor_code,
        status=a.status,
        source=source,  # type: ignore[arg-type]
        note=a.note,
        updated_at=a.updated_at,
        updated_by=a.updated_by,
    )
