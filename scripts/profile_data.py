"""Re-derive the data-audit facts straight from the raw BlueTide CSVs (BUILD_PROMPT §5, §14 Phase 2).

Why this exists
    It is a SECOND, independent implementation of the key facts. It imports nothing from
    the app, so a bug in the loader can't hide here too. If this script and the golden
    tests (backend/tests/golden/test_real_data.py) ever disagree, one of them is wrong:
    investigate before changing either.

Run from the repo root with any Python 3.9+ (standard library only):
    python3 scripts/profile_data.py

Prints each fact with a check mark against the value in BUILD_PROMPT §5.3 / docs/DATA_AUDIT.md,
and exits non-zero if any fact doesn't match.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
AS_OF = date(2026, 11, 16)
SIX_MONTH_LINE = date(2027, 5, 16)
SELLABLE = {"NB", "PVD", "HCS"}
LB_PER_CASE = {"LOB-T56": Decimal("10"), "CAL-RING": Decimal("13.2")}  # the only case items with pound lots
failures = 0


def rows(name: str) -> list[dict[str, str]]:
    with (RAW / f"bluetide_{name}.csv").open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def canon(code: str) -> str:
    return code.strip().upper()


def parse_date(text: str) -> date | None:
    if not text:
        return None
    if "/" in text:
        return datetime.strptime(text, "%m/%d/%Y").date()
    return date.fromisoformat(text)


def check(label: str, actual: object, expected: object) -> None:
    global failures
    ok = actual == expected
    failures += 0 if ok else 1
    print(f"  {'✓' if ok else '✗'} {label}: {actual}" + ("" if ok else f"   (expected {expected})"))


items = rows("items")
inventory = rows("inventory_on_hand")
sales = rows("sales_lines")
pos = rows("purchase_orders")
vendors = rows("vendors")
customers = {c["customer_code"]: c["customer_type"] for c in rows("customers")}

print("Files")
for name, data in [
    ("items", items),
    ("inventory_on_hand", inventory),
    ("sales_lines", sales),
    ("purchase_orders", pos),
    ("vendors", vendors),
    ("customers", customers),
]:
    print(f"  bluetide_{name}.csv: {len(data):,} rows")

print("\nOn hand (G01, G04–G09)")
nights = Counter(r["snapshot_date"] for r in inventory)
latest_night = max(nights)
check("G01 snapshot nights", dict(sorted(nights.items())), {"2026-11-14": 115, "2026-11-15": 113})
latest = [r for r in inventory if r["snapshot_date"] == latest_night]
sellable: dict[str, Decimal] = defaultdict(Decimal)
on_hold: dict[str, Decimal] = defaultdict(Decimal)
for r in latest:
    code, qty = canon(r["item_code"]), Decimal(r["qty"])
    if r["uom"] == "LB" and code in LB_PER_CASE:
        qty = qty / LB_PER_CASE[code]
    expiry = parse_date(r["expiry_date"])
    if r["location"] == "QA-HOLD":
        on_hold[code] += qty
    elif r["location"] in SELLABLE and (qty < 0 or expiry is None or expiry >= AS_OF):
        sellable[code] += qty
check("G04 SHR-1620 sellable / on hold", (sellable["SHR-1620"], on_hold["SHR-1620"]), (480, 80))
check("G05 LOB-T56 sellable", sellable["LOB-T56"], 83)
check("G06 CAL-RING sellable", sellable["CAL-RING"], 353)
check(
    "G07 COD-FIL / SHR-2630 / POL-BLK",
    (sellable["COD-FIL"], sellable["SHR-2630"], sellable["POL-BLK"]),
    (206, 429, Decimal("8478.5")),
)
check("G08 HAD-FIL sellable / on hold", (sellable["HAD-FIL"], on_hold["HAD-FIL"]), (170, 300))
check("G09 SAL-POR8 / SHR-4150 sellable", (sellable["SAL-POR8"], sellable["SHR-4150"]), (700, 381))
inside = sorted(
    (canon(r["item_code"]), r["lot_no"])
    for r in latest
    if not canon(r["item_code"]).startswith(("ZZ-", "FR-"))
    and r["expiry_date"]
    and AS_OF <= parse_date(r["expiry_date"]) < SIX_MONTH_LINE
    and Decimal(r["qty"]) > 0
)
check("G10 lots inside the six-month line", len(inside), 5)

print("\nItem master (G02, G03 inputs)")
check("G02 canonical items", len({canon(i["item_code"]) for i in items}), 45)
last_sale: dict[str, date] = {}
for s in sales:
    code = canon(s["item_code"])
    if s["status"] != "CANCELLED" and Decimal(s["qty"]) > 0 and Decimal(s["unit_price"]) > 0:
        d = parse_date(s["order_date"])
        if d and (code not in last_sale or d > last_sale[code]):
            last_sale[code] = d
check(
    "T06 last real sale TIL-FIL / SHR-6170 / PAN-1012",
    tuple(str(last_sale[c]) for c in ["TIL-FIL", "SHR-6170", "PAN-1012"]),
    ("2026-04-16", "2026-03-05", "2026-02-10"),
)

print("\nSales (G11–G13)")
fresh = {canon(i["item_code"]) for i in items if i["storage"] == "FRESH" or i["item_code"].startswith("FR-")}
classes: Counter[str] = Counter()
committed: dict[str, Decimal] = defaultdict(Decimal)
for s in sales:
    qty, price, code = Decimal(s["qty"]), Decimal(s["unit_price"]), canon(s["item_code"])
    if s["status"] == "CANCELLED":
        k = "cancelled"
    elif customers.get(s["customer_code"]) == "INTERNAL":
        k = "transfer"
    elif s["order_no"].startswith("CM-") or qty < 0:
        k = "credit"
    elif price == 0:
        k = "sample"
    elif s["order_no"] == "SO-245503":
        k = "one_off"
    elif code in fresh:
        k = "fresh_out_of_scope"
    else:
        k = "real_demand"
    classes[k] += 1
    if k == "real_demand" and s["status"] == "OPEN":
        committed[code] += qty
check(
    "G11 demand classes",
    dict(classes),
    {
        "real_demand": 12040,
        "fresh_out_of_scope": 2856,
        "transfer": 378,
        "cancelled": 294,
        "sample": 104,
        "credit": 76,
        "one_off": 2,
    },
)
check("G12 rows with MM/DD/YYYY dates", sum(1 for s in sales if "/" in s["order_date"]), 51)
check(
    "G13 committed SHR-1620 / CRAB-SNW5 / SHR-2125",
    (committed["SHR-1620"], committed["CRAB-SNW5"], committed["SHR-2125"]),
    (201, 221, 91),
)

print("\nPurchase orders and vendors (G14, G16)")
unique = {tuple(p.values()): p for p in pos}
check("G14 exact duplicate PO rows", len(pos) - len(unique), 2)
open_lines = [p for p in unique.values() if p["status"] == "Open"]
check("G14 open PO lines", len(open_lines), 14)
incoming: dict[str, Decimal] = defaultdict(Decimal)
for p in open_lines:
    incoming[canon(p["item_code"])] += Decimal(p["qty_ordered"]) - Decimal(p["qty_received"])
check(
    "G14 incoming SHR-2630 / HAD-LOIN / PAN-0709 / POL-BLK",
    tuple(incoming[c] for c in ["SHR-2630", "HAD-LOIN", "PAN-0709", "POL-BLK"]),
    (500, 200, 400, 18000),
)
check(
    "G16 BlueTide lead times (raw text)",
    {
        v["vendor_code"]: v["lead_time_days"]
        for v in vendors
        if v["vendor_code"] in {"BXE", "AFS", "DLC", "MNP", "ASP"}
    },
    {"BXE": "56", "AFS": "", "MNP": "14", "ASP": "28", "DLC": "2-3 wks"},
)

print(f"\n{'All facts match.' if failures == 0 else f'{failures} fact(s) did NOT match.'}")
sys.exit(1 if failures else 0)
