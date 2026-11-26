"""Read the BlueTide exports exactly as they are (strings only, nothing trimmed or guessed).

Why the standard-library csv module and not pandas (ADR-019)
    BUILD_PROMPT §16 warns that pandas silently "fixes" values (strips codes, turns blanks
    into NaN, drops leading zeros from UPCs) unless every option is set just right. The csv
    module never converts anything: every value stays the exact string BlueTide wrote, which
    is what the raw layer must keep. It also adds no dependency, so this loader could run
    inside the deployed API later (e.g. a nightly feed) without shipping pandas.

Key details
    - Files are CRLF; `newline=""` lets csv handle that (and quoted commas in addresses).
    - `utf-8-sig` tolerates a byte-order mark if a future export has one ("Austral Frío").
    - Line numbers are physical lines in the file, header = line 1, so a Data notes entry
      can say "bluetide_sales_lines.csv, line 4127" and you can open the file there.

How to change this: a new export file is one entry in RAW_FILES.
"""

from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path

from app.config.settings import REPO_ROOT
from app.loader.types import RawFile, RawRecord, SourceRef

RAW_DIR = REPO_ROOT / "data" / "raw"

# Logical name -> working-copy file name (ADR-017: copies of kestrel-bay/data/<name>.csv).
RAW_FILES: dict[str, str] = {
    "items": "bluetide_items.csv",
    "inventory_on_hand": "bluetide_inventory_on_hand.csv",
    "sales_lines": "bluetide_sales_lines.csv",
    "purchase_orders": "bluetide_purchase_orders.csv",
    "vendors": "bluetide_vendors.csv",
    "customers": "bluetide_customers.csv",
    "price_list": "bluetide_price_list.csv",
}


def row_hash(values: dict[str, str]) -> str:
    """SHA-256 of a row's values in column order. Identical rows hash identically (T24)."""
    joined = "\x1f".join(f"{k}\x1e{v}" for k, v in values.items())
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


# The columns each export must have (BlueTide's header row). An upload missing any of them is
# refused before anything is checked or loaded: a wrong file in a slot would otherwise read every
# missing column as "" and "load successfully", wiping good data (Phase 6 design review).
REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "items": ("item_code", "description", "category", "pack_size", "sell_uom", "vendor_code", "status"),
    "inventory_on_hand": ("snapshot_date", "item_code", "location", "lot_no", "qty", "uom", "expiry_date"),
    "sales_lines": ("order_no", "line_no", "order_date", "ship_date", "customer_code", "item_code", "qty",
                    "uom", "unit_price", "status"),
    "purchase_orders": ("po_no", "line_no", "vendor_code", "item_code", "order_date", "expected_date",
                        "qty_ordered", "qty_received", "uom", "status"),
    "vendors": ("vendor_code", "vendor_name", "country", "lead_time_days"),
    "customers": ("customer_code", "customer_name", "customer_type"),
    "price_list": ("item_code", "price_tier", "price", "uom"),
}  # fmt: skip


class RawFileError(ValueError):
    """A file that can't be one of the BlueTide exports (wrong columns, empty, not text)."""


def read_raw_bytes(content: bytes, file_name: str, logical_name: str, *, check: bool = False) -> RawFile:
    """Read one CSV (as bytes, e.g. an upload) into RawRecords without changing any value.

    `check=True` (uploads from the website) refuses a file without the export's columns, or with
    no rows. The laptop loader reads the known working copies and doesn't need it.
    """
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise RawFileError(f"{file_name} isn't a text CSV file (it couldn't be read as UTF-8).") from error
    reader = csv.DictReader(io.StringIO(text, newline=""))
    header = [h for h in (reader.fieldnames or []) if h]
    required = REQUIRED_COLUMNS.get(logical_name, ())
    missing = [c for c in required if c not in header]
    if check and missing:
        raise RawFileError(
            f"{file_name} doesn't look like BlueTide's {logical_name.replace('_', ' ')} export: "
            f"it has no {', '.join(missing)} column{'s' if len(missing) > 1 else ''}."
        )
    records: list[RawRecord] = []
    for row in reader:
        values = {key: (value if value is not None else "") for key, value in row.items() if key}
        records.append(
            RawRecord(
                source=SourceRef(file=file_name, line=reader.line_num), data=values, row_hash=row_hash(values)
            )
        )
    if check and not records:
        raise RawFileError(f"{file_name} has a header but no rows.")
    return RawFile(
        logical_name=logical_name,
        file_name=file_name,
        sha256=hashlib.sha256(content).hexdigest(),
        records=tuple(records),
    )


def read_raw_file(path: Path, logical_name: str) -> RawFile:
    """Read one CSV into RawRecords without changing a single character of any value."""
    return read_raw_bytes(path.read_bytes(), path.name, logical_name)


def read_all_raw(raw_dir: Path = RAW_DIR) -> dict[str, RawFile]:
    """Read every BlueTide export listed in RAW_FILES. Missing files raise FileNotFoundError."""
    return {name: read_raw_file(raw_dir / file_name, name) for name, file_name in RAW_FILES.items()}
