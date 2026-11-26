"""Matching Dana's records with BlueTide's (planning/records.py, ADR-027): one test or more per rule R1-R6.

The promise these tests keep: the same cases are never counted twice (in stock AND on the way, or on
two copies of one PO), and BlueTide-only data behaves exactly as before Phase 6.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest

from app.planning.engine import plan
from app.planning.records import (
    AppPOLine,
    BlueTidePOLine,
    LineStatusInput,
    ReceiptInput,
    reconcile_pos,
)
from app.planning.types import EtaOverrideInput, ItemInput, VendorInput, VendorSettingInput
from tests.unit.planning.builders import AS_OF, LOCATIONS, RULES, inputs, lot, steady_sales

D = lambda n: AS_OF + timedelta(days=n)  # noqa: E731


def bt(
    po_no: str = "PO-1",
    line_no: int = 1,
    code: str = "X",
    ordered: float | None = 100,
    received: float = 0,
    status: str = "open",
    remaining: float | None = None,
) -> BlueTidePOLine:
    if remaining is None:
        remaining = (ordered or 0) - received if status == "open" else 0.0
    return BlueTidePOLine(po_no, line_no, code, "V1", D(-20), D(10), ordered, received, remaining, status)


def app(po_no: str = "KB-00001", line_no: int = 1, code: str = "X", ordered: float = 100) -> AppPOLine:
    return AppPOLine(po_no, line_no, code, "V1", D(-1), ordered, 9.5)


def receipt(
    qty: float,
    po_no: str = "KB-00001",
    line_no: int = 1,
    lot_no: str = "R1",
    on: date = AS_OF,
    movement_id: int = 1,
) -> ReceiptInput:
    return ReceiptInput(movement_id, po_no, line_no, "X", "NB", lot_no, qty, date(2028, 6, 1), 9.5, on)


def only(result, po_no: str = "KB-00001", line_no: int = 1):
    return next(x for x in result.lines if x.po_no == po_no and x.line_no == line_no)


# ---- BlueTide alone: unchanged from before Phase 6 ------------------------------------------


def test_bluetide_only_open_line_is_counted_with_the_loaders_remaining() -> None:
    r = reconcile_pos([bt(ordered=100, received=40)], [], [], [])
    assert [(x.po_no, x.qty_remaining) for x in r.po_inputs] == [("PO-1", 60)]
    assert only(r, "PO-1").status == "open" and only(r, "PO-1").flags == ()


@pytest.mark.parametrize("status", ["complete", "cancelled"])
def test_bluetide_only_closed_lines_are_not_counted_and_not_flagged(status: str) -> None:
    r = reconcile_pos([bt(status=status, received=100 if status == "complete" else 0)], [], [], [])
    assert r.po_inputs == () and only(r, "PO-1").flags == ()


# ---- R1: Dana's own PO ----------------------------------------------------------------------


def test_r1_app_po_is_counted_as_on_the_way_and_marked_as_hers() -> None:
    r = reconcile_pos([], [app(ordered=300)], [], [])
    (line,) = r.po_inputs
    assert line.source == "app" and line.qty_remaining == 300 and line.expected_date_system is None


def test_r1_app_po_reaches_the_engine_with_her_date() -> None:
    r = reconcile_pos([], [app(ordered=300)], [], [])
    result = plan(
        inputs(pos=list(r.po_inputs), overrides=[EtaOverrideInput("KB-00001", 1, D(9), "Dana")]),
        RULES,
    )
    (incoming,) = result.items[0].incoming
    assert incoming.reference == "Your PO KB-00001 line 1"
    assert incoming.eta == D(9) and incoming.eta_source == "Set by Dana" and incoming.qty == 300


def test_r1_cancelled_app_line_is_not_counted() -> None:
    r = reconcile_pos([], [app()], [LineStatusInput("KB-00001", 1, "cancelled", cancel_reason="Price")], [])
    assert r.po_inputs == () and only(r).status == "cancelled"


def test_r1_shipped_app_line_is_still_counted() -> None:
    r = reconcile_pos([], [app()], [LineStatusInput("KB-00001", 1, "shipped", D(0), "MSCU1234567")], [])
    assert only(r).status == "shipped" and only(r).container_no == "MSCU1234567" and len(r.po_inputs) == 1


# ---- R2: the same PO in both ------------------------------------------------------------------


def test_r2_same_po_in_both_is_counted_once_and_her_quantity_wins() -> None:
    r = reconcile_pos([bt("KB-00001", ordered=80)], [app("KB-00001", ordered=100)], [], [])
    assert len(r.po_inputs) == 1 and r.po_inputs[0].qty_remaining == 100
    assert only(r).source == "both"
    assert any("BlueTide has 80" in f for f in only(r).flags)


def test_r2_matches_by_item_when_bluetide_renumbers_the_line() -> None:
    r = reconcile_pos([bt("KB-00001", line_no=2)], [app("KB-00001", line_no=1)], [], [])
    assert len(r.po_inputs) == 1 and len(r.lines) == 1
    assert "BlueTide numbers this line 2" in only(r).flags


def test_r2_a_line_only_one_side_has_is_counted_but_flagged() -> None:
    r = reconcile_pos([bt("KB-00001", line_no=1, code="Y")], [app("KB-00001", line_no=1, code="X")], [], [])
    assert len(r.po_inputs) == 2
    flags = {x.item_code: x.flags for x in r.lines}
    assert "BlueTide's copy of this PO doesn't have this line" in flags["X"]
    assert "Only in BlueTide's copy of this PO" in flags["Y"]


# ---- R3: receipts -----------------------------------------------------------------------------


def test_r3_receipt_becomes_stock_and_leaves_the_rest_on_the_way() -> None:
    r = reconcile_pos([], [app(ordered=100)], [], [receipt(60)])
    assert r.po_inputs[0].qty_remaining == 40
    (received,) = r.received_lots
    assert received.lot.qty == 60 and received.lot.location_code == "NB" and received.lot.expiry_date


def test_r3_full_receipt_is_received_and_not_on_the_way() -> None:
    r = reconcile_pos([], [app(ordered=100)], [], [receipt(100)])
    assert r.po_inputs == () and only(r).status == "received" and only(r).received == 100


def test_r3_receipt_counted_once_when_bluetide_catches_up() -> None:
    # Dana received 60; a later BlueTide file also shows 60 received (and the stock in its count).
    r = reconcile_pos([bt("KB-00001", received=60)], [app("KB-00001")], [], [receipt(60)])
    assert r.received_lots == ()  # the 60 are in BlueTide's count already: not added again
    assert r.po_inputs[0].qty_remaining == 40  # not 100 - 60 - 60
    assert r.skipped_receipts == ((1, "Already in BlueTide's received quantity for this line"),)


def test_r3_only_the_part_bluetide_hasnt_seen_is_added_newest_first() -> None:
    receipts = [receipt(30, on=D(-3), movement_id=1), receipt(30, on=D(0), movement_id=2, lot_no="R2")]
    r = reconcile_pos([bt("KB-00001", received=30)], [app("KB-00001")], [], receipts)
    assert [(x.movement_id, x.lot.qty) for x in r.received_lots] == [(2, 30)]


def test_r3_receipt_on_a_bluetide_po_line_reduces_what_is_still_to_come() -> None:
    r = reconcile_pos([bt(ordered=100, received=0)], [], [], [receipt(25, po_no="PO-1")])
    assert r.po_inputs[0].qty_remaining == 75 and r.received_lots[0].lot.qty == 25


def test_r3_received_stock_reaches_the_engine_as_sellable() -> None:
    r = reconcile_pos([], [app(ordered=100)], [], [receipt(100)])
    lots = [lot(qty=10)] + [x.lot for x in r.received_lots]
    result = plan(inputs(lots=lots), RULES)
    assert result.items[0].on_hand.sellable == pytest.approx(110)


# ---- R4 / R5: BlueTide says it's done ---------------------------------------------------------


def test_r4_bluetide_received_beats_an_open_app_line_and_flags_it() -> None:
    # Dana never recorded the receipt; BlueTide says all 100 arrived. Not on the way any more.
    r = reconcile_pos([bt("KB-00001", status="complete", received=100)], [app("KB-00001")], [], [])
    assert r.po_inputs == () and r.received_lots == () and only(r).status == "received"
    assert "BlueTide shows 100 received that isn't recorded here" in only(r).flags


def test_r4_bluetide_closed_short_the_rest_is_not_counted() -> None:
    # She ordered 100; BlueTide closed the line as received with 60. The other 40 aren't counted as coming.
    r = reconcile_pos([bt("KB-00001", status="complete", received=60)], [app("KB-00001")], [], [])
    assert r.po_inputs == () and only(r).remaining == 0
    assert any("BlueTide closed this line as received" in f for f in only(r).flags)


def test_r4_a_receipt_bluetide_already_counted_on_a_closed_line_adds_no_stock() -> None:
    r = reconcile_pos([bt(status="complete", received=50)], [], [], [receipt(20, po_no="PO-1")])
    assert r.po_inputs == () and r.received_lots == ()
    assert r.skipped_receipts == ((1, "Already in BlueTide's received quantity for this line"),)


def test_r5_bluetide_cancelled_is_not_counted_and_flagged() -> None:
    r = reconcile_pos([bt("KB-00001", status="cancelled")], [app("KB-00001")], [], [])
    assert r.po_inputs == () and only(r).status == "cancelled"
    assert any("cancelled" in f for f in only(r).flags)


# ---- R6: the lot is already in BlueTide's stock count -----------------------------------------


def test_r6_lot_already_in_a_newer_bluetide_count_is_not_added_twice() -> None:
    r = reconcile_pos([], [app()], [], [receipt(40, on=D(-2))], frozenset({("X", "NB", "R1")}), D(-1))
    assert r.received_lots == ()
    assert r.skipped_receipts == ((1, "Lot R1 is already in BlueTide's stock count"),)


def test_r6_an_older_count_with_the_same_lot_does_not_hide_a_new_receipt() -> None:
    r = reconcile_pos([], [app()], [], [receipt(40, on=D(0))], frozenset({("X", "NB", "R1")}), D(-1))
    assert len(r.received_lots) == 1


# ---- Independent of BlueTide (Ishan, 2026-11-26) ---------------------------------------------


def test_the_plan_works_from_danas_records_alone_with_no_bluetide_data() -> None:
    # No BlueTide items, lots or POs: an item and supplier she added, her PO, a receipt and her own sales.
    mine = ItemInput("KB-COD", "Cod loin 6 oz", "Cod", "CS", 10.0, "KB-V1", "active", "Added in the app")
    r = reconcile_pos(
        [],
        [AppPOLine("KB-00001", 1, "KB-COD", "KB-V1", D(-30), 200, 50.0)],
        [],
        [ReceiptInput(1, "KB-00001", 1, "KB-COD", "NB", "R1", 120, date(2028, 1, 1), 50.0, D(-1))],
    )
    base = inputs(
        items=[mine],
        lots=[x.lot for x in r.received_lots],
        sales=[replace(s, item_code="KB-COD") for s in steady_sales(per_day=2)],
        pos=list(r.po_inputs),
        overrides=[EtaOverrideInput("KB-00001", 1, D(14), "Dana")],
    )
    alone = replace(
        base,
        vendors=(VendorInput("KB-V1", "Gloucester Fillet Co.", "USA", None),),
        vendor_settings=(VendorSettingInput("KB-V1", 21, 7, 7),),
        locations=LOCATIONS,
    )
    p = plan(alone, RULES).items[0]
    assert p.lifecycle_status == "active" and p.vendor_name == "Gloucester Fillet Co."
    assert p.on_hand.sellable == pytest.approx(120)
    assert [(i.reference, i.qty, i.eta) for i in p.incoming] == [("Your PO KB-00001 line 1", 80, D(14))]
    assert p.confirmed.run_out_date is not None  # 2 a day: 120 + 80 lasts about 100 days
