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


def read_raw_file(path: Path, logical_name: str) -> RawFile:
    """Read one CSV into RawRecords without changing a single character of any value."""
    content = path.read_bytes()
    records: list[RawRecord] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            values = {key: (value if value is not None else "") for key, value in row.items() if key}
            records.append(
                RawRecord(
                    source=SourceRef(file=path.name, line=reader.line_num),
                    data=values,
                    row_hash=row_hash(values),
                )
            )
    return RawFile(
        logical_name=logical_name,
        file_name=path.name,
        sha256=hashlib.sha256(content).hexdigest(),
        records=tuple(records),
    )


def read_all_raw(raw_dir: Path = RAW_DIR) -> dict[str, RawFile]:
    """Read every BlueTide export listed in RAW_FILES. Missing files raise FileNotFoundError."""
    return {name: read_raw_file(raw_dir / file_name, name) for name, file_name in RAW_FILES.items()}
