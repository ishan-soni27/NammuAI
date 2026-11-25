"""Data shapes that flow through the loader: raw records in, clean rows and issues out.

How it fits
    read_raw.py  -> RawFile / RawRecord           (strings exactly as exported)
    pipeline.py  -> CleanDataset + list[Issue]    (pure: no DB, no clock)
    write.py     -> database rows                 (field names below == DB column names)

Every clean row carries `source` (file + line), so write.py can set `raw_row_id` and any
number on screen traces back to one line in a BlueTide export (ADR-003).

How to change this: a new clean column needs a field here, the same column in
app/db/models.py, a migration, and code in pipeline.py that fills it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

Severity = Literal["info", "warning", "error"]
Action = Literal["excluded", "corrected", "flagged"]


# ---- Raw input ------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceRef:
    """Where a row came from: file name and physical line number (header = line 1)."""

    file: str
    line: int


@dataclass(frozen=True)
class RawRecord:
    source: SourceRef
    data: dict[str, str]  # column -> value, untrimmed, exactly as in the CSV
    row_hash: str  # SHA-256 of the values; equal hashes = exact duplicate rows (T24)

    def get(self, column: str) -> str:
        """The raw value of a column ('' if the column is missing)."""
        return self.data.get(column, "")


@dataclass(frozen=True)
class RawFile:
    logical_name: str  # "items", "sales_lines", ...
    file_name: str  # "bluetide_items.csv"
    sha256: str
    records: tuple[RawRecord, ...]


# ---- Issues (data_issues rows) --------------------------------------------------------


@dataclass(frozen=True)
class Issue:
    """One row excluded, corrected or flagged, with the trap that caused it (§10 layer 2)."""

    source: SourceRef | None
    trap_id: str | None
    rule_code: str
    severity: Severity
    action: Action
    message: str  # plain English, shown on the Data notes page
    item_code: str | None = None
    field: str | None = None
    original_value: str | None = None
    new_value: str | None = None


@dataclass
class IssueLog:
    """Collects issues while the pipeline runs. Order is preserved for a readable report."""

    issues: list[Issue] = field(default_factory=list)

    def add(
        self,
        source: SourceRef | None,
        trap_id: str | None,
        rule_code: str,
        severity: Severity,
        action: Action,
        message: str,
        *,
        item_code: str | None = None,
        field: str | None = None,
        original_value: str | None = None,
        new_value: str | None = None,
    ) -> None:
        self.issues.append(
            Issue(
                source=source,
                trap_id=trap_id,
                rule_code=rule_code,
                severity=severity,
                action=action,
                message=message,
                item_code=item_code,
                field=field,
                original_value=original_value,
                new_value=new_value,
            )
        )

    def by_trap(self, trap_id: str) -> list[Issue]:
        return [i for i in self.issues if i.trap_id == trap_id]


# ---- Reference seeds (data/reference/*.csv) -------------------------------------------


@dataclass(frozen=True)
class PackSize:
    item_code: str
    pack_size_raw: str
    lb_per_case: Decimal | None  # None for items sold by the pound
    verified_by: str
    note: str


@dataclass(frozen=True)
class VendorSettingSeed:
    vendor_code: str
    lead_time_days: int
    safety_days: int
    order_cycle_days: int
    source: str
    note: str


@dataclass(frozen=True)
class LocationSeed:
    code: str
    name: str
    is_sellable: bool
    is_third_party_storage: bool
    may_return_to_stock: bool
    description: str


@dataclass(frozen=True)
class StockoutPeriodSeed:
    item_code: str
    start_date: date
    end_date: date
    source: str
    note: str


@dataclass(frozen=True)
class ExcludedOrderSeed:
    order_no: str
    reason: str
    source: str


@dataclass(frozen=True)
class ReferenceData:
    pack_sizes: dict[str, PackSize]
    vendor_settings: tuple[VendorSettingSeed, ...]
    vendor_types: dict[str, str]
    locations: tuple[LocationSeed, ...]
    stockout_periods: tuple[StockoutPeriodSeed, ...]
    excluded_orders: tuple[ExcludedOrderSeed, ...]


# ---- Clean rows (one dataclass per clean table; names match app/db/models.py) ---------


@dataclass(frozen=True)
class CleanVendor:
    vendor_code: str
    name: str
    country: str | None
    vendor_type: str
    lead_time_raw: str | None
    lead_time_days_system: int | None
    payment_terms: str | None
    currency: str | None
    source: SourceRef


@dataclass(frozen=True)
class CleanItem:
    item_code: str
    description: str
    category: str
    storage: str
    pack_size_raw: str | None
    lb_per_case: Decimal | None
    sell_uom: str
    vendor_code: str
    shelf_life_months: int | None
    status_raw: str | None
    lifecycle_status: str
    lifecycle_reason: str
    upc: str | None
    created_date: date | None
    source: SourceRef


@dataclass(frozen=True)
class CleanAlias:
    alias_code: str
    item_code: str
    reason: str


@dataclass(frozen=True)
class CleanCustomer:
    customer_code: str
    name: str
    customer_type: str
    salesperson: str | None
    city: str | None
    state: str | None
    source: SourceRef


@dataclass(frozen=True)
class CleanLocation:
    code: str
    name: str
    is_sellable: bool
    is_third_party_storage: bool
    may_return_to_stock: bool
    description: str


@dataclass(frozen=True)
class CleanLot:
    snapshot_date: date
    item_code: str
    location_code: str
    lot_no: str
    is_adjustment: bool
    qty_source: Decimal
    uom_source: str
    qty_sell_uom: Decimal | None
    pack_date: date | None
    expiry_date: date | None
    received_date: date | None
    unit_cost_source: Decimal | None
    unit_cost_sell_uom: Decimal | None
    vendor_lot_ref: str | None
    source: SourceRef


@dataclass(frozen=True)
class CleanSale:
    order_no: str
    line_no: int
    order_date: date
    ship_date: date | None
    customer_code: str
    item_code: str
    qty: Decimal
    uom: str
    unit_price: Decimal
    ext_price: Decimal
    status: str
    salesperson: str | None
    demand_class: str
    source: SourceRef


@dataclass(frozen=True)
class CleanPOLine:
    po_no: str
    line_no: int
    vendor_code: str
    item_code: str
    order_date: date
    expected_date_system: date | None
    qty_ordered: Decimal
    qty_received: Decimal
    qty_remaining_sell_uom: Decimal | None
    uom: str
    unit_cost: Decimal | None
    status_raw: str
    status: str
    container_no: str | None
    source: SourceRef


@dataclass(frozen=True)
class CleanPrice:
    item_code: str
    tier: str
    price: Decimal
    uom: str
    effective_from: date | None
    effective_to: date | None
    source: SourceRef


@dataclass(frozen=True)
class CleanDataset:
    """Everything the clean layer will contain after one load."""

    snapshot_date: date
    vendors: tuple[CleanVendor, ...]
    items: tuple[CleanItem, ...]
    aliases: tuple[CleanAlias, ...]
    customers: tuple[CleanCustomer, ...]
    locations: tuple[CleanLocation, ...]
    lots: tuple[CleanLot, ...]
    sales: tuple[CleanSale, ...]
    po_lines: tuple[CleanPOLine, ...]
    prices: tuple[CleanPrice, ...]
    stockout_periods: tuple[StockoutPeriodSeed, ...]
    excluded_orders: tuple[ExcludedOrderSeed, ...]


@dataclass(frozen=True)
class FileStats:
    """Reconciliation for one source file (DATA_LOAD_REPORT.md)."""

    file_name: str
    sha256: str
    rows_read: int
    rows_stored: int  # rows that became a clean-table row
    issues_by_action: dict[str, int]


@dataclass(frozen=True)
class LoadResult:
    dataset: CleanDataset
    issues: tuple[Issue, ...]
    raw_files: tuple[RawFile, ...]
    file_stats: tuple[FileStats, ...]
