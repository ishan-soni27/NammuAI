"""Download to Excel (Phase 6 step 4), on the real data: each CSV opens cleanly and matches the screens."""

from __future__ import annotations

import csv
import io

from fastapi.testclient import TestClient

V = "/api/v1"


def _rows(api: TestClient, name: str) -> tuple[list[dict[str, str]], str]:
    r = api.get(f"{V}/exports/{name}.csv")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert f"kestrel-bay-{name}-2026-11-16.csv" in r.headers["content-disposition"]
    assert r.content.startswith(b"\xef\xbb\xbf")  # BOM: Excel reads UTF-8 correctly
    assert b"\r\n" in r.content
    return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")))), r.text


def test_order_list_has_every_item_with_her_words_and_plain_numbers(api: TestClient) -> None:
    rows, _ = _rows(api, "order-list")
    assert len(rows) == len(api.get(f"{V}/items").json())
    shr = next(r for r in rows if r["item_code"] == "SHR-1620")
    assert shr["status"] == "Too late" and shr["runs_out"] == "2026-12-14" and shr["unit"] == "cases"
    assert (
        shr["can_sell"] == "480" and shr["weeks_to_arrive"] == "12" and shr["promised_to_customers"] == "201"
    )
    assert rows[0]["status"] == "Too late"  # most urgent first


def test_stuck_list_has_one_row_per_lot_with_value_at_cost(api: TestClient) -> None:
    rows, _ = _rows(api, "stuck-list")
    stuck = api.get(f"{V}/dashboard").json()["stuck_items"]
    assert len(rows) == sum(len(s["lots"]) for s in stuck)
    sal = [r for r in rows if r["item_code"] == "SAL-POR6"]
    assert sum(float(r["quantity"]) for r in sal) == 1350
    assert sum(float(r["quantity"]) for r in sal if r["at_harbor"] == "yes") == 1050
    assert sal[0]["at_harbor"] == "yes"  # Harbor lots first


def test_purchase_orders_are_bluetides_open_lines_with_our_date_and_the_late_flag(api: TestClient) -> None:
    rows, _ = _rows(api, "purchase-orders")
    assert len(rows) == len(api.get(f"{V}/purchase-orders").json())
    shr = next(r for r in rows if r["po_no"] == "PO-260443")
    assert (shr["still_to_come"], shr["arrives"], shr["bluetide_date"], shr["late"]) == (
        "600",
        "2027-01-25",
        "2026-12-28",
        "no",
    )
    late = next(r for r in rows if r["po_no"] == "PO-260394")
    assert late["late"] == "yes" and late["arrives"] == "" and late["unit"] == "cases"


def test_data_notes_and_no_shipments_download(api: TestClient) -> None:
    notes, _ = _rows(api, "data-notes")
    assert len(notes) == api.get(f"{V}/data-issues/summary").json()["total"]
    assert {"file", "line", "problem", "what_we_did"} <= set(notes[0])
    assert api.get(f"{V}/exports/shipments.csv").status_code == 404  # cut (ADR-032)


def test_unknown_export_is_a_plain_404(api: TestClient) -> None:
    r = api.get(f"{V}/exports/nope.csv")
    assert r.status_code == 404 and "no download" in r.json()["error"]["message"]
