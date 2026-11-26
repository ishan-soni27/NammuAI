"""Build the planning engine's inputs from loaded data.

Two sources, one shape (PlanningInputs):
  - inputs_from_dataset: the loader's clean dataset, no database (golden tests, scripts).
  - build_context:       the database, for the API. BlueTide's data (the clean layer) only changes
                         when a load runs, so it is cached per load run; Dana's knowledge (vendor
                         settings, item settings, PO dates, handled notes) is read fresh on every
                         request, so a change shows up immediately (ADR-004).

BlueTide owns every fact (ADR-032): stock, sales, POs and receipts come only from its uploaded
files. The app adds only what BlueTide doesn't know, and never records a transaction.

Only REAL demand reaches the engine (§6.2: no transfers, samples, credits, cancellations, the
cruise one-off or fresh), and only open PO lines with something still to come (T25).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.business_rules import BusinessRules
from app.db import models as m
from app.loader.types import CleanDataset, VendorSettingSeed
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
class PlanningContext:
    """Everything one request needs: the engine inputs and the load they're based on."""

    inputs: PlanningInputs
    load: LoadInfo


# latest load run id -> clean-layer inputs; size 1
_clean_cache: dict[int, PlanningInputs] = {}


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


def build_context(session: Session, rules: BusinessRules) -> PlanningContext:
    """Engine inputs: the cached BlueTide data for the latest load, plus Dana's current knowledge."""
    load = latest_load(session)
    key = load.load_run_id or 0
    clean = _clean_cache.get(key)
    if clean is None:
        clean = _clean_inputs_from_db(session)
        _clean_cache.clear()
        _clean_cache[key] = clean
    handled = session.scalars(select(m.HandledFlag).where(m.HandledFlag.cleared_at.is_(None))).all()
    inputs = replace(
        clean,
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
    return PlanningContext(inputs, load)


def inputs_from_db(session: Session, rules: BusinessRules) -> tuple[PlanningInputs, LoadInfo]:
    """Engine inputs and the load they're based on (see build_context for the details)."""
    context = build_context(session, rules)
    return context.inputs, context.load


def clear_cache() -> None:
    """Forget cached BlueTide inputs (tests; a reload changes the load run id anyway)."""
    _clean_cache.clear()
