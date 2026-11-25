"""Supply side of the plan: what is on hand (and, in Phase 3, what is on the way).

BUILD_PROMPT §6.1 (sellable stock), §6.5/§6.6 (lead times; ETAs come in Phase 3).

Sellable stock, per item, in the item's selling unit, is the sum of lots in the latest
snapshot (the loader keeps only that one, T01) where:
  - the location is sellable (NB, PVD, HCS per data/reference/locations.csv, T11),
  - qty > 0 (zero lots are skipped by the loader, T12),
  - the lot is not expired: expiry_date >= AS_OF (T14). Lots inside the six-month line
    still count, because Dana discounts them rather than binning them (T15),
PLUS negative adjustment lines (T13, conservative: they reduce stock) which have no expiry.

Shown separately and NEVER added in (Walt 00:04:40, "If I can't sell it, it isn't inventory"):
  - on_hold:  not-sellable locations that may return to stock (QA-HOLD),
  - damaged:  other not-sellable locations (DAMAGED),
  - expired:  sellable locations, but past expiry.

Whether an item is planned at all (lifecycle active) is decided by the caller, so the
same numbers serve both "what to order" (active items) and "what you're stuck with" (all).

How to change this ("count QA-HOLD as available", BUILD_PROMPT §17): pass
`count_on_hold_as_sellable=True` to `summarize_on_hand`, or flip is_sellable for QA-HOLD in
data/reference/locations.csv and reload.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

ZERO = Decimal(0)


@dataclass(frozen=True)
class LotInput:
    """One on-hand lot, already converted to the item's selling unit by the loader (T10)."""

    item_code: str
    location_code: str
    lot_no: str
    qty: Decimal | None  # None = no conversion factor; never counted (logged by the loader)
    expiry_date: date | None
    is_adjustment: bool = False


@dataclass(frozen=True)
class LocationInput:
    code: str
    is_sellable: bool
    may_return_to_stock: bool


@dataclass
class OnHand:
    """Per-item on-hand breakdown. Only `sellable` is used for run-out."""

    sellable: Decimal = ZERO
    on_hold: Decimal = ZERO
    damaged: Decimal = ZERO
    expired: Decimal = ZERO
    sellable_by_location: dict[str, Decimal] = field(default_factory=dict)


def summarize_on_hand(
    lots: list[LotInput],
    locations: list[LocationInput],
    as_of: date,
    *,
    count_on_hold_as_sellable: bool = False,
) -> dict[str, OnHand]:
    """Split every lot into sellable / on hold / damaged / expired, per item.

    Example: SHR-1620 on Nov 15 has NB 260 + HCS 140 + PVD 80 (sellable, 480) and
    QA-HOLD 80 (on_hold), so OnHand(sellable=480, on_hold=80) (golden fact G04).
    A lot at an unknown location is treated as not sellable (conservative).
    """
    by_code = {loc.code: loc for loc in locations}
    result: dict[str, OnHand] = defaultdict(OnHand)

    for lot in lots:
        if lot.qty is None:
            continue  # unconvertible quantity: excluded and logged by the loader (T10)
        summary = result[lot.item_code]
        location = by_code.get(lot.location_code)
        sellable_location = bool(location and location.is_sellable)
        may_return = bool(location and location.may_return_to_stock)

        if not sellable_location:
            if may_return and count_on_hold_as_sellable:
                _add_sellable(summary, lot)
            elif may_return:
                summary.on_hold += lot.qty  # T11: QA-HOLD, "sometimes it passes and comes back"
            else:
                summary.damaged += lot.qty  # T11: DAMAGED, written off eventually
            continue

        if lot.is_adjustment:
            _add_sellable(summary, lot)  # T13: negative ADJ lines net against sellable
        elif lot.expiry_date is not None and lot.expiry_date < as_of:
            summary.expired += lot.qty  # T14: past expiry, a write-off
        elif lot.qty > 0:
            _add_sellable(summary, lot)

    return dict(result)


def _add_sellable(summary: OnHand, lot: LotInput) -> None:
    assert lot.qty is not None
    summary.sellable += lot.qty
    summary.sellable_by_location[lot.location_code] = (
        summary.sellable_by_location.get(lot.location_code, ZERO) + lot.qty
    )


def effective_lead_time_days(
    dana_days: int | None, bluetide_days: int | None, default_days: int
) -> tuple[int, str]:
    """The lead time the plan uses, and where it came from (T27, §6.5).

    Dana's number wins (she knows the real lead times, 00:02:25), then BlueTide's, then the
    fallback default (which should never be needed for a seeded vendor).
    Example: effective_lead_time_days(84, 56, 28) -> (84, "Dana")
    """
    if dana_days is not None:
        return dana_days, "Dana"
    if bluetide_days is not None:
        return bluetide_days, "BlueTide"
    return default_days, "default"
