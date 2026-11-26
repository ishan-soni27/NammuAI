"""Tiny planning-engine inputs for tests. AS_OF is Monday 2026-11-16, like the real data."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from app.config.business_rules import BusinessRules
from app.planning.engine import plan
from app.planning.types import (
    EtaOverrideInput,
    HandledNoteInput,
    ItemInput,
    ItemPlan,
    ItemSettingInput,
    LocationInput,
    LotInput,
    PlanningInputs,
    PlanResult,
    POLineInput,
    SaleInput,
    StockoutInput,
    VendorInput,
    VendorSettingInput,
)

AS_OF = date(2026, 11, 16)
RULES = BusinessRules()
LOCATIONS = (
    LocationInput("NB", True, False, False),
    LocationInput("HCS", True, False, True),
    LocationInput("QA-HOLD", False, True, False),
    LocationInput("DAMAGED", False, False, False),
)


def item(code: str = "X", **kw) -> ItemInput:
    base = ItemInput(code, f"Item {code}", "Shrimp", "CS", 20.0, "V1", "active", "Selling.")
    return replace(base, **kw)


def lot(
    code: str = "X",
    qty: float = 100,
    location: str = "NB",
    expiry: date | None = date(2028, 1, 1),
    lot_no: str = "L1",
    cost: float | None = 10.0,
    adj: bool = False,
) -> LotInput:
    return LotInput(code, location, lot_no, qty, expiry, adj, cost)


def steady_sales(code: str = "X", per_day: float = 1.0, days: int = 365) -> list[SaleInput]:
    """One real-demand order per day for the last `days` days (INVOICED)."""
    return [
        SaleInput(
            code,
            f"SO-{n}",
            "Dory Grill",
            AS_OF - timedelta(days=n),
            AS_OF - timedelta(days=n),
            per_day,
            False,
        )
        for n in range(1, days + 1)
    ]


def open_order(
    code: str = "X",
    qty: float = 10,
    ship: date = AS_OF + timedelta(days=5),
    ordered: date = AS_OF - timedelta(days=2),
    customer: str = "Seabright Markets",
) -> SaleInput:
    return SaleInput(code, f"SO-OPEN-{qty}-{ship}", customer, ordered, ship, qty, True)


def po(
    code: str = "X",
    qty: float = 100,
    ordered: date = AS_OF - timedelta(days=10),
    bluetide: date | None = AS_OF + timedelta(days=20),
    po_no: str = "PO-1",
    vendor: str = "V1",
) -> POLineInput:
    return POLineInput(po_no, 1, code, vendor, ordered, bluetide, qty)


def inputs(
    items: list[ItemInput] | None = None,
    lots: list[LotInput] | None = None,
    sales: list[SaleInput] | None = None,
    pos: list[POLineInput] | None = None,
    lead: int = 14,
    safety: int = 7,
    cycle: int = 7,
    overrides: list[EtaOverrideInput] | None = None,
    notes: list[HandledNoteInput] | None = None,
    stockouts: list[StockoutInput] | None = None,
    item_settings: list[ItemSettingInput] | None = None,
) -> PlanningInputs:
    return PlanningInputs(
        items=tuple(items or [item()]),
        vendors=(VendorInput("V1", "Maritime Northern Pack", "Canada", lead),),
        vendor_settings=(VendorSettingInput("V1", lead, safety, cycle),),
        item_settings=tuple(item_settings or []),
        locations=LOCATIONS,
        lots=tuple(lots if lots is not None else [lot()]),
        sales=tuple(sales if sales is not None else steady_sales()),
        po_lines=tuple(pos or []),
        eta_overrides=tuple(overrides or []),
        handled_notes=tuple(notes or []),
        stockouts=tuple(stockouts or []),
    )


def run(rules: BusinessRules = RULES, **kw) -> PlanResult:
    return plan(inputs(**kw), rules)


def one(result: PlanResult, code: str = "X") -> ItemPlan:
    return next(p for p in result.items if p.item.item_code == code)
