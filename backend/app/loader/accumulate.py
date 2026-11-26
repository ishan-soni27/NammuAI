"""Sales history accumulates across weekly uploads (ADR-032, step 3). Pure: no database, no clock.

BlueTide's sales export may hold only recent weeks, but the selling rate needs 8 weeks and the
season pattern needs a year. So each load merges the uploaded sales file with the sales lines the
previous load kept, keyed by order number + line number:
  - a line in the new file wins (OPEN -> INVOICED or CANCELLED is an update, never a duplicate);
  - an older line the new file no longer lists is kept, with the load it first came from
    (SourceRef.origin), so it still traces to that upload's file and line;
  - then the normal loader rules (T16-T23) run on the merged rows.

How to change this: the key is `sales_key` (order and line, normalized like BlueTide prints them).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.loader.normalize import parse_business_date
from app.loader.types import RawFile, RawRecord

DAYS_PER_MONTH = 365.25 / 12


def sales_key(record: RawRecord) -> tuple[str, str]:
    """('SO-250907', '1'): order number trimmed and upper-cased, line number trimmed (leading zeros off)."""
    order = " ".join(record.get("order_no").split()).upper()
    line = record.get("line_no").strip()
    return order, line.lstrip("0") or line


@dataclass(frozen=True)
class SalesMerge:
    """What merging this week's sales file with the history did (shown in the import check)."""

    new: int  # lines not seen before
    updated: int  # same order + line, different values (e.g. OPEN -> INVOICED)
    unchanged: int
    kept: int  # older lines the new file no longer lists, carried over
    first_order_date: date | None  # the oldest order in the merged history

    def months_of_history(self, snapshot: date) -> float:
        if self.first_order_date is None:
            return 0.0
        return (snapshot - self.first_order_date).days / DAYS_PER_MONTH


def _order_date(record: RawRecord) -> date | None:
    try:
        return parse_business_date(record.get("order_date").strip())[0]
    except ValueError:  # a bad date is the loader's problem (logged there); it just doesn't count here
        return None


def _first_order_date(records: tuple[RawRecord, ...]) -> date | None:
    dates = [d for d in (_order_date(r) for r in records) if d]
    return min(dates) if dates else None


def merge_sales(new: RawFile, previous: RawFile | None) -> tuple[RawFile, SalesMerge]:
    """The new file's lines, then the previous history's lines it doesn't list (see module docstring)."""
    if previous is None:
        return new, SalesMerge(len(new.records), 0, 0, 0, _first_order_date(new.records))
    before = {sales_key(r): r for r in previous.records}
    new_keys = set()
    added = updated = unchanged = 0
    for r in new.records:
        key = sales_key(r)
        new_keys.add(key)
        old = before.get(key)
        if old is None:
            added += 1
        elif old.data == r.data:
            unchanged += 1
        else:
            updated += 1
    kept = tuple(r for r in previous.records if sales_key(r) not in new_keys)
    records = new.records + kept
    merged = RawFile(new.logical_name, new.file_name, new.sha256, records)
    return merged, SalesMerge(added, updated, unchanged, len(kept), _first_order_date(records))
