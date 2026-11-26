"""Phase 6 step 1 through the API, on the real data: Dana's POs, receipts, items and suppliers.

Each test gets a fresh copy of the loaded database (tests/api/conftest.py).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

V = "/api/v1"


def _count(engine: Engine, sql: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(sql)).scalar_one())


def _card(api: TestClient, code: str) -> dict:
    return api.get(f"{V}/items/{code}").json()["card"]


def _po(api: TestClient, **kw) -> dict:
    body = {"vendor_code": "BXE", "lines": [{"item_code": "SHR-1620", "qty": 400}], **kw}
    r = api.post(f"{V}/purchase-orders", json=body)
    assert r.status_code == 201, r.text
    return r.json()


# ---- One list of POs ------------------------------------------------------------------------


def test_open_pos_list_bluetide_lines_with_their_arrival_dates(api: TestClient) -> None:
    pos = {p["po_no"]: p for p in api.get(f"{V}/purchase-orders").json()}
    shr = pos["PO-260443"]["lines"][0]
    assert shr["item_code"] == "SHR-1620" and shr["remaining"] == 600 and shr["eta"] == "2027-01-25"
    assert pos["PO-260394"]["status"] == "late" and pos["PO-260394"]["lines"][0]["eta"] is None
    assert all(p["source"] == "bluetide" for p in pos.values())
    assert api.get(f"{V}/purchase-orders", params={"status": "received"}).json()  # history is there


def test_search_finds_pos_by_item(api: TestClient) -> None:
    found = api.get(f"{V}/purchase-orders", params={"q": "shr-1620"}).json()
    assert found and all(any(x["item_code"] == "SHR-1620" for x in p["lines"]) for p in found)


# ---- Creating a PO (R1) -----------------------------------------------------------------------


def test_new_po_counts_as_on_the_way_and_is_audited(api: TestClient, db_engine: Engine) -> None:
    before = _card(api, "SHR-1620")
    po = _po(api, expected_date="2027-01-04", note="Called Linh")
    assert po["po_no"] == "KB-00001" and po["source"] == "app" and po["status"] == "open"
    line = po["lines"][0]
    assert line["eta"] == "2027-01-04" and line["eta_source"].startswith("Set by")
    assert line["unit_cost"] is not None  # defaulted from the last BlueTide cost
    after = _card(api, "SHR-1620")
    assert after["on_the_way"] == before["on_the_way"] + 400
    detail = api.get(f"{V}/items/SHR-1620").json()
    assert any(i["reference"] == "Your PO KB-00001 line 1" for i in detail["incoming"])
    assert _count(db_engine, "SELECT count(*) FROM audit_log WHERE action = 'purchase_order.create'") == 1
    assert _po(api)["po_no"] == "KB-00002"  # numbers keep counting


def test_new_po_expected_date_defaults_to_the_suppliers_lead_time(api: TestClient) -> None:
    po = _po(api)
    assert po["lines"][0]["eta"] == "2027-02-08"  # Nov 16 + 84 days (Bien Xanh, Dana's 12 weeks)


def test_new_po_clears_the_items_handled_note_so_it_isnt_counted_twice(api: TestClient) -> None:
    api.post(f"{V}/items/SHR-1620/handled", json={"qty": 400, "eta": "2027-01-04"})
    assert _card(api, "SHR-1620")["handled_note"] is not None
    _po(api, expected_date="2027-01-04")
    card = _card(api, "SHR-1620")
    assert card["handled_note"] is None
    assert card["on_the_way"] == 600 + 400  # PO-260443 plus the new PO, not plus the note too


def test_new_po_rejects_bad_input_in_plain_english(api: TestClient) -> None:
    cases = [
        ({"vendor_code": "NOPE", "lines": [{"item_code": "SHR-1620", "qty": 1}]}, 404, "supplier"),
        ({"vendor_code": "BXE", "lines": [{"item_code": "NOPE", "qty": 1}]}, 404, "item"),
        ({"vendor_code": "BXE", "lines": [{"item_code": "SHR-1620", "qty": 1}] * 2}, 422, "twice"),
        (
            {
                "vendor_code": "BXE",
                "expected_date": "2026-11-01",
                "lines": [{"item_code": "SHR-1620", "qty": 1}],
            },
            422,
            "already",
        ),
        (
            {
                "vendor_code": "BXE",
                "order_date": "2026-12-01",
                "lines": [{"item_code": "SHR-1620", "qty": 1}],
            },
            422,
            "after today",
        ),
    ]
    for body, status, words in cases:
        r = api.post(f"{V}/purchase-orders", json=body)
        assert r.status_code == status, (body, r.text)
        assert words in r.json()["error"]["message"]


# ---- Shipping, cancelling, reopening ----------------------------------------------------------


def test_ship_with_a_new_date_then_cancel_then_reopen(api: TestClient) -> None:
    _po(api, expected_date="2027-01-04")
    shipped = api.post(
        f"{V}/purchase-orders/KB-00001/lines/1/ship",
        json={"container_no": "MSCU1234567", "eta": "2027-01-11"},
    ).json()
    line = shipped["lines"][0]
    assert (
        line["status"] == "shipped" and line["container_no"] == "MSCU1234567" and line["eta"] == "2027-01-11"
    )
    assert shipped["status"] == "shipped"

    cancelled = api.post(
        f"{V}/purchase-orders/KB-00001/lines/1/cancel", json={"reason": "Price too high"}
    ).json()
    assert cancelled["status"] == "cancelled" and not cancelled["lines"][0]["counted"]
    assert _card(api, "SHR-1620")["on_the_way"] == 600  # only PO-260443 again

    reopened = api.delete(f"{V}/purchase-orders/KB-00001/lines/1/status").json()
    assert reopened["lines"][0]["status"] == "open" and reopened["lines"][0]["counted"]


def test_cancelling_a_bluetide_po_line_stops_counting_it(api: TestClient) -> None:
    r = api.post(f"{V}/purchase-orders/PO-260443/lines/1/cancel", json={"reason": "Supplier can't fill it"})
    assert r.status_code == 200
    assert _card(api, "SHR-1620")["on_the_way"] == 0


# ---- Receiving and undo (R3) ------------------------------------------------------------------


def _receive(api: TestClient, po: str = "KB-00001", **kw) -> dict:
    body = {"qty": 150, "location_code": "NB", "lot_no": "R-KB1-1", "expiry_date": "2028-11-01", **kw}
    return api.post(f"{V}/purchase-orders/{po}/lines/1/receive", json=body)


def test_receiving_adds_stock_reduces_on_the_way_and_can_be_undone(
    api: TestClient, db_engine: Engine
) -> None:
    _po(api, expected_date="2027-01-04")
    before = _card(api, "SHR-1620")
    r = _receive(api)
    assert r.status_code == 201, r.text
    line = r.json()["lines"][0]
    assert line["received"] == 150 and line["remaining"] == 250 and line["receipts"][0]["added_to_stock"]
    after = _card(api, "SHR-1620")
    assert after["sellable"] == before["sellable"] + 150
    assert after["on_the_way"] == before["on_the_way"] - 150 == 600 + 250
    lots = api.get(f"{V}/items/SHR-1620").json()["lots"]
    assert any(lot["lot_no"] == "R-KB1-1" and "Received in the app" in lot["reason"] for lot in lots)

    movement = line["receipts"][0]["movement_id"]
    assert api.post(f"{V}/stock-movements/{movement}/undo", json={"reason": "Wrong PO"}).status_code == 201
    assert _card(api, "SHR-1620")["sellable"] == before["sellable"]
    assert api.post(f"{V}/stock-movements/{movement}/undo", json={}).status_code == 409  # only once
    assert _count(db_engine, "SELECT count(*) FROM stock_movements") == 2  # the history stays


def test_receiving_into_hold_is_shown_on_hold_not_sellable(api: TestClient) -> None:
    _po(api, expected_date="2027-01-04")
    before = _card(api, "SHR-1620")
    assert _receive(api, location_code="QA-HOLD").status_code == 201
    after = _card(api, "SHR-1620")
    assert after["on_hold"] == before["on_hold"] + 150 and after["sellable"] == before["sellable"]


def test_receiving_against_a_bluetide_po_line(api: TestClient) -> None:
    assert _receive(api, po="PO-260443", qty=600).status_code == 201
    card = _card(api, "SHR-1620")
    assert card["on_the_way"] == 0 and card["sellable"] == 480 + 600


def test_receiving_rejects_bad_input_in_plain_english(api: TestClient) -> None:
    _po(api, expected_date="2027-01-04")
    cases = [
        ({"qty": 500}, 422, "still to come"),
        ({"location_code": "DAMAGED"}, 422, "can't be received"),
        ({"location_code": "XX"}, 404, "building"),
        ({"expiry_date": "2026-11-01"}, 422, "after the day it arrived"),
        ({"received_on": "2026-12-01"}, 422, "after today"),
    ]
    for extra, status, words in cases:
        r = _receive(api, **extra)
        assert r.status_code == status, (extra, r.text)
        assert words in r.json()["error"]["message"]
    assert _receive(api, qty=500, allow_over_receipt=True).status_code == 201


# ---- Items and suppliers of her own (independent of BlueTide) ---------------------------------


def test_new_supplier_and_item_can_be_ordered_and_planned(api: TestClient) -> None:
    supplier = api.post(
        f"{V}/vendors",
        json={"name": "Gloucester Fillet Co.", "country": "USA", "lead_time_days": 21, "cushion_days": 7},
    )
    assert supplier.status_code == 201, supplier.text
    code = supplier.json()["vendor_code"]
    assert code == "GFC" and supplier.json()["lead_time_days_bluetide"] is None
    assert any(v["vendor_code"] == "GFC" for v in api.get(f"{V}/vendors").json())

    item = api.post(
        f"{V}/items",
        json={
            "item_code": "kb-cod6",
            "description": "Cod loin 6 oz",
            "category": "cod",
            "sell_uom": "CS",
            "lb_per_case": 10,
            "vendor_code": "GFC",
        },
    )
    assert item.status_code == 201, item.text
    assert item.json()["item_code"] == "KB-COD6" and item.json()["category"] == "Cod"

    po = _po(api, vendor_code="GFC", lines=[{"item_code": "KB-COD6", "qty": 80, "unit_cost": 52.5}])
    assert po["lines"][0]["eta"] == "2026-12-07"  # 21 days
    card = _card(api, "KB-COD6")
    assert card["vendor_name"] == "Gloucester Fillet Co." and card["on_the_way"] == 80
    assert card["lifecycle_status"] == "active"


def test_item_and_supplier_validation(api: TestClient) -> None:
    dup = api.post(
        f"{V}/items",
        json={
            "item_code": "SHR-1620",
            "description": "x",
            "category": "Shrimp",
            "sell_uom": "LB",
            "vendor_code": "BXE",
        },
    )
    assert dup.status_code == 409
    no_lb = api.post(
        f"{V}/items",
        json={
            "item_code": "KB-1",
            "description": "x",
            "category": "Shrimp",
            "sell_uom": "CS",
            "vendor_code": "BXE",
        },
    )
    assert no_lb.status_code == 422 and "pounds" in no_lb.json()["error"]["message"]
    bad_days = api.post(f"{V}/vendors", json={"name": "Slow Co", "lead_time_days": 0, "cushion_days": 7})
    assert bad_days.status_code == 422


def test_editing_a_bluetide_item_stores_danas_copy(api: TestClient) -> None:
    r = api.patch(f"{V}/items/SHR-1620/details", json={"description": "White shrimp 16/20 EZ peel"})
    assert r.status_code == 200 and r.json()["source"] == "both"
    assert _card(api, "SHR-1620")["description"] == "White shrimp 16/20 EZ peel"
    details = {x["item_code"]: x for x in api.get(f"{V}/item-details").json()}
    assert details["SHR-1620"]["source"] == "both" and details["SHR-2125"]["source"] == "bluetide"


def test_dana_records_survive_and_the_plan_is_unchanged_without_them(api: TestClient) -> None:
    # No app records: the Monday numbers are exactly the pre-Phase 6 ones (regression).
    d = api.get(f"{V}/dashboard").json()
    assert d["summary"]["too_late"] == 3 and d["summary"]["order_this_week"] == 6
    assert d["summary"]["order_soon"] == 5 and d["summary"]["fine"] == 16


def test_locations_say_which_buildings_can_receive(api: TestClient) -> None:
    locs = {x["code"]: x for x in api.get(f"{V}/locations").json()}
    assert locs["NB"]["can_receive"] and locs["QA-HOLD"]["can_receive"] and not locs["DAMAGED"]["can_receive"]
    assert locs["HCS"]["is_third_party_storage"]
