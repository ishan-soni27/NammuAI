"""Database tables (BUILD_PROMPT §8.3). Four layers, each with a different lifetime.

    RAW      raw_rows: every CSV row exactly as exported (JSONB, untrimmed strings).
             Kept per load run, never edited. Any number on screen traces back to one of
             these rows (ADR-003).
    CLEAN    vendors, items, item_aliases, customers, locations, inventory_lots,
             sales_lines, purchase_order_lines, prices, stockout_periods, excluded_orders:
             BlueTide data after the T01–T31 rules. Rebuilt from scratch on every load.
    APP      vendor_settings, item_settings, po_eta_overrides, handled_flags,
             harbor_storage_rows: what Dana knows that BlueTide doesn't; uploads, upload_files:
             the BlueTide files she uploaded. The loader NEVER truncates or deletes these
             (invariant #5, ADR-008). BlueTide owns every fact; the app records no transactions
             (ADR-032; the Phase 6 record-keeping tables were dropped in migration 0006).
    LOGGING  load_runs, data_issues, audit_log, event_log, request_log (§10).

Important design rule: APP-layer tables have NO foreign keys to CLEAN-layer tables.
    The loader rebuilds the clean layer by deleting and re-inserting it. A foreign key from
    `vendor_settings` to `vendors` would force that delete to either fail or CASCADE, and a
    cascade would silently wipe Dana's lead times. The service layer validates codes
    instead. `tests/unit/test_models.py` enforces this rule.

Types
    Quantities and money: NUMERIC(14,4) mapped to Python `Decimal` (no float drift on pound
    quantities, §16). Business dates: DATE. Log and audit times: TIMESTAMPTZ in UTC,
    defaulting to now() on the database server.

How to change this
    Add a column: add it here, then `alembic revision --autogenerate -m "..."`, review the
    generated file, and `alembic upgrade head`. New tables need RLS enabled in their
    migration (ADR-015; see migrations/versions/0001_initial_schema.py) and an entry in
    the right *_LAYER tuple at the bottom.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON

# Postgres types, with plain equivalents for SQLite so the API test suite can run on an
# in-memory database (there is no local Postgres; ADR-023). On Postgres these render exactly
# as before (BIGINT identity, JSONB), so the migration is unchanged.
JSON_DOC = JSON().with_variant(JSONB(), "postgresql")
BIG_ID = BigInteger().with_variant(Integer(), "sqlite")  # SQLite only autoincrements INTEGER keys

# Predictable constraint names, so migrations are reviewable and reversible.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Allowed values, kept next to the tables that use them. These are labels, not
# business numbers, so they live here rather than in business_rules.py.
SELL_UOMS = ("CS", "LB")
LIFECYCLE_STATUSES = ("active", "dormant", "discontinued", "legacy", "fresh_out_of_scope")
VENDOR_TYPES = ("stock_supplier", "fresh_supplier", "service_provider", "legacy")
DEMAND_CLASSES = (
    "real_demand",
    "cancelled",
    "transfer",
    "credit",
    "sample",
    "one_off",
    "fresh_out_of_scope",
)
SALES_STATUSES = ("INVOICED", "OPEN", "CANCELLED")
PO_STATUSES = ("open", "complete", "cancelled")  # normalized from Received/Closed/Open/Cancelled (T25)
ISSUE_SEVERITIES = ("info", "warning", "error")
ISSUE_ACTIONS = ("excluded", "corrected", "flagged")
LOAD_STATUSES = ("running", "succeeded", "failed")
EVENT_SOURCES = ("api", "loader", "web")
UPLOAD_KINDS = ("bluetide",)  # Dana's own templates were cut (ADR-032)
UPLOAD_STATUSES = ("open", "checked", "loaded", "failed", "discarded")


def _in(column: str, values: tuple[str, ...]) -> str:
    """SQL for a CHECK constraint like "sell_uom IN ('CS', 'LB')"."""
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {
        str: Text(),
        Decimal: Numeric(14, 4),
        datetime: DateTime(timezone=True),
        date: Date(),
        dict[str, Any]: JSON_DOC,
        list[dict[str, Any]]: JSON_DOC,
    }


def _pk() -> Mapped[int]:
    """Surrogate bigint identity primary key."""
    return mapped_column(BIG_ID, Identity(), primary_key=True)


def _created_now() -> Mapped[datetime]:
    """A timestamptz column set by the database (UTC) when the row is inserted."""
    return mapped_column(server_default=func.now())


def _raw_row_fk() -> Mapped[int | None]:
    """Pointer back to the exact CSV row this clean row came from (traceability, ADR-003)."""
    return mapped_column(BIG_ID, ForeignKey("raw_rows.id"))


# =====================================================================================
# LOGGING layer (load_runs first, because raw_rows and data_issues point to it)
# =====================================================================================


class LoadRun(Base):
    """One execution of the loader: when, which files (with SHA-256), row counts, outcome."""

    __tablename__ = "load_runs"
    __table_args__ = (CheckConstraint(_in("status", LOAD_STATUSES), name="status"),)

    id: Mapped[int] = _pk()
    started_at: Mapped[datetime] = _created_now()
    finished_at: Mapped[datetime | None]
    status: Mapped[str]
    as_of_date: Mapped[date]
    # [{"name": "bluetide_items.csv", "sha256": "...", "rows": 48}, ...]
    files: Mapped[list[dict[str, Any]]] = mapped_column(server_default="[]")
    summary: Mapped[dict[str, Any]] = mapped_column(server_default="{}")
    git_sha: Mapped[str | None]
    # The data/reference/*.csv seeds exactly as this load read them (file name -> text). The website's
    # import uses the last load's copy, because the deployed API doesn't ship data/ (Phase 6 step 3).
    reference: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOC)


# =====================================================================================
# RAW layer
# =====================================================================================


class RawRow(Base):
    """A CSV row exactly as BlueTide exported it (all values as untrimmed strings)."""

    __tablename__ = "raw_rows"
    __table_args__ = (Index("ix_raw_rows_run_file_line", "load_run_id", "source_file", "source_line_number"),)

    id: Mapped[int] = _pk()
    load_run_id: Mapped[int] = mapped_column(ForeignKey("load_runs.id", ondelete="CASCADE"))
    source_file: Mapped[str]  # e.g. "bluetide_items.csv"
    source_line_number: Mapped[int] = mapped_column(Integer)  # line in the file; header is line 1
    data: Mapped[dict[str, Any]]
    row_hash: Mapped[str]  # SHA-256 of the raw values; finds exact duplicates (T24)


# =====================================================================================
# CLEAN layer (rebuilt on every load)
# =====================================================================================


class Vendor(Base):
    __tablename__ = "vendors"
    __table_args__ = (CheckConstraint(_in("vendor_type", VENDOR_TYPES), name="vendor_type"),)

    vendor_code: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    country: Mapped[str | None]
    vendor_type: Mapped[str]  # from data/reference/vendor_types.csv (T28, ADR-018)
    lead_time_raw: Mapped[str | None]  # exactly as BlueTide has it, e.g. "2-3 wks" (T27)
    lead_time_days_system: Mapped[int | None] = mapped_column(Integer)  # parsed; null if blank
    payment_terms: Mapped[str | None]
    currency: Mapped[str | None]
    raw_row_id: Mapped[int | None] = _raw_row_fk()


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint(_in("sell_uom", SELL_UOMS), name="sell_uom"),
        CheckConstraint(_in("lifecycle_status", LIFECYCLE_STATUSES), name="lifecycle_status"),
    )

    item_code: Mapped[str] = mapped_column(primary_key=True)  # canonical: strip().upper() (T02)
    description: Mapped[str]
    category: Mapped[str]  # normalized: strip + title case (T08)
    storage: Mapped[str]
    pack_size_raw: Mapped[str | None]  # free text, e.g. "4x2.5lb" (T09)
    lb_per_case: Mapped[Decimal | None]  # from data/reference/pack_sizes.csv; null for LB items
    sell_uom: Mapped[str]
    vendor_code: Mapped[str] = mapped_column(ForeignKey("vendors.vendor_code"))
    shelf_life_months: Mapped[int | None] = mapped_column(Integer)  # informational only (T30)
    status_raw: Mapped[str | None]  # "Active", "A", "", "DISC"... (T04)
    lifecycle_status: Mapped[str]  # computed (§6.4); item_settings.lifecycle_override wins
    lifecycle_reason: Mapped[str]  # plain English, e.g. "No real sales since Apr 16, 2026"
    upc: Mapped[str | None]  # string: keeps leading zeros
    created_date: Mapped[date | None]
    raw_row_id: Mapped[int | None] = _raw_row_fk()


class ItemAlias(Base):
    """Raw code variants that map to a canonical item, e.g. "shr-1620 " -> "SHR-1620" (T02/T03)."""

    __tablename__ = "item_aliases"

    alias_code: Mapped[str] = mapped_column(primary_key=True)  # exact raw text, spaces included
    item_code: Mapped[str] = mapped_column(ForeignKey("items.item_code"))
    reason: Mapped[str]


class Customer(Base):
    __tablename__ = "customers"

    customer_code: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    customer_type: Mapped[str]  # RESTAURANT / GROCERY / INTERNAL / CRUISE; INTERNAL = transfers (T16)
    salesperson: Mapped[str | None]
    city: Mapped[str | None]
    state: Mapped[str | None]
    raw_row_id: Mapped[int | None] = _raw_row_fk()


class Location(Base):
    """Seeded from data/reference/locations.csv. Decides what counts as sellable (T11)."""

    __tablename__ = "locations"

    code: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    is_sellable: Mapped[bool]
    is_third_party_storage: Mapped[bool]  # Harbor: costs money per pallet per month
    may_return_to_stock: Mapped[bool]  # QA-HOLD: "sometimes it passes and comes back"
    description: Mapped[str]


class InventoryLot(Base):
    """One lot in the latest on-hand snapshot (T01), with quantities converted to sell_uom (T10)."""

    __tablename__ = "inventory_lots"
    __table_args__ = (
        UniqueConstraint("snapshot_date", "item_code", "location_code", "lot_no"),
        Index("ix_inventory_lots_item", "item_code"),
    )

    id: Mapped[int] = _pk()
    snapshot_date: Mapped[date]
    item_code: Mapped[str] = mapped_column(ForeignKey("items.item_code"))
    location_code: Mapped[str] = mapped_column(ForeignKey("locations.code"))
    lot_no: Mapped[str]
    is_adjustment: Mapped[bool]  # ADJ-xxxx lines (T13)
    qty_source: Mapped[Decimal]  # as exported
    uom_source: Mapped[str]  # as exported: CS or LB
    qty_sell_uom: Mapped[Decimal | None]  # converted; null only if no conversion factor (logged error)
    pack_date: Mapped[date | None]
    expiry_date: Mapped[date | None]  # the ONLY age signal we trust (T30)
    received_date: Mapped[date | None]
    unit_cost_source: Mapped[Decimal | None]
    unit_cost_sell_uom: Mapped[Decimal | None]
    vendor_lot_ref: Mapped[str | None]
    raw_row_id: Mapped[int | None] = _raw_row_fk()


class SalesLine(Base):
    __tablename__ = "sales_lines"
    __table_args__ = (
        UniqueConstraint("order_no", "line_no"),
        CheckConstraint(_in("status", SALES_STATUSES), name="status"),
        CheckConstraint(_in("demand_class", DEMAND_CLASSES), name="demand_class"),
        Index("ix_sales_lines_item_class_date", "item_code", "demand_class", "order_date"),
    )

    id: Mapped[int] = _pk()
    order_no: Mapped[str]
    line_no: Mapped[int] = mapped_column(Integer)
    order_date: Mapped[date]  # demand is dated by order date (ADR-013)
    ship_date: Mapped[date | None]  # open orders leave stock on this date (T22)
    customer_code: Mapped[str] = mapped_column(ForeignKey("customers.customer_code"))
    item_code: Mapped[str] = mapped_column(ForeignKey("items.item_code"))
    qty: Mapped[Decimal]
    uom: Mapped[str]
    unit_price: Mapped[Decimal]
    ext_price: Mapped[Decimal]
    status: Mapped[str]
    salesperson: Mapped[str | None]
    demand_class: Mapped[str]  # §6.2 classification
    raw_row_id: Mapped[int | None] = _raw_row_fk()


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        UniqueConstraint("po_no", "line_no"),
        CheckConstraint(_in("status", PO_STATUSES), name="status"),
    )

    id: Mapped[int] = _pk()
    po_no: Mapped[str]
    line_no: Mapped[int] = mapped_column(Integer)
    vendor_code: Mapped[str] = mapped_column(ForeignKey("vendors.vendor_code"))
    item_code: Mapped[str] = mapped_column(ForeignKey("items.item_code"))
    order_date: Mapped[date]
    expected_date_system: Mapped[date | None]  # BlueTide's date, often stale (T26)
    qty_ordered: Mapped[Decimal]
    qty_received: Mapped[Decimal]
    qty_remaining_sell_uom: Mapped[Decimal | None]  # ordered - received, converted (T25)
    uom: Mapped[str]
    unit_cost: Mapped[Decimal | None]
    status_raw: Mapped[str]
    status: Mapped[str]
    container_no: Mapped[str | None]
    raw_row_id: Mapped[int | None] = _raw_row_fk()


class Price(Base):
    """Price list, loaded for Marco's phase 2. Unused in v1 (T29). No FK: FUEL-SURCH is not an item."""

    __tablename__ = "prices"

    id: Mapped[int] = _pk()
    item_code: Mapped[str]
    tier: Mapped[str]
    price: Mapped[Decimal]
    uom: Mapped[str]
    effective_from: Mapped[date | None]
    effective_to: Mapped[date | None]  # null = open-ended
    raw_row_id: Mapped[int | None] = _raw_row_fk()


class StockoutPeriod(Base):
    """Known stockout windows (inclusive). Their days are left out of rate calculations (T23)."""

    __tablename__ = "stockout_periods"
    __table_args__ = (CheckConstraint("end_date >= start_date", name="dates_in_order"),)

    id: Mapped[int] = _pk()
    item_code: Mapped[str] = mapped_column(ForeignKey("items.item_code"))
    start_date: Mapped[date]
    end_date: Mapped[date]
    source: Mapped[str]
    note: Mapped[str | None]


class ExcludedOrder(Base):
    """Orders that are not real demand, e.g. the cruise line one-off (T20)."""

    __tablename__ = "excluded_orders"

    order_no: Mapped[str] = mapped_column(primary_key=True)
    reason: Mapped[str]
    source: Mapped[str]


# =====================================================================================
# APP layer (Dana's knowledge; the loader never touches these; no FKs to CLEAN tables)
# =====================================================================================


class VendorSetting(Base):
    """Dana's real lead time, cushion and order cycle per vendor (T27, §6.5)."""

    __tablename__ = "vendor_settings"
    __table_args__ = (
        # Sanity backstops only. The user-facing 1–365 limits are in business_rules.py.
        CheckConstraint("lead_time_days > 0", name="lead_time_positive"),
        CheckConstraint("safety_days >= 0", name="safety_non_negative"),
        CheckConstraint("order_cycle_days > 0", name="order_cycle_positive"),
    )

    vendor_code: Mapped[str] = mapped_column(primary_key=True)
    lead_time_days: Mapped[int] = mapped_column(Integer)
    safety_days: Mapped[int] = mapped_column(Integer)
    order_cycle_days: Mapped[int] = mapped_column(Integer)
    source: Mapped[str]  # "seed: call 00:02:25 ..." or "Set by Dana"
    note: Mapped[str | None]
    updated_at: Mapped[datetime] = _created_now()
    updated_by: Mapped[str]


class ItemSetting(Base):
    """Per-item overrides: "this item is still active", or a different cushion."""

    __tablename__ = "item_settings"
    __table_args__ = (
        CheckConstraint(
            "lifecycle_override IS NULL OR " + _in("lifecycle_override", LIFECYCLE_STATUSES),
            name="lifecycle_override",
        ),
        CheckConstraint(
            "safety_days_override IS NULL OR safety_days_override >= 0",
            name="safety_override_non_negative",
        ),
        CheckConstraint("cases_per_pallet IS NULL OR cases_per_pallet > 0", name="cases_per_pallet_positive"),
    )

    item_code: Mapped[str] = mapped_column(primary_key=True)
    lifecycle_override: Mapped[str | None]
    safety_days_override: Mapped[int | None] = mapped_column(Integer)
    cases_per_pallet: Mapped[int | None] = mapped_column(Integer)  # Dana's number, for Harbor storage cost
    note: Mapped[str | None]
    updated_at: Mapped[datetime] = _created_now()
    updated_by: Mapped[str]


class PoEtaOverride(Base):
    """A real arrival date Dana typed in for a PO line (promised in email Q3; T26)."""

    __tablename__ = "po_eta_overrides"
    __table_args__ = (PrimaryKeyConstraint("po_no", "line_no"),)

    po_no: Mapped[str]
    line_no: Mapped[int] = mapped_column(Integer)
    eta: Mapped[date]
    note: Mapped[str | None]
    updated_at: Mapped[datetime] = _created_now()
    updated_by: Mapped[str]


class HandledFlag(Base):
    """ "I've handled this one" (Dana 00:09:45). Never auto-deleted, only cleared (§6.10)."""

    __tablename__ = "handled_flags"
    __table_args__ = (Index("ix_handled_flags_item", "item_code"),)

    id: Mapped[int] = _pk()
    item_code: Mapped[str]
    qty: Mapped[Decimal | None]  # with eta, counts as incoming supply (§6.6)
    eta: Mapped[date | None]
    note: Mapped[str | None]
    created_at: Mapped[datetime] = _created_now()
    created_by: Mapped[str]
    cleared_at: Mapped[datetime | None]
    cleared_by: Mapped[str | None]
    clear_reason: Mapped[str | None]


# ---- Dana's own records (Phase 6; ADR-026, ADR-027) ---------------------------------------
# Same rule as above: no foreign keys into the clean layer. Item, vendor and location codes are
# plain text, checked by the service layer. Foreign keys between these app tables are fine.


class Upload(Base):
    """One upload of BlueTide's export files from the website (check first, then load; ADR-029)."""

    __tablename__ = "uploads"
    __table_args__ = (
        CheckConstraint(_in("kind", UPLOAD_KINDS), name="kind"),
        CheckConstraint(_in("status", UPLOAD_STATUSES), name="status"),
    )

    id: Mapped[int] = _pk()
    kind: Mapped[str]
    status: Mapped[str]
    report: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOC)  # the check (dry run), then the load
    confirm_code: Mapped[str | None]  # the one-time code the check hands out; the load must send it
    load_run_id: Mapped[int | None] = mapped_column(BIG_ID, ForeignKey("load_runs.id"))
    error: Mapped[str | None]
    created_at: Mapped[datetime] = _created_now()
    created_by: Mapped[str]
    updated_at: Mapped[datetime] = _created_now()
    updated_by: Mapped[str]


class UploadFile(Base):
    """A file Dana uploaded into one slot of an import, kept byte for byte (sha256 as for the loader)."""

    __tablename__ = "upload_files"
    __table_args__ = (UniqueConstraint("upload_id", "slot"),)

    id: Mapped[int] = _pk()
    upload_id: Mapped[int] = mapped_column(BIG_ID, ForeignKey("uploads.id"))
    slot: Mapped[str]  # "items", "sales_lines", ... (one per BlueTide export)
    file_name: Mapped[str]
    sha256: Mapped[str]
    size_bytes: Mapped[int] = mapped_column(Integer)
    rows: Mapped[int] = mapped_column(Integer)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = _created_now()


HARBOR_ROW_KINDS = ("at_harbor", "what_if")


class HarborStorageRow(Base):
    """A Harbor storage calculation Dana added to her table (P1 #1; ADR-031).

    Kept exactly as worked out (rate included), so a later change to the rate or the stock
    never rewrites what she saved. at_harbor = what was there that day (pallets per lot);
    what_if = an amount she typed in."""

    __tablename__ = "harbor_storage_rows"
    __table_args__ = (
        CheckConstraint(_in("kind", HARBOR_ROW_KINDS), name="kind"),
        CheckConstraint("cases >= 0", name="cases_not_negative"),
        CheckConstraint("cases_per_pallet > 0", name="cases_per_pallet_positive"),
    )

    id: Mapped[int] = _pk()
    kind: Mapped[str]
    as_of_date: Mapped[date]  # the business day it was worked out for
    item_code: Mapped[str]
    description: Mapped[str]
    cases: Mapped[Decimal]
    lots: Mapped[int] = mapped_column(Integer)
    cases_per_pallet: Mapped[int] = mapped_column(Integer)
    pallets: Mapped[int] = mapped_column(Integer)
    rate_per_pallet_month: Mapped[Decimal]
    cost_per_month: Mapped[Decimal]
    created_at: Mapped[datetime] = _created_now()
    created_by: Mapped[str]


# =====================================================================================
# LOGGING layer (continued)
# =====================================================================================


class DataIssue(Base):
    """Every row the loader excluded, corrected or flagged, with the trap that caused it (§10 layer 2)."""

    __tablename__ = "data_issues"
    __table_args__ = (
        CheckConstraint(_in("severity", ISSUE_SEVERITIES), name="severity"),
        CheckConstraint(_in("action", ISSUE_ACTIONS), name="action"),
        Index("ix_data_issues_run_trap", "load_run_id", "trap_id"),
    )

    id: Mapped[int] = _pk()
    load_run_id: Mapped[int] = mapped_column(ForeignKey("load_runs.id", ondelete="CASCADE"))
    source_file: Mapped[str]
    source_line_number: Mapped[int | None] = mapped_column(Integer)
    raw_row_id: Mapped[int | None] = mapped_column(BIG_ID, ForeignKey("raw_rows.id", ondelete="CASCADE"))
    trap_id: Mapped[str | None]  # "T01".."T31"
    rule_code: Mapped[str]  # e.g. "older_snapshot_row"
    severity: Mapped[str]
    action: Mapped[str]
    item_code: Mapped[str | None]
    field: Mapped[str | None]
    original_value: Mapped[str | None]
    new_value: Mapped[str | None]
    message: Mapped[str]  # plain English, shown on the Data notes page


class AuditLog(Base):
    """Who changed what, before and after. Written in the same transaction as the change (§10 layer 3)."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_occurred_at", "occurred_at"),)

    id: Mapped[int] = _pk()
    occurred_at: Mapped[datetime] = _created_now()
    actor: Mapped[str]
    action: Mapped[str]  # e.g. "vendor_settings.update"
    entity_type: Mapped[str]
    entity_id: Mapped[str]
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOC)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOC)
    request_id: Mapped[str | None]


class EventLog(Base):
    """Notable events and errors from the API, the loader and the browser."""

    __tablename__ = "event_log"
    __table_args__ = (
        CheckConstraint(_in("source", EVENT_SOURCES), name="source"),
        Index("ix_event_log_occurred_at", "occurred_at"),
    )

    id: Mapped[int] = _pk()
    occurred_at: Mapped[datetime] = _created_now()
    level: Mapped[str]
    source: Mapped[str]
    event: Mapped[str]
    request_id: Mapped[str | None]
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOC)


class RequestLog(Base):
    """One row per API request (written in the background, Phase 4)."""

    __tablename__ = "request_log"
    __table_args__ = (Index("ix_request_log_occurred_at", "occurred_at"),)

    id: Mapped[int] = _pk()
    occurred_at: Mapped[datetime] = _created_now()
    request_id: Mapped[str]
    method: Mapped[str]
    path: Mapped[str]
    status: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[Decimal] = mapped_column(Numeric(10, 1))
    actor: Mapped[str | None]


# =====================================================================================
# Layer registry: the loader uses this to know what it may rebuild (invariant #5)
# =====================================================================================

RAW_LAYER: tuple[str, ...] = ("raw_rows",)
CLEAN_LAYER: tuple[str, ...] = (
    "vendors",
    "items",
    "item_aliases",
    "customers",
    "locations",
    "inventory_lots",
    "sales_lines",
    "purchase_order_lines",
    "prices",
    "stockout_periods",
    "excluded_orders",
)
APP_LAYER: tuple[str, ...] = (
    "vendor_settings",
    "item_settings",
    "po_eta_overrides",
    "handled_flags",
    "harbor_storage_rows",
    "uploads",
    "upload_files",
)
# Dropped in migration 0006 (ADR-032): the Phase 6 record-keeping tables. Kept here only so a test can
# prove no model brings them back.
DROPPED_IN_0006: tuple[str, ...] = (
    "app_vendors",
    "app_items",
    "purchase_orders",
    "purchase_order_lines_app",
    "po_line_status",
    "stock_movements",
    "app_customers",
    "shipments",
    "shipment_lines",
    "stock_counts",
    "stock_count_lines",
    "app_sales_lines",
)
LOGGING_LAYER: tuple[str, ...] = ("load_runs", "data_issues", "audit_log", "event_log", "request_log")
