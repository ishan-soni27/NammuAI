"""Phase 6 step 3 through the API, on the real data: importing BlueTide's files and Dana's own templates.

Each test gets a fresh copy of the loaded database (tests/api/conftest.py). The BlueTide files are the
real working copies in data/raw (read, never modified: invariant #2).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.config.settings import REPO_ROOT
from app.loader.read_raw import RAW_FILES

V = "/api/v1"
RAW = REPO_ROOT / "data" / "raw"


def _count(engine: Engine, sql: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(sql)).scalar_one())


def _start(api: TestClient, kind: str) -> int:
    r = api.post(f"{V}/imports", json={"kind": kind})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _put(api: TestClient, upload_id: int, slot: str, content: bytes, name: str = "file.csv"):
    return api.put(f"{V}/imports/{upload_id}/files/{slot}", params={"name": name}, content=content)


def _summary(api: TestClient) -> tuple[int, int, int, int]:
    s = api.get(f"{V}/dashboard").json()["summary"]
    return s["too_late"], s["order_this_week"], s["order_soon"], s["fine"]


# ---- BlueTide's files ---------------------------------------------------------------------------


def test_reloading_the_same_bluetide_files_changes_nothing_and_keeps_danas_records(
    api: TestClient, db_engine: Engine
) -> None:
    # One of Dana's own records first: it must survive the load (invariant #5).
    r = api.post(
        f"{V}/purchase-orders", json={"vendor_code": "BXE", "lines": [{"item_code": "SHR-1620", "qty": 50}]}
    )
    assert r.status_code == 201
    before = _summary(api)
    runs_before = _count(db_engine, "SELECT count(*) FROM load_runs WHERE status = 'succeeded'")

    upload = _start(api, "bluetide")
    for slot in ("items", "inventory_on_hand", "purchase_orders"):
        r = _put(api, upload, slot, (RAW / RAW_FILES[slot]).read_bytes(), RAW_FILES[slot])
        assert r.status_code == 200, r.text
    checked = api.post(f"{V}/imports/{upload}/check").json()
    report = checked["report"]
    assert report["blockers"] == [] and checked["confirm_code"]
    sources = {f["slot"]: f["source"] for f in report["files"]}
    assert sources["items"] == "uploaded" and sources["sales_lines"] == "last load"
    assert all(f["same_as_last"] for f in report["files"])  # byte-identical to the last load
    assert any("nothing will change" in w for w in report["warnings"])
    assert all(c["now"] == c["after"] for c in report["changes"]), report["changes"]
    assert report["snapshot_date"] == "2026-11-15"

    wrong = api.post(f"{V}/imports/{upload}/load", json={"confirm_code": "nope"})
    assert wrong.status_code == 422
    loaded = api.post(f"{V}/imports/{upload}/load", json={"confirm_code": checked["confirm_code"]})
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["status"] == "loaded" and loaded.json()["load_run_id"]
    assert _count(db_engine, "SELECT count(*) FROM load_runs WHERE status = 'succeeded'") == runs_before + 1
    assert _summary(api) == before  # same files, same numbers
    assert _count(db_engine, "SELECT count(*) FROM purchase_orders") == 1  # Dana's PO is still there
    assert _count(db_engine, "SELECT count(*) FROM audit_log WHERE action = 'import.load'") == 1


def test_a_wrong_or_empty_file_is_refused_before_anything_is_checked(api: TestClient) -> None:
    upload = _start(api, "bluetide")
    vendors = (RAW / RAW_FILES["vendors"]).read_bytes()
    r = _put(api, upload, "items", vendors, "bluetide_vendors.csv")
    assert (
        r.status_code == 422 and "doesn't look like BlueTide's items export" in r.json()["error"]["message"]
    )
    header_only = (RAW / RAW_FILES["items"]).read_bytes().split(b"\r\n")[0] + b"\r\n"
    r = _put(api, upload, "items", header_only, "items.csv")
    assert r.status_code == 422 and "no rows" in r.json()["error"]["message"]
    assert _put(api, upload, "nope", vendors).status_code == 404


def _inventory_with(old: bytes, new: bytes) -> bytes:
    return (RAW / RAW_FILES["inventory_on_hand"]).read_bytes().replace(old, new)


def test_a_stock_count_after_today_blocks_the_load(api: TestClient) -> None:
    upload = _start(api, "bluetide")
    _put(api, upload, "inventory_on_hand", _inventory_with(b"2026-11-15", b"2026-11-20"))
    checked = api.post(f"{V}/imports/{upload}/check").json()
    assert checked["confirm_code"] is None
    assert any("after today" in b for b in checked["report"]["blockers"])
    r = api.post(f"{V}/imports/{upload}/load", json={"confirm_code": "x"})
    assert r.status_code == 409


def test_an_older_stock_count_than_the_one_loaded_is_blocked(api: TestClient) -> None:
    upload = _start(api, "bluetide")
    _put(api, upload, "inventory_on_hand", _inventory_with(b"2026-11-15", b"2026-11-14"))
    blockers = api.post(f"{V}/imports/{upload}/check").json()["report"]["blockers"]
    assert any("older than the one loaded now" in b for b in blockers)


def test_a_new_file_after_a_check_needs_a_new_check(api: TestClient) -> None:
    upload = _start(api, "bluetide")
    _put(api, upload, "items", (RAW / RAW_FILES["items"]).read_bytes())
    assert api.post(f"{V}/imports/{upload}/check").json()["status"] == "checked"
    again = _put(api, upload, "items", (RAW / RAW_FILES["items"]).read_bytes())
    assert again.json()["status"] == "open" and again.json()["confirm_code"] is None


# ---- Dana's own templates (independent of BlueTide) ---------------------------------------------


def test_templates_download_with_their_header_row(api: TestClient) -> None:
    r = api.get(f"{V}/import-templates/stock_count.csv")
    assert r.status_code == 200 and "count_date,item_code,building,lot_no,quantity" in r.text
    assert "attachment" in r.headers["content-disposition"]


TEMPLATE_FILES = {
    "suppliers": "supplier_code,name,country,weeks_to_arrive,cushion_weeks\r\nGFC,Gloucester Fillet Co.,USA,3,1\r\n",
    "items": (
        "item_code,name,category,sold_by,lb_per_case,supplier_code,still_selling\r\n"
        "KB-COD6,Cod loin 6 oz,Groundfish,case,10,GFC,yes\r\n"
    ),
    "customers": "customer_code,name,type\r\nHLB,Harbor Light Bistro,RESTAURANT\r\n",
    "stock_count": (
        "count_date,item_code,building,lot_no,quantity,expiry_date,unit_cost\r\n"
        "2026-11-16,KB-COD6,New Bedford,C1,120,2028-06-01,52.50\r\n"
        "2026-11-16,SHR-1620,NB,C2,300,2028-01-01,96\r\n"
    ),
    "purchase_orders": (
        "po_no,supplier_code,order_date,expected_date,item_code,quantity,unit_cost\r\n"
        "GFC-1001,GFC,2026-11-16,2026-12-07,KB-COD6,80,52.50\r\n"
    ),
    "sales_history": "order_no,order_date,ship_date,customer_code,item_code,quantity,unit_price\r\n"
    + "".join(f"HLB-{n},2026-{m:02d}-{d:02d},,HLB,KB-COD6,14,80\r\n" for n, (m, d) in enumerate(
        [(9, 28), (10, 5), (10, 12), (10, 19), (10, 26), (11, 2), (11, 9)]
    )),
}  # fmt: skip


def test_her_own_templates_load_and_the_plan_uses_them(api: TestClient, db_engine: Engine) -> None:
    upload = _start(api, "template")
    for slot, body in TEMPLATE_FILES.items():
        r = _put(api, upload, slot, body.encode(), f"{slot}.csv")
        assert r.status_code == 200, (slot, r.text)
    checked = api.post(f"{V}/imports/{upload}/check").json()
    assert checked["report"]["blockers"] == [], checked["report"]["problems"]
    loaded = api.post(f"{V}/imports/{upload}/load", json={"confirm_code": checked["confirm_code"]})
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["report"]["loaded"]["stock_count_lines"] == 2

    card = api.get(f"{V}/items/KB-COD6").json()["card"]
    assert card["vendor_name"] == "Gloucester Fillet Co." and card["sellable"] == 120
    assert card["on_the_way"] == 80  # her imported PO
    demand = api.get(f"{V}/items/KB-COD6").json()["demand"]
    assert demand["selling_per_week"] > 0  # her sales history feeds the selling rate
    # Her count is newer than BlueTide's (Nov 16 > Nov 15): it's the starting stock for SHR-1620.
    shr = api.get(f"{V}/items/SHR-1620").json()
    assert shr["card"]["sellable"] == 300
    assert all("stock count" in lot["reason"] for lot in shr["lots"] if lot["counted"])
    assert _count(db_engine, "SELECT count(*) FROM app_sales_lines") == 7


def test_template_problems_block_the_load_with_the_line(api: TestClient) -> None:
    upload = _start(api, "template")
    bad = "item_code,name,category,sold_by,lb_per_case,supplier_code,still_selling\r\nKB-X,Thing,Cod,case,,NOPE,yes\r\n"
    _put(api, upload, "items", bad.encode())
    report = api.post(f"{V}/imports/{upload}/check").json()["report"]
    assert report["blockers"] and report["problems"][0]["line"] == 2
    assert "pounds per case" in report["problems"][0]["message"]
    wrong = _put(api, upload, "items", b"foo,bar\r\n1,2\r\n")
    assert wrong.status_code == 422 and "template" in wrong.json()["error"]["message"]
