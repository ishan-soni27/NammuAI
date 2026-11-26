"""Harbor storage cost (P1 #1; ADR-031) on the real data: what's there, pallets, $, her saved table."""

from __future__ import annotations

import csv
import io

from fastapi.testclient import TestClient

V = "/api/v1"


def _item(page: dict, code: str) -> dict:
    return next(x for x in page["items"] if x["item_code"] == code)


def test_lists_what_is_at_harbor_with_no_cost_until_cases_per_pallet(api: TestClient) -> None:
    page = api.get(f"{V}/harbor-storage").json()
    assert page["rate_per_pallet_month"] == 30 and page["location_names"] == ["Harbor Cold Storage"]
    assert page["totals"]["items"] == 14 and page["totals"]["cases"] == 2095
    sal = _item(page, "SAL-POR6")
    assert sal["cases"] == 1050 and len(sal["lots"]) == 2 and sal["pallets"] is None
    assert sal["stuck_tag"] == "INSIDE_SIX_MONTHS"
    assert _item(page, "SHR-1620")["stuck_tag"] is None  # needed for selling: at Harbor, not stuck (G-fact)
    assert page["totals"]["priced_items"] == 0 and page["saved"] == []


def test_add_to_table_works_it_out_on_the_server_and_remembers_cases_per_pallet(api: TestClient) -> None:
    page = api.post(
        f"{V}/harbor-storage/rows", json={"rows": [{"item_code": "sal-por6", "cases_per_pallet": 60}]}
    ).json()
    row = page["saved"][0]
    assert (row["kind"], row["cases"], row["lots"], row["pallets"], row["cost_per_month"]) == (
        "at_harbor",
        1050,
        2,
        18,
        540,
    )
    assert row["as_of_date"] == "2026-11-16" and row["created_by"]
    sal = _item(page, "SAL-POR6")
    assert (sal["cases_per_pallet"], sal["pallets"], sal["cost_per_month"]) == (60, 18, 540)
    assert page["totals"]["priced_items"] == 1 and page["totals"]["cost_per_month"] == 540
    actions = [a["action"] for a in api.get(f"{V}/audit-log").json()[:2]]
    assert set(actions) == {"harbor_storage.add", "item_settings.update"}


def test_what_if_amount_and_validation(api: TestClient) -> None:
    page = api.post(
        f"{V}/harbor-storage/rows",
        json={"rows": [{"item_code": "SHR-1620", "cases_per_pallet": 80, "cases": 300}]},
    ).json()
    row = page["saved"][0]
    assert (row["kind"], row["lots"], row["pallets"], row["cost_per_month"]) == ("what_if", 1, 4, 120)
    bad = api.post(
        f"{V}/harbor-storage/rows", json={"rows": [{"item_code": "SAL-POR6", "cases_per_pallet": 0}]}
    )
    assert bad.status_code == 422 and "1 to 1,000" in bad.json()["error"]["message"]
    none_there = api.post(
        f"{V}/harbor-storage/rows", json={"rows": [{"item_code": "HAD-FIL", "cases_per_pallet": 50}]}
    )
    assert none_there.status_code == 422 and "no HAD-FIL at Harbor" in none_there.json()["error"]["message"]
    # all or nothing: the good first row wasn't saved either
    mixed = api.post(
        f"{V}/harbor-storage/rows",
        json={
            "rows": [
                {"item_code": "TIL-FIL", "cases_per_pallet": 50},
                {"item_code": "HAD-FIL", "cases_per_pallet": 50},
            ]
        },
    )
    assert mixed.status_code == 422
    assert len(api.get(f"{V}/harbor-storage").json()["saved"]) == 1


def test_cases_per_pallet_on_item_settings_and_delete_and_download(api: TestClient) -> None:
    r = api.patch(f"{V}/items/TIL-FIL/settings", json={"cases_per_pallet": 50})
    assert r.status_code == 200 and r.json()["cases_per_pallet"] == 50
    assert api.patch(f"{V}/items/TIL-FIL/settings", json={"cases_per_pallet": 5000}).status_code == 422
    page = api.get(f"{V}/harbor-storage").json()
    assert _item(page, "TIL-FIL")["pallets"] == 3  # 140 / 50 = 2.8, a part pallet charged whole
    page = api.post(
        f"{V}/harbor-storage/rows", json={"rows": [{"item_code": "TIL-FIL", "cases_per_pallet": 50}]}
    ).json()
    row_id = page["saved"][0]["id"]
    out = api.get(f"{V}/exports/harbor-storage.csv")
    assert out.status_code == 200 and out.content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(io.StringIO(out.content.decode("utf-8-sig"))))
    assert (
        rows[0]["item_code"] == "TIL-FIL"
        and rows[0]["pallets"] == "3"
        and rows[0]["dollars_per_month"] == "90"
    )
    assert rows[0]["what"] == "At Harbor that day" and rows[0]["saved_for"] == "2026-11-16"
    page = api.delete(f"{V}/harbor-storage/rows/{row_id}").json()
    assert page["saved"] == []
    assert api.delete(f"{V}/harbor-storage/rows/{row_id}").status_code == 404
