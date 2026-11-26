"""On the way (ADR-032) through the API, on the real data: BlueTide's open PO lines, read only.

POs are created, shipped and received in BlueTide; the app shows its open lines with our arrival
date and lets Dana type a real one (the PO-date tests are in test_api_endpoints.py).
Each test gets a fresh copy of the loaded database (tests/api/conftest.py).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

V = "/api/v1"


def test_on_the_way_lists_every_open_bluetide_line_with_our_date_and_bluetides(
    api: TestClient, db_engine: Engine
) -> None:
    lines = api.get(f"{V}/purchase-orders").json()
    with db_engine.connect() as conn:
        open_lines = conn.execute(
            text(
                "SELECT count(*) FROM purchase_order_lines "
                "WHERE status = 'open' AND qty_remaining_sell_uom > 0"
            )
        ).scalar_one()
    assert len(lines) == open_lines  # every open BlueTide line, nothing invented
    by_po = {(x["po_no"], x["line_no"]): x for x in lines}
    shr = by_po[("PO-260443", 1)]
    assert (shr["item_code"], shr["qty"], shr["eta"], shr["bluetide_date"]) == (
        "SHR-1620",
        600,
        "2027-01-25",
        "2026-12-28",
    )
    assert shr["eta_source"] == "Real lead time" and shr["is_late"] is False
    late = [x for x in lines if x["is_late"]]
    assert {x["po_no"] for x in late} == {"PO-260376", "PO-260394", "PO-260407"}
    assert sum(x["qty"] for x in late) == 1500 and all(x["eta"] is None for x in late)
    assert lines[: len(late)] == late  # late first: they need Dana's date


def test_search_finds_lines_by_item_po_or_supplier(api: TestClient) -> None:
    by_item = api.get(f"{V}/purchase-orders", params={"q": "shr-1620"}).json()
    assert by_item and all(x["item_code"] == "SHR-1620" for x in by_item)
    assert [x["po_no"] for x in api.get(f"{V}/purchase-orders", params={"q": "po-260394"}).json()] == [
        "PO-260394"
    ]
    by_supplier = api.get(f"{V}/purchase-orders", params={"q": "bien xanh"}).json()
    assert by_supplier and all(x["vendor_name"] == "Bien Xanh Export Co." for x in by_supplier)


def test_a_real_date_moves_a_late_line_into_the_counted_ones(api: TestClient) -> None:
    r = api.patch(f"{V}/purchase-orders/PO-260394/lines/1", json={"eta": "2026-12-04"})
    assert r.status_code == 200, r.text
    line = next(x for x in api.get(f"{V}/purchase-orders").json() if x["po_no"] == "PO-260394")
    assert (line["eta"], line["is_late"], line["eta_source"]) == ("2026-12-04", False, "Set by Dana")


def test_the_cut_write_routes_are_gone(api: TestClient) -> None:
    # ADR-032: BlueTide owns POs, receipts, shipments and items; the app records no transactions.
    assert api.post(f"{V}/purchase-orders", json={}).status_code == 405
    assert api.get(f"{V}/purchase-orders/PO-260443").status_code == 404
    assert api.post(f"{V}/purchase-orders/PO-260443/lines/1/receive", json={}).status_code == 404
    assert api.get(f"{V}/shipments").status_code == 404
    assert api.post(f"{V}/stock-moves", json={}).status_code == 404
    assert api.get(f"{V}/locations").status_code == 404
    assert api.post(f"{V}/items", json={}).status_code == 405
    assert api.get(f"{V}/item-details").status_code == 404
    assert api.post(f"{V}/vendors", json={}).status_code == 405
    assert api.get(f"{V}/import-templates/items.csv").status_code == 404
