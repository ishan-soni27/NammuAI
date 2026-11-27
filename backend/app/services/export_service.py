"""Download to Excel (Phase 6 step 4; P0 #13): every list as a CSV Excel opens cleanly.

Each export is built from the same service the screen uses (planning_service, harbor_service), so a
download always matches what Dana sees. Excel-friendly on purpose:
  - UTF-8 with a byte-order mark (Excel otherwise garbles "Austral Frío"),
  - dates as 2026-11-16 (Excel reads them as dates in any locale),
  - numbers without units, and the unit in its own column (so she can add them up),
  - statuses in her words ("Too late", not TOO_LATE),
  - CRLF line ends, quoted only where needed.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable, Iterable
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.business_rules import BusinessRules
from app.db import models as m
from app.loader.report import TRAP_TITLES
from app.services import harbor_service, planning_service
from app.services.planning_inputs import latest_load

STATUS_WORDS = {
    "OUT_OF_STOCK": "Out of stock (estimated)",
    "TOO_LATE": "Too late",
    "OVERDUE": "Overdue",
    "ORDER_THIS_WEEK": "Order this week",
    "ORDER_SOON": "Order soon",
    "OK": "Fine",
    "NO_RECENT_SALES": "No recent sales",
    "NOT_PLANNED": "Not planned",
}
TAG_WORDS = {
    "EXPIRED": "Expired",
    "STOPPED_SELLING": "Stopped selling",
    "INSIDE_SIX_MONTHS": "Inside six-month line",
    "LONG_AT_HARBOR": "Long at Harbor",
    "OVERSTOCK": "Overstock",
}
UNIT_WORDS = {"CS": "cases", "LB": "lb"}


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        rounded = round(value, 2)
        return int(rounded) if rounded == int(rounded) else rounded
    if isinstance(value, date):
        return value.isoformat()
    return value


def _csv(header: list[str], rows: Iterable[list[Any]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([_cell(v) for v in row])
    return "﻿" + out.getvalue()


def _unit(uom: str) -> str:
    return UNIT_WORDS.get(uom.upper(), uom.lower())


def order_list(db: Session, rules: BusinessRules) -> str:
    """Every item and what to do about it (filter the Status column in Excel)."""
    header = [
        "item_code",
        "item",
        "status",
        "runs_out",
        "order_by",
        "order_at_least",
        "unit",
        "supplier",
        "country",
        "weeks_to_arrive",
        "cushion_weeks",
        "new_order_arrives",
        "back_in_stock",
        "short_until_then",
        "can_sell",
        "can_sell_now_estimated",
        "on_hold",
        "promised_to_customers",
        "on_the_way",
        "on_late_pos",
        "only_covered_by_late_po",
        "handled_note",
    ]
    rank = {k: i for i, k in enumerate(STATUS_WORDS)}
    cards = sorted(
        planning_service.all_items(db, rules),
        key=lambda c: (rank.get(c.status, 9), c.run_out_date or date.max),
    )
    rows = (
        [
            c.item_code,
            c.description,
            "Handled" if c.handled_note else STATUS_WORDS.get(c.status, c.status),
            c.run_out_date,
            c.order_by_date,
            c.order_at_least,
            _unit(c.sell_uom),
            c.vendor_name,
            c.country,
            c.lead_time_days / 7,
            c.cushion_days / 7,
            c.new_order_arrival,
            c.back_in_stock_date,
            c.short_qty,
            c.sellable,
            c.sellable_now,
            c.on_hold,
            c.promised_to_customers,
            c.on_the_way,
            c.late_qty,
            c.covered_only_by_late_po,
            c.handled_note.note if c.handled_note else None,
        ]
        for c in cards
    )
    return _csv(header, rows)


def stuck_list(db: Session, rules: BusinessRules) -> str:
    """One row per lot on the stuck list, worst problem first, Harbor lots marked."""
    header = [
        "item_code",
        "item",
        "problem",
        "all_problems",
        "lot",
        "building",
        "at_harbor",
        "quantity",
        "unit",
        "expires",
        "value_at_cost",
    ]
    rows = []
    for item in planning_service.dashboard(db, rules).stuck_items:
        for lot in sorted(item.lots, key=lambda x: (not x.at_harbor, x.expiry_date or date.max)):
            rows.append(
                [
                    item.item_code,
                    item.description,
                    TAG_WORDS.get(lot.primary_tag, lot.primary_tag),
                    "; ".join(TAG_WORDS.get(t, t) for t in lot.tags),
                    lot.lot_no,
                    lot.location_name,
                    lot.at_harbor,
                    lot.qty,
                    _unit(item.sell_uom),
                    lot.expiry_date,
                    lot.value_at_cost,
                ]
            )
    return _csv(header, rows)


def purchase_orders(db: Session, rules: BusinessRules) -> str:
    """BlueTide's open PO lines, as the On the way page shows them: our date, BlueTide's, and late."""
    header = [
        "po_no",
        "line",
        "supplier",
        "item_code",
        "item",
        "still_to_come",
        "unit",
        "arrives",
        "arrival_set_by",
        "bluetide_date",
        "late",
        "notes",
    ]
    rows = (
        [
            x.po_no,
            x.line_no,
            x.vendor_name,
            x.item_code,
            x.description,
            x.qty,
            _unit(x.sell_uom),
            x.eta,
            x.eta_source,
            x.bluetide_date,
            x.is_late,
            "; ".join(x.flags),
        ]
        for x in planning_service.on_the_way(db, rules)
    )
    return _csv(header, rows)


def data_notes(db: Session, rules: BusinessRules) -> str:
    """Every change the loader made to BlueTide's files in the latest load, with file and line."""
    header = [
        "file",
        "line",
        "problem",
        "trap",
        "what_we_did",
        "item_code",
        "field",
        "original",
        "became",
        "note",
    ]
    load = latest_load(db)
    if load.load_run_id is None:
        return _csv(header, [])
    issues = db.scalars(
        select(m.DataIssue)
        .where(m.DataIssue.load_run_id == load.load_run_id)
        .order_by(m.DataIssue.trap_id, m.DataIssue.source_file, m.DataIssue.source_line_number)
    ).all()
    action = {"excluded": "Left out", "corrected": "Corrected", "flagged": "Flagged for you"}
    rows = (
        [
            i.source_file,
            i.source_line_number,
            TRAP_TITLES.get(i.trap_id or "", "Row error"),
            i.trap_id,
            action.get(i.action, i.action),
            i.item_code,
            i.field,
            i.original_value,
            i.new_value,
            i.message,
        ]
        for i in issues
    )
    return _csv(header, rows)


def harbor_storage(db: Session, rules: BusinessRules) -> str:
    """Dana's Harbor storage table (ADR-031), exactly as each row was worked out, newest first."""
    header = [
        "saved_for",
        "saved_at_utc",
        "saved_by",
        "what",
        "item_code",
        "item",
        "cases",
        "lots",
        "cases_per_pallet",
        "pallets",
        "dollars_per_pallet_month",
        "dollars_per_month",
    ]
    what = {"at_harbor": "At Harbor that day", "what_if": "What-if amount"}
    rows = (
        [
            r.as_of_date,
            r.created_at.strftime("%Y-%m-%d %H:%M"),
            r.created_by,
            what.get(r.kind, r.kind),
            r.item_code,
            r.description,
            float(r.cases),
            r.lots,
            r.cases_per_pallet,
            r.pallets,
            float(r.rate_per_pallet_month),
            float(r.cost_per_month),
        ]
        for r in harbor_service.saved_rows(db)
    )
    return _csv(header, rows)


EXPORTS: dict[str, Callable[[Session, BusinessRules], str]] = {
    "order-list": order_list,
    "stuck-list": stuck_list,
    "purchase-orders": purchase_orders,
    "data-notes": data_notes,
    "harbor-storage": harbor_storage,
}
