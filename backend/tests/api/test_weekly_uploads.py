"""Weekly uploads (ADR-032, step 3), through the API on the real data.

Every Monday Dana uploads BlueTide's exports. These tests check that the week-to-week loop is right:
- sales history accumulates (an export of recent weeks keeps the older history);
- an order that changed is updated, not duplicated, and new lines are added;
- every carried-over line still traces to the upload and line it came from;
- handled notes keep the business day they were written;
- old loads' raw rows are pruned, so storage stays bounded.

The BlueTide files are the real working copies in data/raw (read, never modified: invariant #2);
modified copies are built in memory.
"""

from __future__ import annotations

import csv
import io
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.config.business_rules import BusinessRules
from app.config.settings import REPO_ROOT
from app.loader.pipeline import build_dataset
from app.loader.read_raw import RAW_FILES, read_all_raw
from app.loader.reference import load_reference
from app.loader.write import start_load_run, write_load

V = "/api/v1"
RAW = REPO_ROOT / "data" / "raw"
SALES = RAW_FILES["sales_lines"]


def _sales_rows() -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO((RAW / SALES).read_bytes().decode("utf-8")))
    return list(reader.fieldnames or []), list(reader)


def _csv(header: list[str], rows: list[dict[str, str]]) -> bytes:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=header, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def _order_date(row: dict[str, str]) -> date:
    raw = row["order_date"].strip()
    if "/" in raw:
        month, day, year = raw.split("/")
        return date(int(year), int(month), int(day))
    return date.fromisoformat(raw)


def _upload_sales(api: TestClient, content: bytes) -> dict:
    upload = api.post(f"{V}/imports", json={}).json()["id"]
    r = api.put(f"{V}/imports/{upload}/files/sales_lines", params={"name": SALES}, content=content)
    assert r.status_code == 200, r.text
    return api.post(f"{V}/imports/{upload}/check").json()


def _load(api: TestClient, checked: dict) -> None:
    r = api.post(f"{V}/imports/{checked['id']}/load", json={"confirm_code": checked["confirm_code"]})
    assert r.status_code == 200, r.text


def _count(engine: Engine, sql: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(sql)).scalar_one())


# ---- Sales accumulate -------------------------------------------------------------------------


def test_an_export_of_recent_weeks_keeps_the_older_history(api: TestClient, db_engine: Engine) -> None:
    header, rows = _sales_rows()
    recent = [r for r in rows if _order_date(r) >= date(2026, 10, 1)]
    before_lines = _count(db_engine, "SELECT count(*) FROM sales_lines")
    before_demand = api.get(f"{V}/items/SHR-1620").json()["demand"]
    before_summary = api.get(f"{V}/dashboard").json()["summary"]

    checked = _upload_sales(api, _csv(header, recent))
    sales = checked["report"]["sales"]
    assert (sales["new"], sales["updated"], sales["unchanged"]) == (0, 0, len(recent))
    assert sales["kept"] == len(rows) - len(recent) and sales["months_of_history"] >= 12
    assert not any("months of sales history" in w for w in checked["report"]["warnings"])
    _load(api, checked)

    assert _count(db_engine, "SELECT count(*) FROM sales_lines") == before_lines  # nothing lost
    # The selling rate and the season pattern are recomputed from the merged history: unchanged.
    after_demand = api.get(f"{V}/items/SHR-1620").json()["demand"]
    assert after_demand["selling_per_week"] == before_demand["selling_per_week"]
    assert after_demand["season_by_month"] == before_demand["season_by_month"]
    assert api.get(f"{V}/dashboard").json()["summary"] == before_summary

    # Carried-over lines still trace to the first load's file and line.
    latest = _count(db_engine, "SELECT max(id) FROM load_runs")
    kept = _count(
        db_engine,
        f"SELECT count(*) FROM raw_rows WHERE load_run_id = {latest} AND source_file = '{SALES}' "
        "AND origin_load_run_id = 1",
    )
    assert kept == len(rows) - len(recent)
    assert _count(db_engine, f"SELECT count(*) FROM data_issues WHERE source_file = '{SALES} (load #1)'") > 0


def test_an_order_that_changed_is_updated_not_duplicated_and_new_lines_are_added(
    api: TestClient, db_engine: Engine
) -> None:
    header, rows = _sales_rows()
    before_lines = _count(db_engine, "SELECT count(*) FROM sales_lines")
    assert api.get(f"{V}/items/SHR-1620").json()["card"]["promised_to_customers"] == 201
    for r in rows:  # Seabright's 120 cases of 16/20 shrimp for Dec 14 has shipped and been invoiced
        if r["order_no"].strip() == "SO-251062" and r["item_code"].strip().upper() == "SHR-1620":
            r["status"] = "INVOICED"
    new_line = dict(rows[-1])
    new_line.update(
        order_no="SO-999001", line_no="1", order_date="2026-11-15", ship_date="2026-11-20", status="OPEN"
    )
    new_line.update(item_code="SHR-1620", qty="10")

    checked = _upload_sales(api, _csv(header, [*rows, new_line]))
    sales = checked["report"]["sales"]
    assert (sales["new"], sales["updated"], sales["unchanged"], sales["kept"]) == (1, 1, len(rows) - 1, 0)
    _load(api, checked)

    assert _count(db_engine, "SELECT count(*) FROM sales_lines") == before_lines + 1  # updated, not added
    status = _count(
        db_engine, "SELECT count(*) FROM sales_lines WHERE order_no = 'SO-251062' AND status = 'INVOICED'"
    )
    assert status == 1
    # 201 promised - 120 invoiced + 10 new = 91.
    assert api.get(f"{V}/items/SHR-1620").json()["card"]["promised_to_customers"] == 91


def test_less_than_a_year_of_history_is_warned_about(api: TestClient, db_engine: Engine) -> None:
    # As if there were no stored history (a first upload of recent weeks only).
    with db_engine.begin() as conn:
        conn.execute(text(f"UPDATE raw_rows SET source_file = 'renamed.csv' WHERE source_file = '{SALES}'"))
    header, rows = _sales_rows()
    checked = _upload_sales(api, _csv(header, [r for r in rows if _order_date(r) >= date(2026, 10, 1)]))
    assert checked["report"]["sales"]["months_of_history"] < 2
    assert any("months of sales history" in w for w in checked["report"]["warnings"])


# ---- Handled notes are dated in business time ----------------------------------------------------


def test_a_handled_note_keeps_the_business_day_it_was_written(api: TestClient, db_engine: Engine) -> None:
    r = api.post(f"{V}/items/SHR-1620/handled", json={"note": "Air freight booked"})
    assert r.status_code == 201
    note_id = r.json()["id"]
    created_on = _count(db_engine, "SELECT count(*) FROM handled_flags WHERE created_on = '2026-11-16'")
    assert created_on == 1

    def hint() -> list[str]:
        card = next(
            c for c in api.get(f"{V}/dashboard").json()["handled_items"] if c["item_code"] == "SHR-1620"
        )
        return card["handled_note"]["bluetide_now_shows"]

    # PO-260443 was ordered Nov 2, before the note: it's not "BlueTide caught up".
    assert hint() == []
    # A note written Nov 1 was before that PO: BlueTide caught up, so suggest clearing it.
    with db_engine.begin() as conn:
        conn.execute(text(f"UPDATE handled_flags SET created_on = '2026-11-01' WHERE id = {note_id}"))
    assert hint() == ["PO-260443"]


# ---- Storage stays bounded --------------------------------------------------------------------


def test_only_the_newest_n_loads_keep_their_raw_rows_and_notes(db_engine: Engine) -> None:
    rules = BusinessRules()
    result = build_dataset(read_all_raw(), load_reference(), rules)
    with db_engine.begin() as conn:  # an upload tied to load #1, with its file bytes
        conn.execute(
            text(
                "INSERT INTO uploads (id, kind, status, load_run_id, created_by, updated_by) "
                "VALUES (90, 'bluetide', 'loaded', 1, 'test', 'test')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO upload_files (upload_id, slot, file_name, sha256, size_bytes, rows, content) "
                "VALUES (90, 'items', 'bluetide_items.csv', 'abc', 3, 1, X'616263')"
            )
        )
    runs = []
    for _ in range(2):
        run_id = start_load_run(db_engine, result, rules, "test")
        write_load(db_engine, run_id, result, (), keep_loads=2)
        runs.append(run_id)
    with db_engine.connect() as conn:
        raw_runs = sorted(conn.execute(text("SELECT DISTINCT load_run_id FROM raw_rows")).scalars())
        note_runs = sorted(conn.execute(text("SELECT DISTINCT load_run_id FROM data_issues")).scalars())
        all_runs = conn.execute(text("SELECT count(*) FROM load_runs")).scalar_one()
        content = conn.execute(text("SELECT content FROM upload_files WHERE upload_id = 90")).scalar_one()
        pruned = conn.execute(text(f"SELECT summary FROM load_runs WHERE id = {runs[-1]}")).scalar_one()
    assert raw_runs == note_runs == runs  # load #1's raw rows and notes are gone
    assert all_runs == 3  # every load's summary stays
    assert content is None  # its upload keeps name, sha256 and rows, not the bytes
    assert '"pruned_load_runs": [1]' in str(pruned).replace("'", '"')
