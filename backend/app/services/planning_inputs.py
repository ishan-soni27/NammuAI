"""Build the planning engine's inputs from loaded data.

Two sources, one shape (PlanningInputs):
  - inputs_from_dataset: the loader's clean dataset, no database (golden tests, scripts).
  - inputs_from_db:      the database, for the API (Phase 4). The BlueTide part (clean layer) only
                         changes when the loader runs, so it is cached per load run; Dana's edits
                         (app layer: vendor settings, PO dates, handled notes, item settings) are
                         read fresh on every request, so a change shows up immediately (ADR-004).

Only REAL demand reaches the engine (§6.2: no transfers, samples, credits, cancellations, the
cruise one-off or fresh), and only open PO lines with something still to come (T25).

Dana's own records (Phase 6, ADR-027) join here too: suppliers and items she added (hers win on
the same code), POs she created, lines she marked shipped or cancelled, and receipts. BlueTide's
side and hers are matched by planning/records.py (rules R1-R6), so nothing is counted twice. With
no BlueTide load at all, the plan is built from her records alone.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.business_rules import BusinessRules
from app.db import models as m
from app.loader.classify import SaleFacts, classify_sale
from app.loader.convert import to_sell_uom
from app.loader.types import CleanDataset, VendorSettingSeed
from app.planning.records import (
    AppPOLine,
    AppShipmentLine,
    BlueTidePOLine,
    LineStatusInput,
    LotRecord,
    MovementInput,
    ReceiptInput,
    Reconciled,
    ShipmentsReconciled,
    apply_movements,
    reconcile_pos,
    reconcile_shipments,
)
from app.planning.types import (
    EtaOverrideInput,
    HandledNoteInput,
    ItemInput,
    ItemSettingInput,
    LocationInput,
    LotInput,
    PlanningInputs,
    POLineInput,
    SaleInput,
    StockoutInput,
    VendorInput,
    VendorSettingInput,
)


def inputs_from_dataset(
    dataset: CleanDataset,
    vendor_settings: tuple[VendorSettingSeed, ...],
    *,
    eta_overrides: tuple[EtaOverrideInput, ...] = (),
    handled_notes: tuple[HandledNoteInput, ...] = (),
    item_settings: tuple[ItemSettingInput, ...] = (),
) -> PlanningInputs:
    customers = {c.customer_code: c.name for c in dataset.customers}
    return PlanningInputs(
        items=tuple(
            ItemInput(
                item_code=i.item_code,
                description=i.description,
                category=i.category,
                sell_uom=i.sell_uom,
                lb_per_case=float(i.lb_per_case) if i.lb_per_case is not None else None,
                vendor_code=i.vendor_code,
                lifecycle_status=i.lifecycle_status,
                lifecycle_reason=i.lifecycle_reason,
            )
            for i in dataset.items
        ),
        vendors=tuple(
            VendorInput(v.vendor_code, v.name, v.country, v.lead_time_days_system) for v in dataset.vendors
        ),
        vendor_settings=tuple(
            VendorSettingInput(s.vendor_code, s.lead_time_days, s.safety_days, s.order_cycle_days)
            for s in vendor_settings
        ),
        item_settings=item_settings,
        locations=tuple(
            LocationInput(x.code, x.is_sellable, x.may_return_to_stock, x.is_third_party_storage)
            for x in dataset.locations
        ),
        lots=tuple(
            LotInput(
                item_code=lot.item_code,
                location_code=lot.location_code,
                lot_no=lot.lot_no,
                qty=float(lot.qty_sell_uom) if lot.qty_sell_uom is not None else None,
                expiry_date=lot.expiry_date,
                is_adjustment=lot.is_adjustment,
                unit_cost=float(lot.unit_cost_sell_uom) if lot.unit_cost_sell_uom is not None else None,
            )
            for lot in dataset.lots
        ),
        sales=tuple(
            SaleInput(
                item_code=s.item_code,
                order_no=s.order_no,
                customer_name=customers.get(s.customer_code, s.customer_code),
                order_date=s.order_date,
                ship_date=s.ship_date,
                qty=float(s.qty),
                is_open=s.status == "OPEN",
            )
            for s in dataset.sales
            if s.demand_class == "real_demand"
        ),
        po_lines=tuple(
            POLineInput(
                po_no=p.po_no,
                line_no=p.line_no,
                item_code=p.item_code,
                vendor_code=p.vendor_code,
                order_date=p.order_date,
                expected_date_system=p.expected_date_system,
                qty_remaining=float(p.qty_remaining_sell_uom),
            )
            for p in dataset.po_lines
            if p.status == "open" and p.qty_remaining_sell_uom and p.qty_remaining_sell_uom > 0
        ),
        eta_overrides=eta_overrides,
        handled_notes=handled_notes,
        stockouts=tuple(
            StockoutInput(s.item_code, s.start_date, s.end_date) for s in dataset.stockout_periods
        ),
    )


# ---- From the database -------------------------------------------------------------------


@dataclass(frozen=True)
class LoadInfo:
    load_run_id: int | None
    snapshot_date: date | None  # the on-hand snapshot the numbers are based on
    finished_at: datetime | None


@dataclass(frozen=True)
class BlueTideFacts:
    """What BlueTide says beyond the planning inputs, for matching Dana's records (ADR-027).

    The planning inputs keep only open PO lines with something to come; matching also needs the
    received, complete and cancelled ones, and which lots are in the stock count.
    """

    po_lines: tuple[BlueTidePOLine, ...]
    snapshot_lots: frozenset[tuple[str, str, str]]  # (item, location, lot) in the stock count
    orders: dict[tuple[str, str], str]  # (order no, item) -> INVOICED / OPEN / CANCELLED, every sales line
    customers: dict[str, tuple[str, str]]  # code -> (name, customer type)
    excluded_orders: frozenset[str]  # data/reference/excluded_orders.csv (T20)


@dataclass(frozen=True)
class PlanningContext:
    """Everything one request needs: the engine inputs plus how Dana's records were matched."""

    inputs: PlanningInputs
    load: LoadInfo
    reconciled: Reconciled
    app_item_codes: frozenset[str]
    app_vendor_codes: frozenset[str]
    lot_records: tuple[LotRecord, ...] = ()  # the lots the plan counts, with where each came from
    shipments: ShipmentsReconciled | None = None
    movement_flags: tuple[str, ...] = ()


# latest load run id -> (clean-layer inputs, BlueTide facts); size 1
_clean_cache: dict[int, tuple[PlanningInputs, BlueTideFacts]] = {}


def latest_load(session: Session) -> LoadInfo:
    """The most recent successful load: its id keys the cache; the snapshot date is shown on screen."""
    row = session.execute(
        select(m.LoadRun.id, m.LoadRun.finished_at, m.LoadRun.summary)
        .where(m.LoadRun.status == "succeeded")
        .order_by(m.LoadRun.id.desc())
        .limit(1)
    ).first()
    if row is None:
        return LoadInfo(None, None, None)
    snapshot = (row.summary or {}).get("snapshot_date")
    return LoadInfo(row.id, date.fromisoformat(snapshot) if snapshot else None, row.finished_at)


def _clean_inputs_from_db(session: Session) -> PlanningInputs:
    """The BlueTide side: items, vendors, locations, lots, real demand, open POs, stockouts."""
    items = session.scalars(select(m.Item)).all()
    customers = dict(session.execute(select(m.Customer.customer_code, m.Customer.name)).all())
    sales = session.execute(
        select(
            m.SalesLine.item_code,
            m.SalesLine.order_no,
            m.SalesLine.customer_code,
            m.SalesLine.order_date,
            m.SalesLine.ship_date,
            m.SalesLine.qty,
            m.SalesLine.status,
        ).where(m.SalesLine.demand_class == "real_demand")
    ).all()
    po_lines = session.scalars(
        select(m.PurchaseOrderLine).where(
            m.PurchaseOrderLine.status == "open", m.PurchaseOrderLine.qty_remaining_sell_uom > 0
        )
    ).all()
    return PlanningInputs(
        items=tuple(
            ItemInput(
                i.item_code,
                i.description,
                i.category,
                i.sell_uom,
                float(i.lb_per_case) if i.lb_per_case is not None else None,
                i.vendor_code,
                i.lifecycle_status,
                i.lifecycle_reason,
            )
            for i in items
        ),
        vendors=tuple(
            VendorInput(v.vendor_code, v.name, v.country, v.lead_time_days_system)
            for v in session.scalars(select(m.Vendor)).all()
        ),
        vendor_settings=(),
        item_settings=(),
        locations=tuple(
            LocationInput(x.code, x.is_sellable, x.may_return_to_stock, x.is_third_party_storage)
            for x in session.scalars(select(m.Location)).all()
        ),
        lots=tuple(
            LotInput(
                x.item_code,
                x.location_code,
                x.lot_no,
                float(x.qty_sell_uom) if x.qty_sell_uom is not None else None,
                x.expiry_date,
                x.is_adjustment,
                float(x.unit_cost_sell_uom) if x.unit_cost_sell_uom is not None else None,
            )
            for x in session.scalars(select(m.InventoryLot)).all()
        ),
        sales=tuple(
            SaleInput(
                s.item_code,
                s.order_no,
                customers.get(s.customer_code, s.customer_code),
                s.order_date,
                s.ship_date,
                float(s.qty),
                s.status == "OPEN",
            )
            for s in sales
        ),
        po_lines=tuple(
            POLineInput(
                p.po_no,
                p.line_no,
                p.item_code,
                p.vendor_code,
                p.order_date,
                p.expected_date_system,
                float(p.qty_remaining_sell_uom),
            )
            for p in po_lines
        ),
        stockouts=tuple(
            StockoutInput(s.item_code, s.start_date, s.end_date)
            for s in session.scalars(select(m.StockoutPeriod)).all()
        ),
    )


def _bluetide_facts(session: Session) -> BlueTideFacts:
    """Every BlueTide PO line in the item's selling unit, and the stock count's lot keys."""
    units = {
        i.item_code: (i.sell_uom, i.lb_per_case)
        for i in session.execute(select(m.Item.item_code, m.Item.sell_uom, m.Item.lb_per_case)).all()
    }
    lines = []
    for p in session.scalars(select(m.PurchaseOrderLine)).all():
        sell_uom, lb = units.get(p.item_code, (p.uom, None))
        ordered = to_sell_uom(p.qty_ordered, p.uom, sell_uom, lb)
        received = to_sell_uom(p.qty_received, p.uom, sell_uom, lb)
        lines.append(
            BlueTidePOLine(
                po_no=p.po_no,
                line_no=p.line_no,
                item_code=p.item_code,
                vendor_code=p.vendor_code,
                order_date=p.order_date,
                expected_date_system=p.expected_date_system,
                ordered=float(ordered) if ordered is not None else None,
                received=float(received) if received is not None else 0.0,
                remaining=(
                    float(p.qty_remaining_sell_uom)
                    if p.status == "open" and p.qty_remaining_sell_uom is not None
                    else 0.0
                ),
                status=p.status,
            )
        )
    lots = frozenset(
        (x.item_code, x.location_code, x.lot_no)
        for x in session.execute(
            select(m.InventoryLot.item_code, m.InventoryLot.location_code, m.InventoryLot.lot_no)
        ).all()
    )
    rank = {"INVOICED": 2, "OPEN": 1, "CANCELLED": 0}
    orders: dict[tuple[str, str], str] = {}
    for order_no, item_code, status in session.execute(
        select(m.SalesLine.order_no, m.SalesLine.item_code, m.SalesLine.status)
    ).all():
        key = (order_no, item_code)
        if key not in orders or rank.get(status, 0) > rank.get(orders[key], 0):
            orders[key] = status
    customers = {
        c.customer_code: (c.name, c.customer_type) for c in session.scalars(select(m.Customer)).all()
    }
    excluded = frozenset(session.scalars(select(m.ExcludedOrder.order_no)).all())
    return BlueTideFacts(tuple(lines), lots, orders, customers, excluded)


def _app_items(session: Session, clean: PlanningInputs) -> tuple[tuple[ItemInput, ...], frozenset[str]]:
    """BlueTide's items plus Dana's; hers win on the same code (ADR-026)."""
    by_code = {i.item_code: i for i in clean.items}
    mine = session.scalars(select(m.AppItem)).all()
    for a in mine:
        bluetide = by_code.get(a.item_code)
        if a.status == "discontinued":
            lifecycle, reason = "discontinued", f"Marked discontinued by {a.updated_by}"
        elif bluetide is not None:
            lifecycle, reason = bluetide.lifecycle_status, bluetide.lifecycle_reason
        else:
            lifecycle, reason = "active", f"Added in the app by {a.created_by}"
        by_code[a.item_code] = ItemInput(
            a.item_code,
            a.description,
            a.category,
            a.sell_uom,
            float(a.lb_per_case) if a.lb_per_case is not None else None,
            a.vendor_code,
            lifecycle,
            reason,
        )
    return tuple(by_code.values()), frozenset(a.item_code for a in mine)


def _app_vendors(session: Session, clean: PlanningInputs) -> tuple[tuple[VendorInput, ...], frozenset[str]]:
    by_code = {v.vendor_code: v for v in clean.vendors}
    mine = session.scalars(select(m.AppVendor)).all()
    for a in mine:
        bluetide = by_code.get(a.vendor_code)
        by_code[a.vendor_code] = VendorInput(
            a.vendor_code, a.name, a.country, bluetide.lead_time_days_system if bluetide else None
        )
    return tuple(by_code.values()), frozenset(a.vendor_code for a in mine)


def _reconcile(session: Session, facts: BlueTideFacts, load: LoadInfo) -> Reconciled:
    """Dana's POs, line statuses and receipts, matched with BlueTide's (planning/records.py)."""
    app_lines = [
        AppPOLine(
            po.po_no,
            line.line_no,
            line.item_code,
            po.vendor_code,
            po.order_date,
            float(line.qty_ordered),
            float(line.unit_cost) if line.unit_cost is not None else None,
        )
        for po, line in session.execute(
            select(m.PurchaseOrder, m.PurchaseOrderLineApp).join(
                m.PurchaseOrderLineApp, m.PurchaseOrderLineApp.po_id == m.PurchaseOrder.id
            )
        ).all()
    ]
    statuses = [
        LineStatusInput(s.po_no, s.line_no, s.status, s.shipped_on, s.container_no, s.cancel_reason)  # type: ignore[arg-type]
        for s in session.scalars(select(m.PoLineStatus)).all()
    ]
    movements = session.scalars(select(m.StockMovement).where(m.StockMovement.kind == "receipt")).all()
    reversed_ids = {mv.reverses_id for mv in movements if mv.reverses_id is not None}
    receipts = [
        ReceiptInput(
            mv.id,
            mv.po_no or "",
            mv.po_line_no or 0,
            mv.item_code,
            mv.location_code,
            mv.lot_no,
            float(mv.qty),
            mv.expiry_date,
            float(mv.unit_cost) if mv.unit_cost is not None else None,
            mv.movement_date,
        )
        for mv in movements
        if mv.reverses_id is None and mv.id not in reversed_ids and mv.po_no is not None
    ]
    return reconcile_pos(
        facts.po_lines, app_lines, statuses, receipts, facts.snapshot_lots, load.snapshot_date
    )


def all_customers(session: Session, facts: BlueTideFacts | None = None) -> dict[str, tuple[str, str]]:
    """BlueTide's customers plus Dana's (hers win on the same code): code -> (name, type)."""
    out = (
        dict(facts.customers)
        if facts is not None
        else {c.customer_code: (c.name, c.customer_type) for c in session.scalars(select(m.Customer)).all()}
    )
    for c in session.scalars(select(m.AppCustomer)).all():
        out[c.customer_code] = (c.name, c.customer_type)
    return out


def _app_shipment_lines(
    session: Session, facts: BlueTideFacts, items: tuple[ItemInput, ...], rules: BusinessRules
) -> list[AppShipmentLine]:
    """Dana's orders, each line classified like BlueTide's sales (transfers, credits, samples, one-offs)."""
    customers = all_customers(session, facts)
    lifecycle = {i.item_code: i.lifecycle_status for i in items}
    out = []
    for shipment, line in session.execute(
        select(m.Shipment, m.ShipmentLine).join(m.ShipmentLine, m.ShipmentLine.shipment_id == m.Shipment.id)
    ).all():
        name, ctype = customers.get(shipment.customer_code, (shipment.customer_code, None))
        # A sample is a $0 line (T17); a missing price on a customer order isn't a sample.
        price = Decimal(0) if shipment.kind == "sample" else (line.unit_price or Decimal(1))
        demand_class = classify_sale(
            SaleFacts(
                status="OPEN" if shipment.status == "open" else "INVOICED",
                customer_type=ctype,
                order_no=shipment.order_no,
                qty=line.qty,
                unit_price=price,
                item_lifecycle=lifecycle.get(line.item_code, "active"),
            ),
            set(facts.excluded_orders),
            rules,
        )
        out.append(
            AppShipmentLine(
                shipment_id=shipment.id,
                order_no=shipment.order_no,
                line_no=line.line_no,
                item_code=line.item_code,
                customer_name=name,
                kind=shipment.kind,  # type: ignore[arg-type]
                order_date=shipment.order_date,
                ship_date=shipment.shipped_on or shipment.ship_date,
                status=shipment.status,  # type: ignore[arg-type]
                qty=float(line.qty),
                is_real_demand=demand_class == "real_demand",
            )
        )
    return out


def _movements(session: Session) -> list[MovementInput]:
    """Dana's picks, moves and adjustments, leaving out anything undone (and the undo rows)."""
    rows = session.scalars(select(m.StockMovement).where(m.StockMovement.kind != "receipt")).all()
    reversed_ids = {r.reverses_id for r in rows if r.reverses_id is not None}
    return [
        MovementInput(
            r.id,
            r.kind,
            r.item_code,
            r.location_code,
            r.lot_no,
            float(r.qty),
            r.expiry_date,
            float(r.unit_cost) if r.unit_cost is not None else None,
            r.movement_date,
            r.shipment_id,
        )
        for r in rows
        if r.reverses_id is None and r.id not in reversed_ids
    ]


def build_context(session: Session, rules: BusinessRules) -> PlanningContext:
    """Engine inputs: cached BlueTide data for the latest load + Dana's current edits and records."""
    load = latest_load(session)
    key = load.load_run_id or 0
    cached = _clean_cache.get(key)
    if cached is None:
        cached = (_clean_inputs_from_db(session), _bluetide_facts(session))
        _clean_cache.clear()
        _clean_cache[key] = cached
    clean, facts = cached
    handled = session.scalars(select(m.HandledFlag).where(m.HandledFlag.cleared_at.is_(None))).all()
    items, app_items = _app_items(session, clean)
    vendors, app_vendors = _app_vendors(session, clean)
    reconciled = _reconcile(session, facts, load)
    shipments = reconcile_shipments(_app_shipment_lines(session, facts, items, rules), facts.orders)
    base_lots = [LotRecord(lot, "bluetide") for lot in clean.lots] + [
        LotRecord(r.lot, "received", f"Received in the app ({r.po_no} line {r.po_line_no})")
        for r in reconciled.received_lots
    ]
    sellable = frozenset(x.code for x in clean.locations if x.is_sellable)
    lot_records, movement_flags = apply_movements(
        base_lots, _movements(session), shipments.applied_shipments, load.snapshot_date, sellable
    )
    sales = (
        tuple(
            x
            for x in clean.sales
            if not (x.is_open and (x.order_no, x.item_code) in shipments.drop_bluetide_open)
        )
        + shipments.sales
    )
    inputs = replace(
        clean,
        items=items,
        vendors=vendors,
        lots=tuple(r.lot for r in lot_records),
        sales=sales,
        po_lines=reconciled.po_inputs,
        vendor_settings=tuple(
            VendorSettingInput(s.vendor_code, s.lead_time_days, s.safety_days, s.order_cycle_days)
            for s in session.scalars(select(m.VendorSetting)).all()
        ),
        item_settings=tuple(
            ItemSettingInput(s.item_code, s.lifecycle_override, s.safety_days_override)
            for s in session.scalars(select(m.ItemSetting)).all()
        ),
        eta_overrides=tuple(
            EtaOverrideInput(o.po_no, o.line_no, o.eta, o.updated_by)
            for o in session.scalars(select(m.PoEtaOverride)).all()
        ),
        handled_notes=tuple(
            # Notes are dated in BUSINESS time: "today" is AS_OF, never the clock (invariant #1).
            HandledNoteInput(
                h.id,
                h.item_code,
                float(h.qty) if h.qty is not None else None,
                h.eta,
                h.note,
                rules.as_of_date,
            )
            for h in handled
        ),
    )
    return PlanningContext(
        inputs, load, reconciled, app_items, app_vendors, lot_records, shipments, movement_flags
    )


def inputs_from_db(session: Session, rules: BusinessRules) -> tuple[PlanningInputs, LoadInfo]:
    """Engine inputs and the load they're based on (see build_context for the details)."""
    context = build_context(session, rules)
    return context.inputs, context.load


def clear_cache() -> None:
    """Forget cached BlueTide inputs (tests; a reload changes the load run id anyway)."""
    _clean_cache.clear()


def count_rows(session: Session, model: type) -> int:
    return int(session.execute(select(func.count()).select_from(model)).scalar_one())
