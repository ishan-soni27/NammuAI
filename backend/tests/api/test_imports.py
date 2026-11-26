"""Weekly uploads through the API (ADR-029), on the real data: Dana's BlueTide files, checked, then loaded.

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


def _start(api: TestClient, kind: str = "bluetide") -> int:
    r = api.post(f"{V}/imports", json={"kind": kind})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _put(api: TestClient, upload_id: int, slot: str, content: bytes, name: str = "file.csv"):
    return api.put(f"{V}/imports/{upload_id}/files/{slot}", params={"name": name}, content=content)


def _summary(api: TestClient) -> tuple[int, int, int, int]:
    s = api.get(f"{V}/dashboard").json()["summary"]
    return s["too_late"], s["order_this_week"], s["order_soon"], s["fine"]


# ---- BlueTide's files ---------------------------------------------------------------------------


def test_reloading_the_same_bluetide_files_changes_nothing_and_keeps_danas_knowledge(
    api: TestClient, db_engine: Engine
) -> None:
    # Dana's knowledge first: it must survive the load (invariant #5).
    assert api.patch(f"{V}/purchase-orders/PO-260394/lines/1", json={"eta": "2026-12-04"}).status_code == 200
    r = api.post(f"{V}/items/SHR-2125/handled", json={"qty": 100, "eta": "2026-12-10", "note": "Air"})
    assert r.status_code == 201
    assert api.patch(f"{V}/items/TIL-FIL/settings", json={"cases_per_pallet": 50}).status_code == 200
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
    # Her date, note and pallet number are all still there.
    assert _count(db_engine, "SELECT count(*) FROM po_eta_overrides") == 1
    assert _count(db_engine, "SELECT count(*) FROM handled_flags WHERE cleared_at IS NULL") == 1
    assert _count(db_engine, "SELECT cases_per_pallet FROM item_settings WHERE item_code = 'TIL-FIL'") == 50
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
