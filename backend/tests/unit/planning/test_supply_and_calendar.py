"""Pure planning helpers added in Phase 2: on-hand breakdown (§6.1) and month arithmetic."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.planning.calendar import add_months
from app.planning.supply import LocationInput, LotInput, summarize_on_hand

AS_OF = date(2026, 11, 16)
LOCATIONS = [
    LocationInput("NB", True, False),
    LocationInput("HCS", True, False),
    LocationInput("QA-HOLD", False, True),
    LocationInput("DAMAGED", False, False),
]


def _lot(location: str, qty: str, expiry: date | None = date(2028, 1, 1), adj: bool = False) -> LotInput:
    return LotInput("X", location, "L", Decimal(qty), expiry, adj)


def test_on_hand_breakdown_never_adds_hold_damaged_or_expired() -> None:
    oh = summarize_on_hand(
        [
            _lot("NB", "100"),
            _lot("HCS", "50", expiry=date(2027, 3, 1)),  # inside six months: still sellable (T15)
            _lot("NB", "18", expiry=date(2026, 8, 30)),  # expired (T14)
            _lot("QA-HOLD", "80"),
            _lot("DAMAGED", "5"),
            _lot("NB", "-2", expiry=None, adj=True),  # adjustment (T13)
        ],
        LOCATIONS,
        AS_OF,
    )["X"]
    assert (oh.sellable, oh.on_hold, oh.damaged, oh.expired) == (148, 80, 5, 18)
    assert oh.sellable_by_location == {"NB": 98, "HCS": 50}


def test_expiry_on_as_of_day_still_counts() -> None:
    oh = summarize_on_hand([_lot("NB", "10", expiry=AS_OF)], LOCATIONS, AS_OF)["X"]
    assert oh.sellable == 10


def test_on_hold_toggle_for_the_qa_hold_what_if() -> None:
    oh = summarize_on_hand([_lot("QA-HOLD", "80")], LOCATIONS, AS_OF, count_on_hold_as_sellable=True)["X"]
    assert (oh.sellable, oh.on_hold) == (80, 0)


def test_unknown_location_and_unconverted_lots_are_not_counted() -> None:
    lots = [_lot("MYSTERY", "40"), LotInput("X", "NB", "L", None, None)]
    oh = summarize_on_hand(lots, LOCATIONS, AS_OF)["X"]
    assert oh.sellable == 0


def test_add_months() -> None:
    assert add_months(date(2026, 11, 16), 6) == date(2027, 5, 16)
    assert add_months(date(2026, 8, 31), 6) == date(2027, 2, 28)
    assert add_months(date(2027, 8, 31), 6) == date(2028, 2, 29)  # leap year (§16)
    assert add_months(date(2026, 12, 15), 1) == date(2027, 1, 15)
