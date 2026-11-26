"""Build the planning engine's inputs from loaded data.

Phase 3: from the loader's clean dataset (no database), used by the golden tests and
scripts/compare_answer_key.py. Phase 4 adds the same mapping from database rows (and Dana's
app-layer edits: vendor settings, ETA overrides, handled notes, item settings) for the API.

Only REAL demand reaches the engine (§6.2: no transfers, samples, credits, cancellations, the
cruise one-off or fresh), and only open PO lines with something still to come (T25).
"""

from __future__ import annotations

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
