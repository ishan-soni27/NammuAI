"""Harbor storage cost (P1 #1; ADR-031): pallets and dollars a month for stock in a paid warehouse.

Pure: no database, clock or I/O. The rules (A47):
  - each lot sits on its own pallets (lots aren't mixed on a pallet: traceability, and picking
    the soonest to expire first);
  - a part pallet is charged as a whole one (Harbor charges per pallet);
  - cases per pallet is Dana's number for the item. Without it there is no cost: it's never guessed.
Quantities come in the item's selling unit; pounds become cases with the item's pounds per case.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from app.planning.types import ItemInput, LocationInput, LotInput

# Quantities are floats made from exact decimals: 120 / 60 must be 2 pallets, not 3.
_ROUND = 6


@dataclass(frozen=True)
class StorageLot:
    lot_no: str
    location_code: str
    cases: float
    expiry_date: date | None


@dataclass(frozen=True)
class StorageLine:
    """One item's stock in paid storage, and what it costs a month once cases per pallet is known."""

    item_code: str
    lots: tuple[StorageLot, ...]
    cases: float
    cases_per_pallet: int | None
    pallets: int | None
    cost_per_month: float | None
    unconverted_lots: int = 0  # lots in pounds with no pounds per case: can't be put on pallets


def pallets_needed(cases_per_lot: Iterable[float], cases_per_pallet: int) -> int:
    """Pallets for these lots: each lot rounded up to whole pallets on its own (A47)."""
    if cases_per_pallet <= 0:
        raise ValueError("cases per pallet must be positive")
    return sum(math.ceil(round(c / cases_per_pallet, _ROUND)) for c in cases_per_lot if c > 0)


def monthly_cost(pallets: int, rate_per_pallet_month: float) -> float:
    return round(pallets * rate_per_pallet_month, 2)


def to_cases(qty: float, item: ItemInput) -> float | None:
    """A quantity in the item's selling unit, as cases (None: sold by the pound, pounds per case unknown)."""
    if item.sell_uom.upper() == "CS":
        return qty
    if item.lb_per_case:
        return qty / item.lb_per_case
    return None


def storage_lines(
    lots: Sequence[LotInput],
    locations: Sequence[LocationInput],
    items: Sequence[ItemInput],
    cases_per_pallet: Mapping[str, int],
    rate_per_pallet_month: float,
) -> list[StorageLine]:
    """Every item with stock in a paid warehouse, most expensive first, then the most cases."""
    paid = {loc.code for loc in locations if loc.is_third_party_storage}
    by_code = {i.item_code: i for i in items}
    found: dict[str, list[StorageLot]] = defaultdict(list)
    unconverted: dict[str, int] = defaultdict(int)
    for lot in lots:
        item = by_code.get(lot.item_code)
        if lot.location_code not in paid or item is None or lot.qty is None or lot.qty <= 0:
            continue
        cases = to_cases(lot.qty, item)
        if cases is None:
            unconverted[lot.item_code] += 1
            continue
        found[lot.item_code].append(StorageLot(lot.lot_no, lot.location_code, cases, lot.expiry_date))
    lines = []
    for code in sorted(found.keys() | unconverted.keys()):
        item_lots = tuple(sorted(found[code], key=lambda x: (x.expiry_date or date.max, x.lot_no)))
        per = cases_per_pallet.get(code)
        pallets = pallets_needed((x.cases for x in item_lots), per) if per else None
        lines.append(
            StorageLine(
                item_code=code,
                lots=item_lots,
                cases=sum(x.cases for x in item_lots),
                cases_per_pallet=per,
                pallets=pallets,
                cost_per_month=monthly_cost(pallets, rate_per_pallet_month) if pallets is not None else None,
                unconverted_lots=unconverted[code],
            )
        )
    lines.sort(key=lambda x: (-(x.cost_per_month or 0), -x.cases))
    return lines
