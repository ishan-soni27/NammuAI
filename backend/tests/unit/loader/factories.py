"""Tiny fake BlueTide exports for rule tests.

Each helper returns one CSV row as a dict with sensible defaults; override only the
columns a test cares about. `load(...)` runs the real pipeline on those rows, so each
test exercises the same code path as a real load, just with three rows instead of 15,750.
"""

from __future__ import annotations

from decimal import Decimal

from app.config.business_rules import BusinessRules
from app.loader.pipeline import build_dataset
from app.loader.read_raw import RAW_FILES, row_hash
from app.loader.types import (
    ExcludedOrderSeed,
    LoadResult,
    LocationSeed,
    PackSize,
    RawFile,
    RawRecord,
    ReferenceData,
    SourceRef,
    StockoutPeriodSeed,
    VendorSettingSeed,
)

RULES = BusinessRules()  # AS_OF 2026-11-16

# The pack text each test item uses, so the fake verified table matches BlueTide's text (T09).
PACK_TEXT = {"SHR-1620": "10x2lb", "LOB-T56": "10 lb cs", "FR-COD": "per lb", "ZZ-SCL-0002": ""}


def item(**kw: str) -> dict[str, str]:
    row = {
        "item_code": "SHR-1620",
        "description": "WHITE SHRIMP 16/20",
        "category": "Shrimp",
        "storage": "FROZEN",
        "pack_size": "10x2lb",
        "sell_uom": "CS",
        "vendor_code": "BXE",
        "shelf_life_months": "24",
        "status": "Active",
        "upc": "030931011872",
        "default_bin": "E-40",
        "created_date": "2018-10-14",
    }
    row.update(kw)
    return row


def lot(**kw: str) -> dict[str, str]:
    row = {
        "snapshot_date": "2026-11-15",
        "item_code": "SHR-1620",
        "description": "WHITE SHRIMP",
        "location": "NB",
        "lot_no": "L260901-01",
        "qty": "100",
        "uom": "CS",
        "pack_date": "2026-06-01",
        "expiry_date": "2028-06-01",
        "received_date": "2026-09-01",
        "unit_cost": "120.00",
        "vendor_lot_ref": "V1",
    }
    row.update(kw)
    return row


def sale(**kw: str) -> dict[str, str]:
    row = {
        "order_no": "SO-1",
        "line_no": "1",
        "order_date": "2026-11-02",
        "ship_date": "2026-11-03",
        "customer_code": "R101",
        "customer_name": "Dory Grill",
        "item_code": "SHR-1620",
        "item_description": "WHITE SHRIMP",
        "qty": "5",
        "uom": "CS",
        "unit_price": "150.00",
        "ext_price": "750.00",
        "status": "INVOICED",
        "salesperson": "M. Ruiz",
    }
    row.update(kw)
    return row


def po(**kw: str) -> dict[str, str]:
    row = {
        "po_no": "PO-1",
        "line_no": "1",
        "vendor_code": "BXE",
        "item_code": "SHR-1620",
        "order_date": "2026-11-02",
        "expected_date": "2026-12-28",
        "qty_ordered": "600",
        "qty_received": "0",
        "uom": "CS",
        "unit_cost": "90.00",
        "status": "Open",
        "incoterms": "CFR",
        "container_no": "",
        "buyer": "DOKAFOR",
    }
    row.update(kw)
    return row


def vendor(**kw: str) -> dict[str, str]:
    row = {
        "vendor_code": "BXE",
        "vendor_name": "Bien Xanh Export Co.",
        "country": "Vietnam",
        "lead_time_days": "56",
        "payment_terms": "Net 60",
        "currency": "USD",
        "contact_email": "",
        "phone": "",
        "address": "",
    }
    row.update(kw)
    return row


def customer(**kw: str) -> dict[str, str]:
    row = {
        "customer_code": "R101",
        "customer_name": "Dory Grill",
        "customer_type": "RESTAURANT",
        "salesperson": "M. Ruiz",
        "city": "Warwick",
        "state": "RI",
        "credit_limit": "5000",
        "payment_terms": "COD",
        "delivery_route": "RT-02",
        "tax_id": "",
        "created_date": "2025-08-18",
    }
    row.update(kw)
    return row


def price(**kw: str) -> dict[str, str]:
    row = {
        "item_code": "SHR-1620",
        "price_tier": "STD",
        "price": "153.00",
        "uom": "CS",
        "effective_from": "2026-06-01",
        "effective_to": "",
    }
    row.update(kw)
    return row


def raw_file(logical: str, rows: list[dict[str, str]]) -> RawFile:
    name = RAW_FILES[logical]
    records = tuple(
        RawRecord(source=SourceRef(name, n), data=dict(r), row_hash=row_hash(dict(r)))
        for n, r in enumerate(rows, start=2)  # header is line 1
    )
    return RawFile(logical_name=logical, file_name=name, sha256="test", records=records)


def reference(
    pack_sizes: dict[str, str | None] | None = None,
    vendor_settings: list[VendorSettingSeed] | None = None,
    vendor_types: dict[str, str] | None = None,
    stockouts: list[StockoutPeriodSeed] | None = None,
    excluded_orders: list[str] | None = None,
) -> ReferenceData:
    packs = pack_sizes if pack_sizes is not None else {"SHR-1620": "20"}
    return ReferenceData(
        pack_sizes={
            code: PackSize(code, PACK_TEXT.get(code, ""), Decimal(v) if v else None, "test", "")
            for code, v in packs.items()
        },
        vendor_settings=tuple(
            vendor_settings
            if vendor_settings is not None
            else [VendorSettingSeed("BXE", 84, 14, 7, "test", "")]
        ),
        vendor_types=vendor_types if vendor_types is not None else {"BXE": "stock_supplier"},
        locations=(
            LocationSeed("NB", "New Bedford", True, False, False, ""),
            LocationSeed("PVD", "Providence", True, False, False, ""),
            LocationSeed("HCS", "Harbor Cold Storage", True, True, False, ""),
            LocationSeed("QA-HOLD", "QA hold", False, False, True, ""),
            LocationSeed("DAMAGED", "Damaged", False, False, False, ""),
        ),
        stockout_periods=tuple(stockouts or []),
        excluded_orders=tuple(ExcludedOrderSeed(o, "test", "test") for o in (excluded_orders or [])),
    )


def load(
    items: list[dict[str, str]] | None = None,
    lots: list[dict[str, str]] | None = None,
    sales: list[dict[str, str]] | None = None,
    pos: list[dict[str, str]] | None = None,
    vendors: list[dict[str, str]] | None = None,
    customers: list[dict[str, str]] | None = None,
    prices: list[dict[str, str]] | None = None,
    ref: ReferenceData | None = None,
    rules: BusinessRules = RULES,
) -> LoadResult:
    """Run the real pipeline on fake rows. Every file gets at least the defaults it needs."""
    raw = {
        "items": raw_file("items", items or [item()]),
        "inventory_on_hand": raw_file("inventory_on_hand", lots or [lot()]),
        "sales_lines": raw_file("sales_lines", sales if sales is not None else [sale()]),
        "purchase_orders": raw_file("purchase_orders", pos if pos is not None else []),
        "vendors": raw_file("vendors", vendors or [vendor()]),
        "customers": raw_file("customers", customers or [customer()]),
        "price_list": raw_file("price_list", prices if prices is not None else []),
    }
    return build_dataset(raw, ref or reference(), rules)


def issues(result: LoadResult, trap: str) -> list:
    return [i for i in result.issues if i.trap_id == trap]
