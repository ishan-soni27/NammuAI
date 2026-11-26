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


# ---- Step 2: shipments, picks and moves (R7-R10) ---------------------------------------------

from app.planning.records import (  # noqa: E402
    AppShipmentLine,
    LotRecord,
    MovementInput,
    apply_movements,
    reconcile_shipments,
)


def ship(status: str = "open", order_no: str = "SH-00001", kind: str = "customer", real: bool = True, qty=40):
    return AppShipmentLine(1, order_no, 1, "X", "Seabright Markets", kind, D(-1), D(3), status, qty, real)  # type: ignore[arg-type]


def test_r7_bluetide_invoiced_beats_an_open_order_here() -> None:
    r = reconcile_shipments([ship("open", "SO-1")], {("SO-1", "X"): "INVOICED"})
    (line,) = r.lines
    assert not line.promised and not line.taken_from_stock and r.sales == ()
    assert any("invoiced" in f for f in line.flags) and r.applied_shipments == frozenset()


def test_r8_shipped_here_but_open_in_bluetide_is_taken_once_from_stock() -> None:
    r = reconcile_shipments([ship("shipped", "SO-1")], {("SO-1", "X"): "OPEN"})
    assert r.applied_shipments == {1} and ("SO-1", "X") in r.drop_bluetide_open
    assert [(s.is_open, s.qty) for s in r.sales] == [
        (False, 40)
    ]  # a sale for the selling rate, not a promise


def test_r8_open_in_both_is_promised_once_hers() -> None:
    r = reconcile_shipments([ship("open", "SO-1", qty=50)], {("SO-1", "X"): "OPEN"})
    assert ("SO-1", "X") in r.drop_bluetide_open and [(s.is_open, s.qty) for s in r.sales] == [(True, 50)]


def test_shipped_in_both_is_not_taken_again() -> None:
    r = reconcile_shipments([ship("shipped", "SO-1")], {("SO-1", "X"): "INVOICED"})
    assert r.applied_shipments == frozenset() and r.sales == () and r.lines[0].flags == ()


def test_cancelled_here_drops_bluetides_open_line() -> None:
    r = reconcile_shipments([ship("cancelled", "SO-1")], {("SO-1", "X"): "OPEN"})
    assert ("SO-1", "X") in r.drop_bluetide_open and r.sales == () and not r.lines[0].promised


def test_a_shipped_sample_takes_stock_but_is_not_demand() -> None:
    r = reconcile_shipments([ship("shipped", kind="sample", real=False)], {})
    assert r.applied_shipments == {1} and r.sales == ()


def _lots(*specs) -> list[LotRecord]:
    return [LotRecord(lot(qty=q, location=loc, lot_no=n, expiry=e), "bluetide") for q, loc, n, e in specs]


def mv(mid, kind, qty, loc="NB", lot_no="L1", on=D(0), shipment=None, expiry=date(2028, 1, 1)):
    return MovementInput(mid, kind, "X", loc, lot_no, qty, expiry, 10.0, on, shipment)


def test_r10_a_pick_larger_than_its_lot_takes_the_next_to_expire_in_that_building() -> None:
    lots = _lots(
        (30, "NB", "L1", date(2028, 1, 1)),
        (50, "NB", "L2", date(2027, 6, 1)),
        (50, "NB", "L3", date(2028, 6, 1)),
    )
    out, flags = apply_movements(
        lots, [mv(1, "shipment", -60, shipment=1)], frozenset({1}), None, frozenset({"NB"})
    )
    assert [r.lot.qty for r in out] == [0, 20, 50] and flags == ()


def test_r10_stock_never_goes_below_zero_and_the_shortfall_is_flagged() -> None:
    out, flags = apply_movements(
        _lots((30, "NB", "L1", date(2028, 1, 1))),
        [mv(1, "shipment", -45, shipment=1)],
        frozenset({1}),
        None,
        frozenset({"NB"}),
    )
    assert out[0].lot.qty == 0 and len(flags) == 1 and "15" in flags[0] and "shortfall" in flags[0]


def test_picks_of_a_shipment_not_taken_from_stock_are_ignored() -> None:
    out, _ = apply_movements(
        _lots((30, "NB", "L1", None)),
        [mv(1, "shipment", -10, shipment=7)],
        frozenset(),
        None,
        frozenset({"NB"}),
    )
    assert out[0].lot.qty == 30


def test_a_move_creates_the_lot_in_the_new_building_with_its_expiry() -> None:
    moves = [mv(1, "move_out", -20, "HCS", "L9"), mv(2, "move_in", 20, "NB", "L9", expiry=date(2027, 3, 1))]
    out, flags = apply_movements(
        _lots((50, "HCS", "L9", date(2027, 3, 1))), moves, frozenset(), None, frozenset({"NB", "HCS"})
    )
    by_place = {r.lot.location_code: r for r in out}
    assert by_place["HCS"].lot.qty == 30 and by_place["NB"].lot.qty == 20
    assert (
        by_place["NB"].origin == "moved"
        and by_place["NB"].lot.expiry_date == date(2027, 3, 1)
        and flags == ()
    )


def test_r9_a_move_dated_before_bluetides_stock_count_is_already_in_it() -> None:
    moves = [mv(1, "move_out", -20, "HCS", "L9", on=D(-5)), mv(2, "move_in", 20, "NB", "L9", on=D(-5))]
    out, _ = apply_movements(
        _lots((50, "HCS", "L9", None)), moves, frozenset(), D(-1), frozenset({"NB", "HCS"})
    )
    assert [(r.lot.location_code, r.lot.qty) for r in out] == [("HCS", 50)]


def test_shipping_her_own_received_stock_with_no_bluetide_data() -> None:
    received = [LotRecord(lot(qty=120, lot_no="R1"), "received")]
    out, _ = apply_movements(
        received, [mv(1, "shipment", -45, lot_no="R1", shipment=1)], frozenset({1}), None, frozenset({"NB"})
    )
    assert out[0].lot.qty == 75
