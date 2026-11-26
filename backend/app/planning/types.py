"""Inputs and outputs of the planning engine (pure dataclasses, no database types).

How it fits
    services/planning_inputs.py turns loaded data (from the database or from the loader's
    clean dataset) into these INPUT classes. planning/engine.py turns them into an ItemPlan
    per item plus a stuck list. Phase 4 maps the OUTPUT classes to API responses.

Units: every quantity is in the item's selling unit (cases or pounds, ADR-012), as float.
Rates and forecasts are fractional by nature, so floats are used inside the engine; display
code rounds. "Order at least" is rounded UP, with a tiny tolerance so 260.0000001 doesn't
become 261.

How to change this ("show a new number on the dashboard", BUILD_PROMPT §17): add a field to
ItemPlan, fill it in engine.py, then add it to api/v1/schemas.py and the frontend type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

# ---- Inputs ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ItemInput:
    item_code: str
    description: str
    category: str
    sell_uom: str  # "CS" or "LB"
    lb_per_case: float | None  # used only to put a category's items in one unit for seasonality
    vendor_code: str
    lifecycle_status: str  # active / dormant / discontinued / legacy / fresh_out_of_scope
    lifecycle_reason: str


@dataclass(frozen=True)
class VendorInput:
    vendor_code: str
    name: str
    country: str | None
    lead_time_days_system: int | None  # BlueTide's number (T27)


@dataclass(frozen=True)
class VendorSettingInput:
    """Dana's numbers for a vendor (app layer, editable on the Lead times page)."""

    vendor_code: str
    lead_time_days: int
    safety_days: int
    order_cycle_days: int


@dataclass(frozen=True)
class ItemSettingInput:
    """Per-item overrides Dana can set (app layer)."""

    item_code: str
    lifecycle_override: str | None = None  # e.g. "active" to revive an item
    safety_days_override: int | None = None


@dataclass(frozen=True)
class LotInput:
    """One on-hand lot of the latest snapshot, already in the item's selling unit (T10)."""

    item_code: str
    location_code: str
    lot_no: str
    qty: float | None  # None = no conversion factor; never counted (logged by the loader)
    expiry_date: date | None
    is_adjustment: bool = False
    unit_cost: float | None = None  # per selling unit, for "$ at cost" (A17)


@dataclass(frozen=True)
class LocationInput:
    code: str
    is_sellable: bool
    may_return_to_stock: bool  # QA-HOLD
    is_third_party_storage: bool = False  # Harbor


@dataclass(frozen=True)
class SaleInput:
    """A sales line that is real demand (§6.2). Other classes never reach the engine."""

    item_code: str
    order_no: str
    customer_name: str
    order_date: date
    ship_date: date | None
    qty: float
    is_open: bool  # OPEN = promised to a customer, not shipped yet (T22)


@dataclass(frozen=True)
class POLineInput:
    """An open purchase order line with something still to come (T25)."""

    po_no: str
    line_no: int
    item_code: str
    vendor_code: str
    order_date: date
    expected_date_system: date | None  # BlueTide's date, often stale (T26)
    qty_remaining: float


@dataclass(frozen=True)
class EtaOverrideInput:
    """A real arrival date Dana typed in for a PO line (promised in email Q3)."""

    po_no: str
    line_no: int
    eta: date


@dataclass(frozen=True)
class HandledNoteInput:
    """ "I've handled this one" (Dana 00:09:45). With qty AND eta it counts as incoming (§6.10)."""

    note_id: int
    item_code: str
    qty: float | None
    eta: date | None
    note: str | None
    created_on: date  # the business date it was written (for "Handled by Dana, Nov 16")


@dataclass(frozen=True)
class StockoutInput:
    """A known stockout window (inclusive). Those days are left out of selling rates (T23)."""

    item_code: str
    start_date: date
    end_date: date


@dataclass(frozen=True)
class PlanningInputs:
    items: tuple[ItemInput, ...]
    vendors: tuple[VendorInput, ...]
    vendor_settings: tuple[VendorSettingInput, ...]
    item_settings: tuple[ItemSettingInput, ...]
    locations: tuple[LocationInput, ...]
    lots: tuple[LotInput, ...]
    sales: tuple[SaleInput, ...]
    po_lines: tuple[POLineInput, ...]
    eta_overrides: tuple[EtaOverrideInput, ...] = ()
    handled_notes: tuple[HandledNoteInput, ...] = ()
    stockouts: tuple[StockoutInput, ...] = ()


# ---- Outputs ---------------------------------------------------------------------------

Status = Literal["TOO_LATE", "ORDER_THIS_WEEK", "ORDER_SOON", "OK", "NO_RECENT_SALES", "NOT_PLANNED"]
StuckTag = Literal["EXPIRED", "STOPPED_SELLING", "INSIDE_SIX_MONTHS", "LONG_AT_HARBOR", "OVERSTOCK"]


@dataclass
class OnHand:
    """Per-item on-hand breakdown (§6.1). Only `sellable` feeds the run-out."""

    sellable: float = 0.0
    on_hold: float = 0.0  # QA-HOLD: may come back, never counted (Dana Q4)
    damaged: float = 0.0
    expired: float = 0.0
    sellable_by_location: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class IncomingLine:
    """Something on the way, with the arrival date we believe and why (§6.6)."""

    source: Literal["po", "handled_note"]
    reference: str  # "PO-260443 line 1" or "Your note #3"
    qty: float
    eta: date | None  # None = late with no known date: NOT counted (Dana Q3)
    eta_source: str  # "Set by Dana", "Real lead time", "BlueTide date", "Late: date unknown", "Your note"
    bluetide_date: date | None
    is_late: bool
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class CommittedLine:
    order_no: str
    customer_name: str
    ship_date: date | None
    qty: float


@dataclass(frozen=True)
class DemandProfile:
    base_rate_per_day: float  # last 8 weeks, stockout days left out
    base_days: int  # days the rate was measured over
    base_index: float  # how seasonal those 8 weeks were (1.0 = a normal month)
    level_per_day: float  # "normal-season" rate = base_rate / base_index
    index_by_month: dict[int, float]  # the category's seasonal multiplier for each month 1..12
    monthly_history: dict[str, float]  # "2025-12" -> real demand that month (last 12 months)


@dataclass(frozen=True)
class ProjectionPoint:
    day: date
    stock: float  # end-of-day stock (can go negative: that's the shortfall)


@dataclass(frozen=True)
class Scenario:
    """One run-out projection. `confirmed` counts only supply with a date; `if_late_arrive`
    also counts late POs as if they showed up today (the best case), to answer Dana's
    "If an item is only covered by a late PO, I want to see that" (Q3)."""

    run_out_date: date | None  # None = lasts beyond the projection horizon
    status: Status
    order_by_date: date | None
    order_at_least: float
    gap_qty: float  # TOO_LATE only: demand you'd miss before stock comes back
    back_in_stock_date: date | None  # TOO_LATE only: when stock comes back (an earlier PO, or the new order)
    points: tuple[ProjectionPoint, ...]


@dataclass(frozen=True)
class ItemPlan:
    item: ItemInput
    lifecycle_status: str  # after any override
    vendor_name: str
    vendor_country: str | None
    lead_time_days: int
    lead_time_source: str  # "Dana", "BlueTide", "default"
    lead_time_days_system: int | None
    safety_days: int
    order_cycle_days: int
    on_hand: OnHand
    committed_total: float
    committed_lines: tuple[CommittedLine, ...]
    incoming: tuple[IncomingLine, ...]  # with a date: counted
    late_incoming: tuple[IncomingLine, ...]  # late, no date: shown, not counted (P0 #2a)
    demand: DemandProfile
    weeks_of_cover: float | None  # None = no demand expected
    new_order_arrival: date
    confirmed: Scenario
    if_late_arrive: Scenario | None  # None when the item has no late POs
    covered_only_by_late_po: bool
    active_handled_note: HandledNoteInput | None
    explanation: tuple[str, ...]


@dataclass(frozen=True)
class StuckLot:
    item_code: str
    description: str
    lot_no: str
    location_code: str
    qty: float
    sell_uom: str
    expiry_date: date | None
    value_at_cost: float | None
    tags: tuple[StuckTag, ...]
    primary_tag: StuckTag
    at_harbor: bool  # paying storage per pallet per month (Walt: the worst case)


@dataclass(frozen=True)
class StuckItem:
    item_code: str
    description: str
    sell_uom: str
    primary_tag: StuckTag
    qty: float
    qty_at_harbor: float
    value_at_cost: float
    lots: tuple[StuckLot, ...]


@dataclass(frozen=True)
class TrustStrip:
    """What BlueTide shows as on hand that we did NOT count (BUILD_PROMPT §9.2)."""

    on_hold: dict[str, float]  # by unit, e.g. {"CS": 420.0}
    damaged: dict[str, float]
    expired: dict[str, float]  # expired lots of planned (non-legacy, non-fresh) items
    legacy: dict[str, float]  # old ZZ stock
    late_po_qty: dict[str, float]  # late POs not counted (Dana Q3)


@dataclass(frozen=True)
class PlanResult:
    as_of: date
    items: tuple[ItemPlan, ...]
    stuck: tuple[StuckItem, ...]
    trust: TrustStrip
    seasonal_index: dict[str, dict[int, float]]
