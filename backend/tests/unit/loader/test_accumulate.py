"""Sales history accumulates across weekly uploads (ADR-032, step 3): the pure merge."""

from __future__ import annotations

from datetime import date

from app.loader.accumulate import merge_sales, sales_key
from app.loader.types import RawFile, RawRecord, SourceRef

FILE = "bluetide_sales_lines.csv"


def _rec(
    order: str, line: str, status: str = "INVOICED", day: str = "2026-11-02", *, at: int = 2, origin=None
):
    data = {"order_no": order, "line_no": line, "order_date": day, "status": status, "qty": "5"}
    return RawRecord(SourceRef(FILE, at, origin), data, f"{order}-{line}-{status}")


def _file(*records: RawRecord) -> RawFile:
    return RawFile("sales_lines", FILE, "sha", tuple(records))


def test_the_key_is_order_and_line_as_bluetide_prints_them() -> None:
    assert sales_key(_rec(" so-250907 ", "01")) == sales_key(_rec("SO-250907", "1")) == ("SO-250907", "1")


def test_the_new_file_wins_and_older_lines_it_no_longer_lists_are_kept() -> None:
    history = _file(
        _rec("SO-1", "1", "OPEN", at=2, origin=4),
        _rec("SO-2", "1", day="2025-11-01", at=3, origin=4),  # older than this week's export
        _rec("SO-3", "1", at=4, origin=4),
    )
    upload = _file(
        _rec("SO-1", "1", "INVOICED", at=2),  # OPEN -> INVOICED: an update, never a duplicate
        _rec("SO-3", "1", at=3),  # same values, new line number
        _rec("SO-9", "1", day="2026-11-15", at=4),  # new
    )
    merged, stats = merge_sales(upload, history)
    keys = [sales_key(r) for r in merged.records]
    assert keys == [("SO-1", "1"), ("SO-3", "1"), ("SO-9", "1"), ("SO-2", "1")]
    assert (stats.new, stats.updated, stats.unchanged, stats.kept) == (1, 1, 1, 1)
    kept = merged.records[-1]
    assert kept.source == SourceRef(FILE, 3, 4)  # still traces to load #4's file, line 3
    assert merged.records[0].data["status"] == "INVOICED"
    assert stats.first_order_date == date(2025, 11, 1)
    assert round(stats.months_of_history(date(2026, 11, 15)), 1) == 12.5


def test_without_a_history_the_upload_is_the_whole_history() -> None:
    merged, stats = merge_sales(_file(_rec("SO-1", "1", day="10/01/2026")), None)
    assert len(merged.records) == 1 and (stats.new, stats.kept) == (1, 0)
    assert stats.first_order_date == date(2026, 10, 1)  # US dates too (T21)
    assert stats.months_of_history(date(2026, 11, 15)) < 12
