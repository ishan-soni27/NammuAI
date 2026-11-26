"""Read the human-maintained seeds in data/reference/ (see data/reference/README.md).

These files are typed by people, so mistakes are possible. Unlike BlueTide data (where we
log and carry on), a bad seed row stops the load with a message naming the file and line.
A silently ignored lead time would be worse than a failed load.

How to change this: a new seed file needs a dataclass in types.py, a reader here, and a
field on ReferenceData.
"""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.config.settings import REPO_ROOT
from app.loader.types import (
    ExcludedOrderSeed,
    LocationSeed,
    PackSize,
    ReferenceData,
    StockoutPeriodSeed,
    VendorSettingSeed,
)

REFERENCE_DIR = REPO_ROOT / "data" / "reference"


class ReferenceDataError(ValueError):
    """A seed file has a value we can't use. The message names the file and line."""


def _rows(path: Path) -> list[tuple[int, dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [(reader.line_num, {k: (v or "").strip() for k, v in row.items() if k}) for row in reader]


def _bool(value: str, where: str) -> bool:
    lowered = value.lower()
    if lowered in {"true", "yes", "1"}:
        return True
    if lowered in {"false", "no", "0"}:
        return False
    raise ReferenceDataError(f"{where}: expected true/false, got {value!r}")


def _int(value: str, where: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ReferenceDataError(f"{where}: expected a whole number, got {value!r}") from exc


def _date(value: str, where: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ReferenceDataError(f"{where}: expected a date like 2026-11-16, got {value!r}") from exc


def _decimal_or_none(value: str, where: str) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ReferenceDataError(f"{where}: expected a number, got {value!r}") from exc


def load_reference(ref_dir: Path = REFERENCE_DIR) -> ReferenceData:
    """Read all seed files into typed objects, failing loudly on any bad value."""

    def where(file: str, line: int) -> str:
        return f"data/reference/{file}, line {line}"

    pack_sizes: dict[str, PackSize] = {}
    for line, r in _rows(ref_dir / "pack_sizes.csv"):
        code = r["item_code"].upper()
        if code in pack_sizes:
            raise ReferenceDataError(f"{where('pack_sizes.csv', line)}: duplicate item {code}")
        pack_sizes[code] = PackSize(
            item_code=code,
            pack_size_raw=r["pack_size_raw"],
            lb_per_case=_decimal_or_none(r["lb_per_case"], where("pack_sizes.csv", line)),
            verified_by=r["verified_by"],
            note=r["note"],
        )

    vendor_settings = tuple(
        VendorSettingSeed(
            vendor_code=r["vendor_code"].upper(),
            lead_time_days=_int(r["lead_time_days"], where("vendor_settings_seed.csv", line)),
            safety_days=_int(r["safety_days"], where("vendor_settings_seed.csv", line)),
            order_cycle_days=_int(r["order_cycle_days"], where("vendor_settings_seed.csv", line)),
            source=r["source"],
            note=r["note"],
        )
        for line, r in _rows(ref_dir / "vendor_settings_seed.csv")
    )

    vendor_types = {
        r["vendor_code"].upper(): r["vendor_type"] for _, r in _rows(ref_dir / "vendor_types.csv")
    }

    locations = tuple(
        LocationSeed(
            code=r["code"],
            name=r["name"],
            is_sellable=_bool(r["is_sellable"], where("locations.csv", line)),
            is_third_party_storage=_bool(r["is_third_party_storage"], where("locations.csv", line)),
            may_return_to_stock=_bool(r["may_return_to_stock"], where("locations.csv", line)),
            description=r["description"],
        )
        for line, r in _rows(ref_dir / "locations.csv")
    )

    stockout_periods = []
    for line, r in _rows(ref_dir / "stockout_periods.csv"):
        start = _date(r["start_date"], where("stockout_periods.csv", line))
        end = _date(r["end_date"], where("stockout_periods.csv", line))
        if end < start:
            raise ReferenceDataError(f"{where('stockout_periods.csv', line)}: end_date is before start_date")
        stockout_periods.append(
            StockoutPeriodSeed(
                item_code=r["item_code"].upper(),
                start_date=start,
                end_date=end,
                source=r["source"],
                note=r["note"],
            )
        )

    excluded_orders = tuple(
        ExcludedOrderSeed(order_no=r["order_no"], reason=r["reason"], source=r["source"])
        for _, r in _rows(ref_dir / "excluded_orders.csv")
    )

    return ReferenceData(
        pack_sizes=pack_sizes,
        vendor_settings=vendor_settings,
        vendor_types=vendor_types,
        locations=locations,
        stockout_periods=tuple(stockout_periods),
        excluded_orders=excluded_orders,
    )


def reference_texts(ref_dir: Path = REFERENCE_DIR) -> dict[str, str]:
    """Every seed CSV's exact text (file name -> text), stored on each load run (ADR-029)."""
    return {path.name: path.read_text(encoding="utf-8") for path in sorted(ref_dir.glob("*.csv"))}


def load_reference_from_texts(texts: dict[str, str]) -> ReferenceData:
    """The same seeds, rebuilt from a load run's stored copy (for imports on the deployed API)."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        for name, text in texts.items():
            if "/" in name or "\\" in name or not name.endswith(".csv"):
                raise ReferenceDataError(f"Unexpected reference file name {name!r}")
            (Path(tmp) / name).write_text(text, encoding="utf-8")
        return load_reference(Path(tmp))
