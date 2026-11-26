"""Phase 6 step 2 through the API, on the real data: orders going out, picks, and moving stock.

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


def _customer(api: TestClient, name: str = "Seabright Markets") -> str:
    return next(c["customer_code"] for c in api.get(f"{V}/customers").json() if c["name"] == name)


def _order(api: TestClient, **kw) -> dict:
    body = {
        "customer_code": _customer(api),
        "location_code": "NB",
        "ship_date": "2026-11-20",
        "lines": [{"item_code": "SHR-1620", "qty": 40, "unit_price": 180}],
        **kw,
    }
    r = api.post(f"{V}/shipments", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _nb_stock(api: TestClient, code: str = "SHR-1620") -> float:
    return sum(
        x["qty"]
        for x in api.get(f"{V}/stock-lots", params={"item": code}).json()
        if x["location_code"] == "NB"
    )


# ---- Customers --------------------------------------------------------------------------------


def test_customers_list_bluetides_and_dana_can_add_one(api: TestClient) -> None:
    assert any(c["source"] == "bluetide" for c in api.get(f"{V}/customers").json())
    r = api.post(f"{V}/customers", json={"name": "Harbor Light Bistro", "customer_type": "restaurant"})
    assert r.status_code == 201 and r.json()["customer_type"] == "RESTAURANT" and r.json()["source"] == "app"
    internal = api.post(f"{V}/customers", json={"name": "Our PVD building", "customer_type": "INTERNAL"})
    assert internal.status_code == 422 and "Move stock" in internal.json()["error"]["message"]


# ---- An order: promised, shipped, undone, cancelled ---------------------------------------------


def test_open_order_is_promised_on_its_ship_date(api: TestClient, db_engine: Engine) -> None:
    before = _card(api, "SHR-1620")["promised_to_customers"]
    order = _order(api)
    assert order["order_no"] == "SH-00001" and order["status"] == "open" and order["lines"][0]["promised"]
    assert _card(api, "SHR-1620")["promised_to_customers"] == before + 40
    assert _count(db_engine, "SELECT count(*) FROM audit_log WHERE action = 'shipment.create'") == 1


def test_ship_takes_the_soonest_to_expire_lots_and_can_be_undone(api: TestClient) -> None:
    _order(api)
    stock, promised = _nb_stock(api), _card(api, "SHR-1620")["promised_to_customers"]
    plan = api.get(f"{V}/shipments/SH-00001/picks").json()
    assert plan["short"] == {} and sum(p["qty"] for p in plan["picks"]) == 40
    expiries = [p["expiry_date"] for p in plan["picks"]]
    assert expiries == sorted(expiries)

    shipped = api.post(f"{V}/shipments/SH-00001/ship", json={}).json()
    line = shipped["lines"][0]
    assert shipped["status"] == "shipped" and line["taken_from_stock"] and line["counts_as_demand"]
    assert sum(p["qty"] for p in line["picks"]) == 40
    assert _nb_stock(api) == stock - 40
    assert _card(api, "SHR-1620")["promised_to_customers"] == promised - 40  # not promised any more
    lots = api.get(f"{V}/items/SHR-1620").json()["lots"]
    assert any("Changed in the app" in lot["reason"] for lot in lots)

    undone = api.post(f"{V}/shipments/SH-00001/undo-ship", json={"reason": "Truck didn't come"}).json()
    assert undone["status"] == "open" and _nb_stock(api) == stock
    assert _card(api, "SHR-1620")["promised_to_customers"] == promised


def test_cancel_stops_the_promise(api: TestClient) -> None:
    before = _card(api, "SHR-1620")["promised_to_customers"]
    _order(api)
    r = api.post(f"{V}/shipments/SH-00001/cancel", json={"reason": "Customer called"})
    assert r.json()["status"] == "cancelled"
    assert _card(api, "SHR-1620")["promised_to_customers"] == before
    assert api.post(f"{V}/shipments/SH-00001/ship", json={}).status_code == 409


def test_shipping_more_than_the_building_has_is_refused(api: TestClient) -> None:
    _order(api, lines=[{"item_code": "SHR-1620", "qty": 5000}])
    r = api.post(f"{V}/shipments/SH-00001/ship", json={})
    assert r.status_code == 422 and "short" in r.json()["error"]["message"]


def test_chosen_picks_must_add_up_and_exist(api: TestClient) -> None:
    _order(api)
    lot = next(
        x
        for x in api.get(f"{V}/stock-lots", params={"item": "SHR-1620"}).json()
        if x["location_code"] == "NB"
    )
    bad_total = api.post(
        f"{V}/shipments/SH-00001/ship", json={"picks": [{"line_no": 1, "lot_no": lot["lot_no"], "qty": 10}]}
    )
    assert bad_total.status_code == 422 and "add up" in bad_total.json()["error"]["message"]
    no_lot = api.post(
        f"{V}/shipments/SH-00001/ship", json={"picks": [{"line_no": 1, "lot_no": "NOPE", "qty": 40}]}
    )
    assert no_lot.status_code == 422
    ok = api.post(
        f"{V}/shipments/SH-00001/ship", json={"picks": [{"line_no": 1, "lot_no": lot["lot_no"], "qty": 40}]}
    )
    assert ok.status_code == 200 and ok.json()["lines"][0]["picks"][0]["lot_no"] == lot["lot_no"]


def test_a_sample_takes_stock_but_is_not_demand(api: TestClient) -> None:
    stock = _nb_stock(api)
    _order(api, kind="sample", lines=[{"item_code": "SHR-1620", "qty": 2}])
    line = api.post(f"{V}/shipments/SH-00001/ship", json={}).json()["lines"][0]
    assert line["taken_from_stock"] and not line["counts_as_demand"] and _nb_stock(api) == stock - 2


def test_order_validation_in_plain_english(api: TestClient) -> None:
    good = {
        "customer_code": _customer(api),
        "location_code": "NB",
        "lines": [{"item_code": "SHR-1620", "qty": 1}],
    }
    cases = [
        ({**good, "customer_code": "NOPE"}, 404, "customer"),
        ({**good, "location_code": "QA-HOLD"}, 422, "sellable"),
        ({**good, "lines": [{"item_code": "NOPE", "qty": 1}]}, 404, "item"),
        ({**good, "order_date": "2026-12-01"}, 422, "after today"),
        ({**good, "ship_date": "2026-11-01"}, 422, "before the order date"),
    ]
    for body, status, words in cases:
        r = api.post(f"{V}/shipments", json=body)
        assert r.status_code == status, (body, r.text)
        assert words in r.json()["error"]["message"]


# ---- Matching BlueTide's orders (R7, R8) ------------------------------------------------------


def test_r8_the_same_open_order_in_both_is_promised_once(api: TestClient) -> None:
    before = _card(api, "SHR-1620")["promised_to_customers"]
    detail = api.get(f"{V}/items/SHR-1620").json()
    bt = detail["promised"][0]  # a BlueTide open order for this item
    _order(api, order_no=bt["order_no"], lines=[{"item_code": "SHR-1620", "qty": bt["qty"]}])
    assert _card(api, "SHR-1620")["promised_to_customers"] == before


def test_r7_an_order_bluetide_shows_invoiced_is_not_promised_again(
    api: TestClient, db_engine: Engine
) -> None:
    with db_engine.connect() as conn:
        order_no = conn.execute(
            text(
                "SELECT order_no FROM sales_lines WHERE item_code = 'SHR-1620' AND status = 'INVOICED' LIMIT 1"
            )
        ).scalar_one()
    before = _card(api, "SHR-1620")["promised_to_customers"]
    order = _order(api, order_no=order_no)
    assert _card(api, "SHR-1620")["promised_to_customers"] == before
    assert any("invoiced" in f for f in order["lines"][0]["flags"])


# ---- Moving stock ------------------------------------------------------------------------------


def _harbor_lot(api: TestClient, code: str = "SAL-POR6") -> dict:
    return next(x for x in api.get(f"{V}/stock-lots", params={"item": code}).json() if x["at_harbor"])


def test_moving_stock_out_of_harbor_and_undo(api: TestClient) -> None:
    lot = _harbor_lot(api)
    stuck = {x["item_code"]: x for x in api.get(f"{V}/dashboard").json()["stuck_items"]}
    at_harbor = stuck["SAL-POR6"]["qty_at_harbor"]
    r = api.post(
        f"{V}/stock-moves",
        json={
            "item_code": "SAL-POR6",
            "from_location": "HCS",
            "lot_no": lot["lot_no"],
            "to_location": "NB",
            "qty": 100,
        },
    )
    assert r.status_code == 201, r.text
    out_id = r.json()[0]["id"]
    stuck = {x["item_code"]: x for x in api.get(f"{V}/dashboard").json()["stuck_items"]}
    assert stuck["SAL-POR6"]["qty_at_harbor"] == at_harbor - 100
    lots = api.get(f"{V}/stock-lots", params={"item": "SAL-POR6"}).json()
    assert any(x["location_code"] == "NB" and x["lot_no"] == lot["lot_no"] and x["qty"] == 100 for x in lots)

    assert api.post(f"{V}/stock-movements/{out_id}/undo", json={}).status_code == 201  # both halves
    stuck = {x["item_code"]: x for x in api.get(f"{V}/dashboard").json()["stuck_items"]}
    assert stuck["SAL-POR6"]["qty_at_harbor"] == at_harbor


def test_move_validation(api: TestClient) -> None:
    lot = _harbor_lot(api)
    base = {"item_code": "SAL-POR6", "from_location": "HCS", "lot_no": lot["lot_no"], "to_location": "NB"}
    assert api.post(f"{V}/stock-moves", json={**base, "qty": lot["qty"] + 1}).status_code == 422
    assert api.post(f"{V}/stock-moves", json={**base, "to_location": "HCS", "qty": 1}).status_code == 422
    before_count = api.post(f"{V}/stock-moves", json={**base, "qty": 1, "moved_on": "2026-11-15"})
    assert before_count.status_code == 422 and "stock count" in before_count.json()["error"]["message"]


def test_a_shipment_pick_is_undone_with_the_order_not_on_its_own(api: TestClient, db_engine: Engine) -> None:
    _order(api)
    api.post(f"{V}/shipments/SH-00001/ship", json={})
    with db_engine.connect() as conn:
        pick = conn.execute(
            text("SELECT id FROM stock_movements WHERE shipment_id IS NOT NULL LIMIT 1")
        ).scalar_one()
    r = api.post(f"{V}/stock-movements/{pick}/undo", json={})
    assert r.status_code == 409 and "Undo shipped" in r.json()["error"]["message"]


def test_no_records_means_the_monday_numbers_are_unchanged(api: TestClient) -> None:
    s = api.get(f"{V}/dashboard").json()["summary"]
    assert (s["too_late"], s["order_this_week"], s["order_soon"], s["fine"]) == (3, 6, 5, 16)


def test_stock_changes_list_says_what_can_be_undone(api: TestClient) -> None:
    lot = _harbor_lot(api)
    api.post(
        f"{V}/stock-moves",
        json={
            "item_code": "SAL-POR6",
            "from_location": "HCS",
            "lot_no": lot["lot_no"],
            "to_location": "NB",
            "qty": 10,
        },
    )
    changes = api.get(f"{V}/stock-movements", params={"item": "SAL-POR6"}).json()
    kinds = {c["kind"]: c for c in changes}
    assert (
        kinds["move_out"]["can_undo"] and not kinds["move_in"]["can_undo"]
    )  # undo the move from its "out" half
    api.post(f"{V}/stock-movements/{kinds['move_out']['id']}/undo", json={})
    after = api.get(f"{V}/stock-movements", params={"item": "SAL-POR6"}).json()
    assert all(not c["can_undo"] for c in after) and sum(c["is_undo"] for c in after) == 2
