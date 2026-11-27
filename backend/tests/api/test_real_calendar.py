"""Today is Boston's calendar date; the numbers stay honest as the count ages (ADR-034, Ishan 2026-11-26).

The data is BlueTide's count of Sun Nov 15. These tests move "today" to Fri Nov 27 (11 days later, no new
upload) with the AS_OF_DATE override, as if Dana opened the app that morning, and use the "view as of"
switch (X-As-Of, or ?as_of= on a download) to look at Mon Nov 16, the day after the count.
"""

from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient

from tests.conftest import clear_config_caches

V = "/api/v1"
NOV16 = {"X-As-Of": "2026-11-16"}


@pytest.fixture
def nov27(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AS_OF_DATE", "2026-11-27")
    clear_config_caches()


def _cards(d: dict) -> dict[str, dict]:
    return {i["item_code"]: i for i in d["order_items"] + d["fine_items"]}


def test_eleven_days_after_the_count_shr_2125_is_out_of_stock_and_orders_are_overdue(
    api: TestClient, nov27: None
) -> None:
    d = api.get(f"{V}/dashboard").json()
    assert (d["as_of"], d["data_snapshot_date"], d["data_date"], d["days_since_count"]) == (
        "2026-11-27",
        "2026-11-15",
        "2026-11-16",
        12,
    )
    cards = _cards(d)
    shr = cards["SHR-2125"]
    assert shr["status"] == "OUT_OF_STOCK" and shr["run_out_date"] == "2026-11-24"
    # Both counts (Ishan's choice 1): BlueTide's count, and the estimate for today.
    assert shr["sellable"] == 90 and shr["sellable_now"] == 0 and shr["count_date"] == "2026-11-15"
    had = cards["HAD-FIL"]
    assert had["status"] == "OVERDUE" and had["order_by_date"] == "2026-11-21" and had["days_overdue"] == 6
    assert had["sellable"] == 170 and 0 < had["sellable_now"] < 170
    s = d["summary"]
    assert (s["out_of_stock"], s["too_late"], s["overdue"]) == (1, 5, 7)
    assert s["sentences"][0].startswith("1 item is probably out of stock now.")
    assert "7 orders are overdue." in s["sentences"][0]
    statuses = [i["status"] for i in d["order_items"]]
    assert statuses[0] == "OUT_OF_STOCK"  # most urgent first


def test_viewing_as_of_nov_16_shows_the_day_after_the_count(api: TestClient, nov27: None) -> None:
    for d in (
        api.get(f"{V}/dashboard", headers=NOV16).json(),
        api.get(f"{V}/dashboard?as_of=2026-11-16").json(),
    ):
        assert (d["as_of"], d["data_date"], d["days_since_count"]) == ("2026-11-16", "2026-11-16", 1)
        s = d["summary"]
        assert (s["out_of_stock"], s["too_late"], s["overdue"]) == (0, 3, 1)  # LOB-MEAT: order by Nov 13
        assert (s["order_this_week"], s["order_soon"]) == (5, 5)
        shr = _cards(d)["SHR-2125"]
        assert shr["status"] == "TOO_LATE" and shr["sellable_now"] == 90 and shr["count_date"] is None


def test_the_item_page_bridges_the_count_and_today(api: TestClient, nov27: None) -> None:
    d = api.get(f"{V}/items/SHR-1620").json()
    rows = {r["key"]: r for r in d["breakdown"]}
    assert rows["at_count"]["qty"] == 480 and rows["at_count"]["date"] == "2026-11-15"
    assert rows["can_sell_now"]["qty"] == pytest.approx(480 - rows["sold_since"]["qty"], abs=0.5)
    assert d["projection"][0]["day"] == "2026-11-27"  # the chart starts today
    same_day = {r["key"]: r for r in api.get(f"{V}/items/SHR-1620", headers=NOV16).json()["breakdown"]}
    assert same_day["can_sell"]["qty"] == 480 and "at_count" not in same_day


@pytest.mark.parametrize("bad", ["2026-11-15", "2026-11-28", "2027-01-01"])
def test_a_view_date_outside_the_count_to_today_window_is_refused(
    api: TestClient, nov27: None, bad: str
) -> None:
    r = api.get(f"{V}/dashboard", headers={"X-As-Of": bad})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "view_date_out_of_range"
    assert "Mon Nov 16" in body["error"]["message"] and "Fri Nov 27" in body["error"]["message"]


def test_a_view_date_that_isnt_a_date_is_refused(api: TestClient) -> None:
    r = api.get(f"{V}/dashboard", headers={"X-As-Of": "next monday"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "bad_view_date"


def test_downloads_follow_the_view_date(api: TestClient, nov27: None) -> None:
    today = api.get(f"{V}/exports/order-list.csv")
    viewed = api.get(f"{V}/exports/order-list.csv?as_of=2026-11-16")
    assert "kestrel-bay-order-list-2026-11-27.csv" in today.headers["content-disposition"]
    assert "kestrel-bay-order-list-2026-11-16.csv" in viewed.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(today.content.decode("utf-8-sig"))))
    shr = next(r for r in rows if r["item_code"] == "SHR-2125")
    assert (shr["status"], shr["can_sell"], shr["can_sell_now_estimated"]) == (
        "Out of stock (estimated)",
        "90",
        "0",
    )
    assert rows[0]["status"] == "Out of stock (estimated)"
    old = list(csv.DictReader(io.StringIO(viewed.content.decode("utf-8-sig"))))
    assert next(r for r in old if r["item_code"] == "SHR-2125")["status"] == "Too late"


def test_a_po_due_since_the_last_upload_isnt_counted(api: TestClient, nov27: None) -> None:
    # PO-260444 (LOB-T810) is due Nov 27 by the real lead time: today, after the count. Not counted until
    # an upload shows it or Dana sets its date (Ishan's choice 2).
    lines = {(x["po_no"], x["line_no"]): x for x in api.get(f"{V}/purchase-orders").json()}
    line = lines[("PO-260444", 1)]
    assert line["is_late"] and line["eta"] is None and line["eta_source"] == "Due since your last upload"
    viewed = {(x["po_no"], x["line_no"]): x for x in api.get(f"{V}/purchase-orders", headers=NOV16).json()}
    assert viewed[("PO-260444", 1)]["eta"] == "2026-11-27" and not viewed[("PO-260444", 1)]["is_late"]


def test_edits_are_judged_against_the_view_date(api: TestClient, nov27: None) -> None:
    url = f"{V}/purchase-orders/PO-260394/lines/1"
    # Today (Nov 27), Nov 20 has passed.
    r = api.patch(url, json={"eta": "2026-11-20"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "date_in_past"
    # Viewing Nov 16 (the demo), it's still ahead, as it was on Nov 16.
    r = api.patch(url, json={"eta": "2026-11-20"}, headers=NOV16)
    assert r.status_code == 200, r.text
    # And back on today, that date has passed: it isn't counted.
    line = next(x for x in api.get(f"{V}/purchase-orders").json() if x["po_no"] == "PO-260394")
    assert line["eta"] is None and line["eta_source"] == "Your date has passed"


def test_health_reports_boston_today_and_how_old_the_count_is(api: TestClient, nov27: None) -> None:
    h = api.get(f"{V}/health").json()
    assert (h["as_of"], h["snapshot_date"], h["data_date"], h["days_since_count"]) == (
        "2026-11-27",
        "2026-11-15",
        "2026-11-16",
        12,
    )
    assert (h["stale_after_days"], h["very_stale_after_days"]) == (7, 14)


def test_a_handled_note_whose_date_has_passed_stops_counting_and_the_item_comes_back(
    api: TestClient, nov27: None
) -> None:
    # Written while viewing Nov 16 (the demo), arriving Nov 20. On Nov 27 that date has passed (A25).
    r = api.post(f"{V}/items/SHR-1620/handled", json={"qty": 400, "eta": "2026-11-20"}, headers=NOV16)
    assert r.status_code == 201, r.text
    then = api.get(f"{V}/dashboard", headers=NOV16).json()
    assert "SHR-1620" in {i["item_code"] for i in then["handled_items"]}
    now = api.get(f"{V}/dashboard").json()
    assert "SHR-1620" not in {i["item_code"] for i in now["handled_items"]}
    card = next(i for i in now["order_items"] if i["item_code"] == "SHR-1620")
    assert card["status"] == "TOO_LATE"  # its real status, not grey "Handled"
    assert card["handled_note"]["date_passed"] and not card["handled_note"]["counts_as_incoming"]
    detail = api.get(f"{V}/items/SHR-1620").json()
    assert not any(i["source"] == "handled_note" for i in detail["incoming"])
    assert detail["handled_notes"][0]["date_passed"]
