"""The numbers-only "why" and the one late-PO instruction (ADR-033), through the API on the real data."""

from __future__ import annotations

from fastapi.testclient import TestClient

V = "/api/v1"
ANCHORS = {"#have", "#promised", "#on-the-way", "#late", "#demand", "#chart"}


def _rows(api: TestClient, code: str) -> dict:
    d = api.get(f"{V}/items/{code}").json()
    assert "explanation" not in d  # the sentences are gone
    return d


def test_shr_1620_shows_its_arithmetic_row_by_row(api: TestClient) -> None:
    d = _rows(api, "SHR-1620")
    rows = {r["key"]: r for r in d["breakdown"]}
    assert [r["key"] for r in d["breakdown"]] == [
        "can_sell",
        "not_counted",
        "promised",
        "on_the_way",
        "selling",
        "season",
        "runs_out",
        "new_order_lands",
        "short",
        "order_at_least",
    ]
    assert (rows["can_sell"]["qty"], rows["can_sell"]["detail"]) == (480, "HCS 140 · NB 260 · PVD 80")
    assert (rows["not_counted"]["qty"], rows["not_counted"]["detail"]) == (80, "on hold 80")
    assert rows["promised"]["qty"] == 201
    assert (
        "7 open orders" in rows["promised"]["detail"]
        and "Seabright Markets 120 on Mon Dec 14" in rows["promised"]["detail"]
    )
    way = rows["on_the_way"]
    assert (way["label"], way["qty"], way["date"]) == ("On the way: PO-260443 line 1", 600, "2027-01-25")
    assert way["detail"].startswith("BlueTide says Mon Dec 28")
    assert (rows["selling"]["qty"], rows["selling"]["unit"]) == (53.0, "cases a week")
    assert rows["season"]["detail"] == "Shrimp: Nov 1.1× · Dec 1.6× · Jan 0.8×"
    assert rows["runs_out"]["date"] == "2026-12-14" and rows["new_order_lands"]["date"] == "2027-02-08"
    assert (rows["short"]["qty"], rows["short"]["date"]) == (382, "2026-12-14")
    assert rows["short"]["detail"] == "until Mon Jan 25, when stock on the way lands"
    assert rows["order_at_least"]["qty"] == 0 and d["card"]["instruction"] is None
    assert {r["link"] for r in d["breakdown"]} <= ANCHORS


def test_one_instruction_for_items_only_a_late_po_would_cover(api: TestClient) -> None:
    ask = "Ask the supplier for its date and set it here, and these numbers update."
    expected = {
        "SHR-2125": f"Order at least 127 cases, unless PO-260394 (800 cases) is really coming. {ask}",
        "CAL-RING": f"Order at least 5 cases, unless PO-260407 (300 cases) is really coming. {ask}",
        "PAN-0709": f"Nothing to order today, but PO-260376 (400 cases) is late. {ask}",
    }
    for code, sentence in expected.items():
        d = _rows(api, code)
        assert d["card"]["instruction"] == sentence, code
        assert {"late", "if_late_arrives"} <= {r["key"] for r in d["breakdown"]}
    # The Monday card carries the same sentence; items without a late PO carry none.
    cards = {c["item_code"]: c for c in api.get(f"{V}/dashboard").json()["order_items"]}
    assert cards["SHR-2125"]["instruction"] == expected["SHR-2125"]
    assert cards["LOB-T56"]["instruction"] is None


def test_a_past_order_by_date_says_order_now(api: TestClient) -> None:
    row = next(r for r in _rows(api, "SHR-2125")["breakdown"] if r["key"] == "order_at_least")
    assert row["date"] is None and row["detail"].startswith("order now (was due Tue Aug 18)")
