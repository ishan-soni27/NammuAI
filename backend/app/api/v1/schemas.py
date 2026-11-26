"""Response and request models for /api/v1 (Pydantic v2).

Purpose
    The API's public shapes in one file, so the frontend's TypeScript types
    (`frontend/src/api/types.ts`) have one place to mirror. These models also generate the
    OpenAPI docs at /api/v1/docs.

Naming
    Fields that reach the UI use Dana's words where it matters (`order_at_least`,
    `on_hold`, `promised_to_customers`, `stuck_tags`, BUILD_PROMPT §12). Quantities are in the
    item's selling unit (`sell_uom`: CS or LB) unless the name says otherwise.

How to change this ("show a new number on the dashboard", §17)
    Engine output (`planning/types.py`) → add the field here → fill it in
    `services/presenters.py` → add it to `frontend/src/api/types.ts` → render it.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Status = Literal["TOO_LATE", "ORDER_THIS_WEEK", "ORDER_SOON", "OK", "NO_RECENT_SALES", "NOT_PLANNED"]


class HealthResponse(BaseModel):
    """GET /api/v1/health."""

    status: Literal["ok", "degraded"] = Field(
        description="'ok' when the database is reachable and migrated, otherwise 'degraded'."
    )
    db: Literal["ok", "down", "not_configured"]
    schema_ready: bool = Field(description="False until database migrations have been run.")
    as_of: date = Field(description="The business 'today' (AS_OF_DATE), never the server clock.")
    last_load_at: datetime | None = Field(
        description="When BlueTide data was last loaded successfully (UTC). Null before the first load."
    )
    version: str = Field(description="Short git commit of the running API, or 'local'.")


# ---- Shared pieces ---------------------------------------------------------------------------


class HandledNoteOut(BaseModel):
    id: int
    item_code: str
    qty: float | None
    eta: date | None
    note: str | None
    created_at: datetime
    created_by: str
    counts_as_incoming: bool = Field(description="True when it has both a quantity and a date (§6.10).")
    bluetide_now_shows: list[str] = Field(
        default_factory=list,
        description="Open POs BlueTide now shows for this item since the note: 'Clear your note?' (§6.10).",
    )


class RunwayOut(BaseModel):
    """The runway bar (§9.1): how long stock lasts vs when a new order would land."""

    stock_lasts_days: int | None = Field(description="Days until run-out; null = beyond the horizon.")
    lead_time_days: int
    cushion_days: int
    horizon_days: int


class ItemCard(BaseModel):
    """One row of the Monday screen (and of GET /items)."""

    item_code: str
    description: str
    category: str
    sell_uom: str
    vendor_code: str
    vendor_name: str
    country: str | None
    lifecycle_status: str
    status: Status
    run_out_date: date | None
    order_by_date: date | None
    new_order_arrival: date
    back_in_stock_date: date | None
    lead_time_days: int
    cushion_days: int
    order_at_least: float
    short_qty: float = Field(description="TOO_LATE only: demand you'd miss before stock comes back.")
    sellable: float
    on_hold: float
    promised_to_customers: float
    on_the_way: float = Field(description="Incoming with a date (counted).")
    late_qty: float = Field(description="Late POs with no date (shown, not counted).")
    weeks_of_cover: float | None
    covered_only_by_late_po: bool
    if_late_arrive_status: Status | None
    if_late_arrive_order_at_least: float | None
    handled_note: HandledNoteOut | None
    runway: RunwayOut


class LateLineOut(BaseModel):
    item_code: str
    description: str
    sell_uom: str
    po_no: str | None
    line_no: int | None
    reference: str
    qty: float
    bluetide_date: date | None
    flags: list[str]


class OnHoldOut(BaseModel):
    item_code: str
    description: str
    sell_uom: str
    qty: float


class LateInventoryOut(BaseModel):
    """P0 #2a: stock that might still come but isn't counted (late POs) or can't be sold yet (QA hold)."""

    late_pos: list[LateLineOut]
    on_hold: list[OnHoldOut]


class StuckLotOut(BaseModel):
    lot_no: str
    location_code: str
    location_name: str
    qty: float
    expiry_date: date | None
    value_at_cost: float | None
    tags: list[str]
    primary_tag: str
    at_harbor: bool


class StuckItemOut(BaseModel):
    item_code: str
    description: str
    sell_uom: str
    primary_tag: str
    qty: float
    qty_at_harbor: float
    value_at_cost: float
    lots: list[StuckLotOut]


class TrustStripOut(BaseModel):
    """What BlueTide counts as on hand that we did NOT count, by unit (§9.2)."""

    on_hold: dict[str, float]
    damaged: dict[str, float]
    expired: dict[str, float]
    old_zz_stock: dict[str, float]
    late_po_qty: dict[str, float]


class SummaryOut(BaseModel):
    too_late: int
    order_this_week: int
    order_soon: int
    handled: int
    fine: int
    covered_only_by_late_po: int
    inside_six_months_value: float
    inside_six_months_value_at_harbor: float
    stuck_value: float
    sentences: list[str] = Field(description="The one-screen summary in plain English (§9.2).")


class DashboardOut(BaseModel):
    """GET /api/v1/dashboard: everything the Monday screen shows."""

    as_of: date
    data_snapshot_date: date | None
    last_load_at: datetime | None
    summary: SummaryOut
    order_items: list[ItemCard] = Field(
        description="TOO_LATE, ORDER_THIS_WEEK, ORDER_SOON, most urgent first."
    )
    handled_items: list[ItemCard] = Field(description="Items Dana marked as handled (never hidden, §6.10).")
    fine_items: list[ItemCard]
    late_inventory: LateInventoryOut
    stuck_items: list[StuckItemOut]
    trust_strip: TrustStripOut


# ---- Item drill-down --------------------------------------------------------------------------


class VendorTermsOut(BaseModel):
    vendor_code: str
    vendor_name: str
    country: str | None
    lead_time_days: int
    lead_time_source: str
    lead_time_days_bluetide: int | None
    cushion_days: int
    order_cycle_days: int


class LotOut(BaseModel):
    lot_no: str
    location_code: str
    location_name: str
    qty: float | None
    qty_source: float
    uom_source: str
    pack_date: date | None
    expiry_date: date | None
    received_date: date | None
    unit_cost: float | None
    value_at_cost: float | None
    counted: bool
    reason: str = Field(description="Plain English: why it is or isn't counted as sellable.")
    stuck_tags: list[str]


class CommittedOut(BaseModel):
    order_no: str
    customer_name: str
    ship_date: date | None
    qty: float


class IncomingOut(BaseModel):
    source: str
    reference: str
    po_no: str | None
    line_no: int | None
    qty: float
    eta: date | None
    eta_source: str
    bluetide_date: date | None
    is_late: bool
    flags: list[str]


class DemandOut(BaseModel):
    selling_per_week: float
    measured_over_days: int
    season_now: float = Field(description="How seasonal the measured weeks were (1.0 = an average month).")
    normal_per_week: float
    season_by_month: dict[int, float]
    monthly_history: dict[str, float]


class PointOut(BaseModel):
    day: date
    stock: float


class ItemSettingsOut(BaseModel):
    item_code: str
    lifecycle_override: str | None
    safety_days_override: int | None
    note: str | None
    updated_at: datetime | None
    updated_by: str | None


class SeasonMarkerOut(BaseModel):
    label: str
    start: date
    end: date


class ItemDetailOut(BaseModel):
    """GET /api/v1/items/{item_code}: the full 'why' (§9.3)."""

    as_of: date
    card: ItemCard
    lifecycle_reason: str
    vendor: VendorTermsOut
    sellable_by_location: dict[str, float]
    damaged: float
    expired: float
    lots: list[LotOut]
    promised: list[CommittedOut]
    incoming: list[IncomingOut]
    late: list[IncomingOut]
    demand: DemandOut
    projection: list[PointOut]
    if_late_arrive_projection: list[PointOut] | None
    explanation: list[str]
    settings: ItemSettingsOut | None
    aliases: list[str]
    handled_notes: list[HandledNoteOut]
    season_markers: list[SeasonMarkerOut] = Field(
        description="Busy seasons to shade on the chart (business_rules)."
    )


# ---- Dana's edits --------------------------------------------------------------------------------


class VendorOut(BaseModel):
    vendor_code: str
    name: str
    country: str | None
    lead_time_days_bluetide: int | None
    lead_time_bluetide_text: str | None
    lead_time_days: int
    cushion_days: int
    order_cycle_days: int
    source: str
    note: str | None
    updated_at: datetime | None
    updated_by: str | None


class VendorPatchIn(BaseModel):
    """Only the fields sent are changed. Days must be within the limits in business_rules.py."""

    lead_time_days: int | None = None
    cushion_days: int | None = None
    order_cycle_days: int | None = None
    note: str | None = Field(default=None, max_length=500)


class PoEtaPatchIn(BaseModel):
    eta: date | None = Field(description="The real arrival date; null clears it (back to the computed date).")
    note: str | None = Field(default=None, max_length=500)


class PoEtaOut(BaseModel):
    po_no: str
    line_no: int
    item_code: str
    eta: date | None
    note: str | None
    updated_at: datetime | None
    updated_by: str | None


class HandledIn(BaseModel):
    qty: float | None = Field(default=None, gt=0)
    eta: date | None = None
    note: str | None = Field(default=None, max_length=500)


class HandledClearIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ItemSettingsPatchIn(BaseModel):
    """Only the fields sent are changed; send null to clear one."""

    lifecycle_override: Literal["active", "dormant", "discontinued"] | None = None
    safety_days_override: int | None = None
    note: str | None = Field(default=None, max_length=500)


# ---- Data notes, activity, settings ----------------------------------------------------------------


class IssueRuleOut(BaseModel):
    rule_code: str
    severity: str
    action: str
    count: int
    example: str


class IssueTrapOut(BaseModel):
    trap_id: str | None
    title: str
    count: int
    rules: list[IssueRuleOut]


class DataIssueSummaryOut(BaseModel):
    load_run_id: int | None
    total: int
    by_trap: list[IssueTrapOut]


class DataIssueOut(BaseModel):
    id: int
    source_file: str
    source_line_number: int | None
    trap_id: str | None
    rule_code: str
    severity: str
    action: str
    item_code: str | None
    field: str | None
    original_value: str | None
    new_value: str | None
    message: str
    raw: dict[str, Any] | None = Field(description="The original CSV row, exactly as exported.")


class Page(BaseModel):
    total: int
    limit: int
    offset: int


class DataIssuePage(Page):
    items: list[DataIssueOut]


class AuditOut(BaseModel):
    id: int
    occurred_at: datetime
    actor: str
    action: str
    entity_type: str
    entity_id: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    request_id: str | None


class EventOut(BaseModel):
    id: int
    occurred_at: datetime
    level: str
    source: str
    event: str
    request_id: str | None
    details: dict[str, Any] | None


class LoadRunOut(BaseModel):
    id: int
    started_at: datetime
    finished_at: datetime | None
    status: str
    as_of_date: date
    git_sha: str | None
    files: list[dict[str, Any]]
    summary: dict[str, Any]


class RuleOut(BaseModel):
    name: str
    value: Any
    unit: str
    doc: str
    source: str


class ClientEventIn(BaseModel):
    level: Literal["INFO", "WARNING", "ERROR"] = "ERROR"
    event: str = Field(max_length=200)
    details: dict[str, Any] = Field(default_factory=dict)


# ---- Dana's own records (Phase 6, ADR-026/027) ------------------------------------------------


class VendorCreateIn(BaseModel):
    """A new supplier. The code is made from the name if left blank."""

    vendor_code: str | None = Field(default=None, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    country: str | None = Field(default=None, max_length=60)
    lead_time_days: int
    cushion_days: int
    order_cycle_days: int | None = None
    note: str | None = Field(default=None, max_length=500)


class ItemCreateIn(BaseModel):
    item_code: str = Field(min_length=1, max_length=30)
    description: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=60)
    sell_uom: Literal["CS", "LB"]
    lb_per_case: float | None = Field(default=None, gt=0)
    vendor_code: str = Field(min_length=1, max_length=20)
    status: Literal["active", "discontinued"] = "active"
    note: str | None = Field(default=None, max_length=500)


class ItemDetailsPatchIn(BaseModel):
    """Only the fields sent change. Editing a BlueTide item stores Dana's version, which wins."""

    description: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, min_length=1, max_length=60)
    sell_uom: Literal["CS", "LB"] | None = None
    lb_per_case: float | None = Field(default=None, gt=0)
    vendor_code: str | None = Field(default=None, min_length=1, max_length=20)
    status: Literal["active", "discontinued"] | None = None
    note: str | None = Field(default=None, max_length=500)


class AppItemOut(BaseModel):
    item_code: str
    description: str
    category: str
    sell_uom: str
    lb_per_case: float | None
    vendor_code: str
    status: str
    source: Literal["app", "bluetide", "both"]
    note: str | None
    updated_at: datetime | None
    updated_by: str | None


class POLineIn(BaseModel):
    item_code: str = Field(min_length=1, max_length=30)
    qty: float = Field(gt=0, description="In the item's selling unit (cases or lb).")
    unit_cost: float | None = Field(
        default=None, ge=0, description="Per selling unit; blank uses the last cost."
    )


class POCreateIn(BaseModel):
    vendor_code: str = Field(min_length=1, max_length=20)
    po_no: str | None = Field(default=None, max_length=30, description="Blank: the next KB-number.")
    order_date: date | None = Field(default=None, description="Blank: today (the business date).")
    expected_date: date | None = Field(
        default=None, description="Blank: order date + the supplier's lead time."
    )
    note: str | None = Field(default=None, max_length=500)
    lines: list[POLineIn] = Field(min_length=1, max_length=50)
    clear_handled_notes: bool = Field(
        default=True,
        description="Clear active 'handled' notes for these items, so they aren't counted twice.",
    )


class POShipIn(BaseModel):
    shipped_on: date | None = None
    container_no: str | None = Field(default=None, max_length=40)
    eta: date | None = Field(
        default=None, description="A new expected arrival date, if the supplier gave one."
    )
    note: str | None = Field(default=None, max_length=500)


class POCancelIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class POReceiveIn(BaseModel):
    qty: float = Field(gt=0, description="In the item's selling unit.")
    location_code: str = Field(min_length=1, max_length=20)
    lot_no: str = Field(min_length=1, max_length=40)
    expiry_date: date
    unit_cost: float | None = Field(default=None, ge=0)
    received_on: date | None = Field(default=None, description="Blank: today (the business date).")
    allow_over_receipt: bool = False
    note: str | None = Field(default=None, max_length=500)


class UndoIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ReceiptOut(BaseModel):
    movement_id: int
    received_on: date
    qty: float
    location_code: str
    location_name: str
    lot_no: str
    expiry_date: date | None
    unit_cost: float | None
    created_by: str
    added_to_stock: bool
    why_not: str | None


class POLineOut(BaseModel):
    po_no: str
    line_no: int
    item_code: str
    description: str
    sell_uom: str
    source: Literal["app", "bluetide", "both"]
    ordered: float
    received: float
    remaining: float
    status: Literal["open", "shipped", "received", "cancelled", "late"]
    counted: bool
    eta: date | None
    eta_source: str | None
    bluetide_date: date | None
    shipped_on: date | None
    container_no: str | None
    cancel_reason: str | None
    unit_cost: float | None
    flags: list[str]
    receipts: list[ReceiptOut]


class POOut(BaseModel):
    po_no: str
    vendor_code: str
    vendor_name: str
    order_date: date
    source: Literal["app", "bluetide", "both"]
    status: Literal["open", "shipped", "late", "partly_received", "received", "cancelled"]
    expected_date: date | None
    note: str | None
    created_by: str | None
    lines: list[POLineOut]


class MovementOut(BaseModel):
    id: int
    movement_date: date
    kind: str
    item_code: str
    location_code: str
    lot_no: str
    qty: float
    reverses_id: int | None
    created_by: str
