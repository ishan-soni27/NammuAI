"""Harbor storage cost rule (P1 #1; ADR-031, A47): pallets per lot, part pallets charged whole."""

from __future__ import annotations

from datetime import date

import pytest

from app.planning.storage import monthly_cost, pallets_needed, storage_lines, to_cases
from app.planning.types import ItemInput, LocationInput, LotInput

RATE = 30.0
LOCATIONS = (
    LocationInput("NB", is_sellable=True, may_return_to_stock=False),
    LocationInput("HCS", is_sellable=True, may_return_to_stock=False, is_third_party_storage=True),
)


def _item(code: str, uom: str = "CS", lb_per_case: float | None = None) -> ItemInput:
    return ItemInput(code, code, "SALMON", uom, lb_per_case, "V1", "active", "")


def _lot(code: str, qty: float | None, loc: str = "HCS", lot: str = "L1") -> LotInput:
    return LotInput(code, loc, lot, qty, date(2027, 6, 1))


def test_a47_each_lot_rounds_up_to_whole_pallets_on_its_own() -> None:
    # 600 and 450 cases at 60 a pallet: 10 + 8 (7.5 rounded up), not 1,050 / 60 = 17.5 -> 18 by coincidence
    assert pallets_needed([600, 450], 60) == 18
    assert pallets_needed([61, 61], 60) == 4  # two part-full second pallets, each charged
    assert pallets_needed([120], 60) == 2  # exact: no extra pallet from float rounding
    assert pallets_needed([0, 30], 60) == 1  # an empty lot takes no pallet


def test_cost_is_pallets_times_the_rate() -> None:
    assert monthly_cost(18, RATE) == 540.0


def test_cases_per_pallet_must_be_positive() -> None:
    with pytest.raises(ValueError):
        pallets_needed([10], 0)


def test_only_paid_storage_counts_and_no_cost_without_cases_per_pallet() -> None:
    items = [_item("SAL-POR6"), _item("TIL-FIL")]
    lots = [
        _lot("SAL-POR6", 600, lot="A"),
        _lot("SAL-POR6", 450, lot="B"),
        _lot("SAL-POR6", 99, loc="NB"),  # New Bedford is ours: no storage charge
        _lot("TIL-FIL", 140),
    ]
    lines = storage_lines(lots, LOCATIONS, items, {"SAL-POR6": 60}, RATE)
    sal, til = lines  # priced first
    assert (sal.item_code, sal.cases, len(sal.lots), sal.pallets, sal.cost_per_month) == (
        "SAL-POR6",
        1050,
        2,
        18,
        540,
    )
    assert (til.item_code, til.cases, til.pallets, til.cost_per_month) == (
        "TIL-FIL",
        140,
        None,
        None,
    )  # never guessed


def test_pounds_become_cases_with_pounds_per_case_or_are_reported() -> None:
    items = [_item("CRAB-MEAT", "LB", 10.0), _item("LOB-MEAT", "LB", None)]
    assert to_cases(250, items[0]) == 25
    assert to_cases(250, items[1]) is None
    lines = storage_lines(
        [_lot("CRAB-MEAT", 250), _lot("LOB-MEAT", 40)], LOCATIONS, items, {"CRAB-MEAT": 20}, RATE
    )
    crab = next(x for x in lines if x.item_code == "CRAB-MEAT")
    lob = next(x for x in lines if x.item_code == "LOB-MEAT")
    assert (crab.cases, crab.pallets) == (25, 2)
    assert (lob.lots, lob.unconverted_lots) == ((), 1)
