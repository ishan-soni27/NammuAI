"""Parsers (dates, numbers, lead times, pack sizes), conversion, and the reference seed files."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.loader.convert import cost_to_sell_uom, to_sell_uom
from app.loader.normalize import (
    canonical_code,
    parse_business_date,
    parse_decimal,
    parse_lead_time_days,
    parse_pack_size_lb,
)
from app.loader.read_raw import read_raw_file
from app.loader.reference import ReferenceDataError, load_reference


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("shr-1620 ", "SHR-1620"), ("Sal-Por6", "SAL-POR6"), ("COD-LOIN ", "COD-LOIN"), ("  zz-x ", "ZZ-X")],
)
def test_canonical_code(raw: str, expected: str) -> None:
    assert canonical_code(raw) == expected


def test_dates_iso_us_blank_and_bad() -> None:
    assert parse_business_date("2026-01-31") == (date(2026, 1, 31), "iso")
    assert parse_business_date("01/31/2026") == (date(2026, 1, 31), "us")
    assert parse_business_date("") == (None, "blank")
    with pytest.raises(ValueError):
        parse_business_date("31/01/2026")  # day-first is not a real month 31
    with pytest.raises(ValueError):
        parse_business_date("Jan 31")


def test_decimals_are_exact() -> None:
    assert parse_decimal("2789.6") == Decimal("2789.6")
    assert parse_decimal("-40.5") + parse_decimal("40.5") == 0  # no float drift
    assert parse_decimal("") is None
    with pytest.raises(ValueError):
        parse_decimal("n/a")


@pytest.mark.parametrize(
    ("raw", "days"),
    [("56", 56), ("", None), ("2-3 wks", 21), ("3 weeks", 21), ("10 days", 10), ("about a month", None)],
)
def test_lead_time_text(raw: str, days: int | None) -> None:
    assert parse_lead_time_days(raw)[0] == days


@pytest.mark.parametrize(
    ("raw", "pounds"),
    [
        ("6x2.2lb", "13.2"),
        ("5kg", "11.0231"),
        ("10 lb cs", "10"),
        ("10#", "10"),
        ("10/2#", "20"),
        ("5x2#", "10"),
        ("5 x 2 lb", "10"),
        ("15 lb case", "15"),
        ("16.5 lb block", "16.5"),
        ("30lb", "30"),
        ("10 LB CS", "10"),
        ("4x2.5lb", "10"),
        ("catch wt", None),
        ("per lb", None),
        ("", None),
    ],
)
def test_pack_size_parser_reads_every_format_in_the_export(raw: str, pounds: str | None) -> None:
    parsed = parse_pack_size_lb(raw)
    assert (parsed is None) if pounds is None else abs(parsed - Decimal(pounds)) < Decimal("0.0001")


def test_unit_conversion_both_directions() -> None:
    assert to_sell_uom(Decimal("132"), "LB", "CS", Decimal("13.2")) == 10
    assert to_sell_uom(Decimal("2"), "CS", "LB", Decimal("16.5")) == 33
    assert to_sell_uom(Decimal("5"), "CS", "CS", None) == 5
    assert to_sell_uom(Decimal("5"), "LB", "CS", None) is None
    assert cost_to_sell_uom(Decimal("2.71"), "LB", "CS", Decimal("13.2")) == Decimal("35.772")


def test_real_reference_seeds_load() -> None:
    ref = load_reference()
    assert len(ref.pack_sizes) == 45
    assert {s.vendor_code: s.lead_time_days for s in ref.vendor_settings} == {
        "BXE": 84,
        "AFS": 42,
        "MNP": 14,
        "ASP": 28,
        "DLC": 21,
    }
    qa = next(loc for loc in ref.locations if loc.code == "QA-HOLD")
    assert (qa.is_sellable, qa.may_return_to_stock) == (False, True)
    assert [o.order_no for o in ref.excluded_orders] == ["SO-245503"]
    assert [(s.item_code, str(s.start_date), str(s.end_date)) for s in ref.stockout_periods] == [
        ("SHR-1620", "2025-12-11", "2026-01-02")
    ]


def test_bad_seed_value_stops_the_load_with_file_and_line(tmp_path: Path) -> None:
    real = Path(__file__).resolve().parents[4] / "data" / "reference"
    for f in real.glob("*.csv"):
        (tmp_path / f.name).write_text(f.read_text())
    (tmp_path / "locations.csv").write_text(
        "code,name,is_sellable,is_third_party_storage,may_return_to_stock,description\nNB,New Bedford,maybe,false,false,x\n"
    )
    with pytest.raises(ReferenceDataError, match=r"locations.csv, line 2"):
        load_reference(tmp_path)


def test_raw_reader_keeps_values_exactly(tmp_path: Path) -> None:
    path = tmp_path / "bluetide_items.csv"
    path.write_bytes(b'item_code,upc,note\r\nshr-1620 ,012169722795,"a, b"\r\n')
    raw = read_raw_file(path, "items")
    record = raw.records[0]
    assert record.data == {
        "item_code": "shr-1620 ",
        "upc": "012169722795",
        "note": "a, b",
    }  # trailing space, leading 0
    assert record.source.line == 2
