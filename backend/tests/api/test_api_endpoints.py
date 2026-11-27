"""API tests on the real data (loaded into SQLite by the real loader writer; see tests/api/conftest.py).

Each test gets its own copy of the loaded database, so edits never leak between tests.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.db.models import CLEAN_LAYER
from app.loader.write import CLEAN_LAYER_INSERT_ORDER

V = "/api/v1"


def _count(engine: Engine, sql: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(sql)).scalar_one())


# ---- Reads: the Monday screen and the drill-down ------------------------------------------------


def test_dashboard_answers_both_questions(api: TestClient) -> None:
    d = api.get(f"{V}/dashboard").json()
    assert d["as_of"] == "2026-11-16" and d["data_snapshot_date"] == "2026-11-15"
    order = {i["item_code"]: i for i in d["order_items"]}
    shr = order["SHR-1620"]
    assert shr["status"] == "TOO_LATE" and shr["run_out_date"] == "2026-12-14"
    assert shr["new_order_arrival"] == "2027-02-08" and shr["back_in_stock_date"] == "2027-01-25"
    assert shr["sellable"] == 480 and shr["on_hold"] == 80 and shr["promised_to_customers"] == 201
    assert shr["runway"] == {
        "stock_lasts_days": 28,
        "lead_time_days": 84,
        "cushion_days": 14,
        "horizon_days": 182,
    }
    statuses = [i["status"] for i in d["order_items"]]
    assert statuses == sorted(
        statuses, key=["OUT_OF_STOCK", "TOO_LATE", "OVERDUE", "ORDER_THIS_WEEK", "ORDER_SOON"].index
    )  # most urgent first
    assert all(i["lifecycle_status"] == "active" for i in d["order_items"] + d["fine_items"])  # G17
    stuck = {s["item_code"]: s for s in d["stuck_items"]}
    assert stuck["SAL-POR6"]["qty"] == 1350 and stuck["SAL-POR6"]["qty_at_harbor"] == 1050
    harbor_lots = [lot for lot in stuck["SAL-POR6"]["lots"] if lot["at_harbor"]]
    assert harbor_lots and all(lot["location_name"] == "Harbor Cold Storage" for lot in harbor_lots)
    assert "SHR-1620" not in stuck
    assert d["trust_strip"]["on_hold"] == {"CS": 420} and d["trust_strip"]["late_po_qty"] == {"CS": 1500}
    assert {line["po_no"] for line in d["late_inventory"]["late_pos"]} == {
        "PO-260394",
        "PO-260376",
        "PO-260407",
    }
    assert d["summary"]["sentences"][0].startswith("3 items will run out before a new order can arrive.")


def test_item_drill_down_explains_the_number(api: TestClient) -> None:
    r = api.get(f"{V}/items/SHR-1620")
    assert r.status_code == 200
    d = r.json()
    assert d["vendor"]["lead_time_days"] == 84 and d["vendor"]["lead_time_days_bluetide"] == 56
    assert d["incoming"][0]["eta"] == "2027-01-25" and d["incoming"][0]["bluetide_date"] == "2026-12-28"
    assert any(p["customer_name"] == "Seabright Markets" and p["qty"] == 120 for p in d["promised"])
    reasons = {lot["location_code"]: lot["reason"] for lot in d["lots"]}
    assert reasons["QA-HOLD"].startswith("On QA hold")
    first = d["breakdown"][0]
    assert (first["key"], first["qty"], first["unit"], first["link"]) == ("can_sell", 480, "cases", "#have")
    assert len(d["projection"]) == 183 and d["demand"]["season_by_month"]["12"] > 1.4
    assert {"label": "Lent 2027", "start": "2027-02-10", "end": "2027-03-28"} in d["season_markers"]


def test_item_lookup_accepts_bluetide_spellings(api: TestClient) -> None:
    for spelling in ["shr-1620 ", "Shr-1620", "  SHR-1620"]:
        r = api.get(f"{V}/items/{spelling}")
        assert r.status_code == 200 and r.json()["card"]["item_code"] == "SHR-1620", spelling
    missing = api.get(f"{V}/items/NOPE-1")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "item_not_found"


def test_late_po_item_shows_it_is_only_covered_by_the_late_po(api: TestClient) -> None:
    d = api.get(f"{V}/items/CAL-RING").json()
    assert d["card"]["covered_only_by_late_po"] and d["incoming"] == []
    assert d["late"][0]["po_no"] == "PO-260407" and d["late"][0]["eta"] is None


def test_items_list_includes_everything(api: TestClient) -> None:
    items = api.get(f"{V}/items").json()
    assert len(items) == 45
    assert {i["item_code"]: i["status"] for i in items}["ZZ-SHR-0001"] == "NOT_PLANNED"


# ---- Writes: Dana's knowledge, each audited -------------------------------------------------------


def test_lead_time_edit_is_validated_audited_and_changes_the_plan(api: TestClient, db_engine: Engine) -> None:
    r = api.patch(f"{V}/vendors/BXE", json={"lead_time_days": 0})
    assert r.status_code == 422 and "between 1 and 365" in r.json()["error"]["message"]
    r = api.patch(
        f"{V}/vendors/BXE",
        json={"lead_time_days": 70, "note": "Vendor says 10 weeks now"},
        headers={"X-Actor": "Ishan"},
    )
    assert r.status_code == 200 and r.json()["lead_time_days"] == 70 and r.json()["updated_by"] == "Ishan"
    audit = api.get(f"{V}/audit-log").json()[0]
    assert (
        audit["action"],
        audit["actor"],
        audit["before"]["lead_time_days"],
        audit["after"]["lead_time_days"],
    ) == ("vendor_settings.update", "Ishan", 84, 70)
    shr = api.get(f"{V}/items/SHR-1620").json()
    assert shr["vendor"]["lead_time_days"] == 70 and shr["card"]["new_order_arrival"] == "2027-01-25"


def test_po_arrival_date_can_be_set_and_cleared(api: TestClient) -> None:
    before = api.get(f"{V}/items/SHR-2125").json()
    assert before["late"] and before["incoming"] == []
    assert api.patch(f"{V}/purchase-orders/PO-260394/lines/1", json={"eta": "2026-11-01"}).status_code == 422
    r = api.patch(
        f"{V}/purchase-orders/PO-260394/lines/1", json={"eta": "2026-12-01", "note": "Vendor confirmed"}
    )
    assert r.status_code == 200 and r.json()["eta"] == "2026-12-01"
    after = api.get(f"{V}/items/SHR-2125").json()
    assert after["late"] == [] and after["incoming"][0]["eta_source"] == "Set by Dana"
    assert api.patch(f"{V}/purchase-orders/PO-260394/lines/1", json={"eta": None}).status_code == 200
    assert api.get(f"{V}/items/SHR-2125").json()["late"]  # back to late
    actions = [a["action"] for a in api.get(f"{V}/audit-log").json()]
    assert actions[:2] == ["po_eta.clear", "po_eta.set"]
    assert api.patch(f"{V}/purchase-orders/PO-999/lines/1", json={"eta": "2026-12-01"}).status_code == 404


def test_handled_note_counts_moves_the_item_and_can_be_cleared(api: TestClient) -> None:
    r = api.post(
        f"{V}/items/shr-1620 /handled",
        json={"qty": 400, "eta": "2026-12-10", "note": "Bought from a local broker"},
    )
    assert r.status_code == 201
    note = r.json()
    assert note["counts_as_incoming"] and note["created_by"] == "Dana"
    d = api.get(f"{V}/dashboard").json()
    assert "SHR-1620" in {i["item_code"] for i in d["handled_items"]}
    assert "SHR-1620" not in {i["item_code"] for i in d["order_items"]}
    detail = api.get(f"{V}/items/SHR-1620").json()
    assert any(i["source"] == "handled_note" and i["qty"] == 400 for i in detail["incoming"])
    cleared = api.request("DELETE", f"{V}/handled/{note['id']}", json={"reason": "Arrived"})
    assert cleared.status_code == 200
    assert api.request("DELETE", f"{V}/handled/{note['id']}").status_code == 409
    assert "SHR-1620" in {i["item_code"] for i in api.get(f"{V}/dashboard").json()["order_items"]}
    actions = [a["action"] for a in api.get(f"{V}/audit-log").json()]
    assert actions[:2] == ["handled.clear", "handled.create"]


def test_handled_note_rejects_bad_input_in_plain_english(api: TestClient) -> None:
    r = api.post(f"{V}/items/SHR-1620/handled", json={"qty": -5})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"
    r = api.post(f"{V}/items/SHR-1620/handled", json={"eta": "2026-01-01"})
    assert r.status_code == 422 and "already passed" in r.json()["error"]["message"]


def test_item_settings_revive_a_dormant_item(api: TestClient) -> None:
    assert {i["item_code"]: i["status"] for i in api.get(f"{V}/items").json()}["SHR-6170"] == "NOT_PLANNED"
    r = api.patch(
        f"{V}/items/SHR-6170/settings", json={"lifecycle_override": "active", "note": "Chef asked for it"}
    )
    assert r.status_code == 200 and r.json()["lifecycle_override"] == "active"
    assert {i["item_code"]: i["status"] for i in api.get(f"{V}/items").json()}["SHR-6170"] != "NOT_PLANNED"
    assert api.patch(f"{V}/items/SHR-6170/settings", json={"safety_days_override": 999}).status_code == 422


def test_failed_edit_writes_nothing(api: TestClient, db_engine: Engine) -> None:
    before = _count(db_engine, "select count(*) from audit_log")
    assert api.patch(f"{V}/vendors/BXE", json={"cushion_days": 400}).status_code == 422
    assert _count(db_engine, "select count(*) from audit_log") == before
    assert _count(db_engine, "select lead_time_days from vendor_settings where vendor_code='BXE'") == 84


# ---- Data notes, activity, settings, logging ----------------------------------------------------


def test_data_notes_summary_and_rows_with_the_original_csv(api: TestClient) -> None:
    summary = api.get(f"{V}/data-issues/summary").json()
    assert summary["total"] == 4047
    traps = {t["trap_id"]: t for t in summary["by_trap"]}
    assert traps["T01"]["count"] == 115 and traps["T01"]["title"] == "Two nights in the on-hand file"
    page = api.get(f"{V}/data-issues", params={"trap_id": "t02", "limit": 5}).json()
    assert page["total"] == 78 and len(page["items"]) == 5
    first = page["items"][0]
    assert first["raw"] is not None and first["raw"]["item_code"] != first["raw"]["item_code"].strip().upper()


def test_activity_load_runs_settings_and_client_events(api: TestClient, db_engine: Engine) -> None:
    runs = api.get(f"{V}/load-runs").json()
    assert runs[0]["status"] == "succeeded" and runs[0]["summary"]["errors"] == 0
    rules = {r["name"]: r for r in api.get(f"{V}/settings").json()}
    assert (
        rules["open_orders_in_selling_rate"]["value"] is False
        and rules["six_month_line_months"]["value"] == 6
    )
    assert (
        api.post(
            f"{V}/client-events", json={"event": "chart_failed", "details": {"page": "item"}}
        ).status_code
        == 202
    )
    events = api.get(f"{V}/events").json()
    assert events[0]["source"] == "web" and events[0]["event"] == "chart_failed"


def test_every_request_is_written_to_request_log(api: TestClient, db_engine: Engine) -> None:
    before = _count(db_engine, "select count(*) from request_log")
    api.get(f"{V}/health", headers={"X-Request-ID": "web-test-request-1"})
    assert _count(db_engine, "select count(*) from request_log") == before + 1
    assert _count(db_engine, "select count(*) from request_log where request_id = 'web-test-request-1'") == 1


def test_health_reads_the_load_time_from_the_database(api: TestClient) -> None:
    body = api.get(f"{V}/health").json()
    assert body["status"] == "ok" and body["last_load_at"] is not None


def test_docs_live_under_api_v1(api: TestClient) -> None:
    assert api.get(f"{V}/docs").status_code == 200
    assert "/api/v1/dashboard" in api.get(f"{V}/openapi.json").json()["paths"]


def test_writer_clears_clean_tables_in_a_safe_order() -> None:
    assert set(CLEAN_LAYER_INSERT_ORDER) == set(CLEAN_LAYER)
