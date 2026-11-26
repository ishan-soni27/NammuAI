"""Planning-engine rules, one test (or a few) per rule in BUILD_PROMPT §6.6–§6.11 and traps T15, T22, T23, T26, T30."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest

from app.planning.demand import demand_profile
from app.planning.projection import simulate
from app.planning.seasonality import compute_seasonal_index, real_demand_by_day, stockout_days
from app.planning.supply import po_arrival
from app.planning.types import EtaOverrideInput, HandledNoteInput, ItemSettingInput, SaleInput, StockoutInput
from tests.unit.planning.builders import (
    AS_OF,
    RULES,
    item,
    lot,
    one,
    open_order,
    po,
    run,
    steady_sales,
)

D = lambda n: AS_OF + timedelta(days=n)  # noqa: E731

# ---- Demand and seasonality (§6.7) ---------------------------------------------------------


def test_steady_demand_gives_index_one_and_rate_one() -> None:
    p = one(run())
    assert p.demand.base_rate_per_day == pytest.approx(1.0)
    assert all(v == pytest.approx(1.0) for v in p.demand.index_by_month.values())
    assert p.demand.level_per_day == pytest.approx(1.0)


def test_seasonal_index_is_computed_in_pounds_across_units() -> None:
    # A case item (20 lb/cs) selling 1 cs/day and a pound item selling 20 lb/day, December only doubled
    # for the CASE item. In pounds both weigh the same, so the category's December is 1.5x, not
    # swamped by the pound item's bigger raw numbers.
    cs = item("CS1", sell_uom="CS", lb_per_case=20.0)
    lb = item("LB1", sell_uom="LB", lb_per_case=None)
    sales = [s for s in steady_sales("CS1", 1.0)] + [s for s in steady_sales("LB1", 20.0)]
    sales += [
        SaleInput("CS1", f"XMAS-{d}", "x", d, d, 1.0, False)
        for d in (date(2025, 12, k) for k in range(1, 32))
    ]
    index = compute_seasonal_index([cs, lb], real_demand_by_day(sales), {}, RULES)["Shrimp"]
    assert index[12] / index[6] == pytest.approx(1.5, rel=0.01)


def test_seasonal_index_is_clamped() -> None:
    sales = [
        SaleInput("X", f"S{d}", "x", d, d, 100.0, False) for d in (date(2025, 12, k) for k in range(1, 32))
    ]
    index = compute_seasonal_index([item()], real_demand_by_day(sales), {}, RULES)["Shrimp"]
    assert index[12] == RULES.seasonal_index_max and index[6] == RULES.seasonal_index_min


def test_T23_stockout_days_excluded_from_rate() -> None:
    # 2 cs/day, except a 20-day stockout inside the 8-week window when sales were zero.
    out_start, out_end = AS_OF - timedelta(days=30), AS_OF - timedelta(days=11)
    sales = [s for s in steady_sales(per_day=2.0) if not out_start <= s.order_date <= out_end]
    out = stockout_days([StockoutInput("X", out_start, out_end)])
    with_window = demand_profile(
        real_demand_by_day(sales)["X"], out["X"], {m: 1.0 for m in range(1, 13)}, RULES
    )
    without = demand_profile(real_demand_by_day(sales)["X"], set(), {m: 1.0 for m in range(1, 13)}, RULES)
    assert with_window.base_rate_per_day == pytest.approx(2.0)  # the stockout didn't look like low demand
    assert with_window.base_days == 56 - 20
    assert without.base_rate_per_day < 1.5  # what would happen without the seed


# ---- Supply: arrival dates (§6.6, T26, A18, Dana Q3) ---------------------------------------


def test_T26_po_eta_rederived() -> None:
    # Ordered Nov 2 from Vietnam (84 days): BlueTide's Dec 28 is the stale 8-week date -> Jan 25.
    line = po(ordered=date(2026, 11, 2), bluetide=date(2026, 12, 28))
    arrival = po_arrival(line, 84, None, RULES)
    assert arrival.eta == date(2027, 1, 25) and arrival.eta_source == "Real lead time"
    assert "BlueTide date is earlier than the real lead time allows" in arrival.flags
    # A BlueTide date LATER than the lead time allows is kept as is.
    assert po_arrival(
        po(ordered=date(2026, 11, 2), bluetide=date(2026, 12, 20)), 14, None, RULES
    ).eta == date(2026, 12, 20)


def test_late_po_is_not_counted_and_on_or_before_today_counts_as_late() -> None:
    # Calamari: ordered Aug 24 + 84 days = Nov 16 = today -> late (A18), no date (Dana Q3).
    arrival = po_arrival(po(ordered=date(2026, 8, 24), bluetide=date(2026, 10, 19)), 84, None, RULES)
    assert (arrival.is_late, arrival.eta, arrival.eta_source) == (True, None, "Late: date unknown")
    assert {"BlueTide date has passed", "Late: confirm with vendor"} <= set(arrival.flags)
    # The knob still works for a live change: assume late POs arrive in 7 days.
    assumed = po_arrival(
        po(ordered=date(2026, 8, 24), bluetide=date(2026, 10, 19)),
        84,
        None,
        replace(RULES, late_po_assumed_days=7),
    )
    assert assumed.eta == date(2026, 11, 23) and assumed.is_late


def test_dana_date_wins_over_everything() -> None:
    late = po(ordered=date(2026, 8, 10), bluetide=date(2026, 10, 5), po_no="PO-260394")
    arrival = po_arrival(late, 84, EtaOverrideInput("PO-260394", 1, date(2026, 12, 1)), RULES)
    assert (arrival.eta, arrival.eta_source, arrival.is_late) == (date(2026, 12, 1), "Set by Dana", False)


# ---- Projection and status (§6.8, T22) -----------------------------------------------------


def test_T22_open_orders_deducted_on_ship_date() -> None:
    # Same order, two ship dates (day 30 vs day 60). Everything else is identical, so any
    # difference in the projection is the ship date alone. (The order also counts as demand
    # history by its ORDER date, §6.2 / ADR-013, so we compare runs instead of hard numbers.)
    base = dict(lots=[lot(qty=500)])
    early = one(run(**base, sales=steady_sales() + [open_order(qty=60, ship=D(30))]))
    late = one(run(**base, sales=steady_sales() + [open_order(qty=60, ship=D(60))]))
    e = {pt.day: pt.stock for pt in early.confirmed.points}
    lt = {pt.day: pt.stock for pt in late.confirmed.points}
    assert e[D(29)] == pytest.approx(lt[D(29)])  # not shipped yet in either
    assert e[D(30)] == pytest.approx(lt[D(30)] - 60)  # left the building on day 30
    assert e[D(60)] == pytest.approx(lt[D(60)])  # both shipped by day 60
    # An overdue ship date counts on day 0.
    overdue = one(run(**base, sales=steady_sales() + [open_order(qty=60, ship=D(-3))]))
    first = one(run(**base, sales=steady_sales() + [open_order(qty=60, ship=D(0))]))
    assert overdue.confirmed.points[0].stock == pytest.approx(first.confirmed.points[0].stock)


@pytest.mark.parametrize(
    ("stock", "expected"),
    [
        (10, "TOO_LATE"),  # runs out day 10, before a 14-day order lands
        (25, "ORDER_THIS_WEEK"),  # runs out day 25: order-by = 25 - 14 - 7 = day 4
        (38, "ORDER_SOON"),  # order-by day 17
        (90, "OK"),
    ],
)
def test_status_thresholds(stock: float, expected: str) -> None:
    assert one(run(lots=[lot(qty=stock)])).confirmed.status == expected


def test_no_recent_sales_is_not_in_the_order_list() -> None:
    quiet = [s for s in steady_sales() if s.order_date < AS_OF - timedelta(days=56)]
    assert one(run(sales=quiet)).confirmed.status == "NO_RECENT_SALES"


def test_order_at_least_uses_lost_sales_flooring() -> None:
    # 10 on hand, 1/day, lead 14, cycle 7, cushion 7: runs out day 10 (lost sales days 10-13 are lost,
    # not paid back). From day 14 to day 28 it needs 15 cases -> order at least 15, not 19.
    p = one(run(lots=[lot(qty=10)]))
    assert p.confirmed.order_at_least == 15
    assert p.confirmed.gap_qty == 4  # days 10, 11, 12, 13
    assert p.confirmed.back_in_stock_date == D(14)


def test_earlier_po_ends_the_shortage_before_a_new_order_could() -> None:
    # Like SHR-1620: runs out, a PO lands before a new order could, so the gap ends at the PO.
    p = one(run(lots=[lot(qty=10)], pos=[po(qty=100, ordered=D(-20), bluetide=D(12))], lead=30))
    assert p.confirmed.status == "TOO_LATE"
    assert p.confirmed.back_in_stock_date == D(12)
    assert any("when stock already on the way lands" in s for s in p.explanation)


def test_weeks_of_cover() -> None:
    assert one(run(lots=[lot(qty=70)])).weeks_of_cover == pytest.approx(10.0)


# ---- Late POs: a separate bucket and the "only covered by a late PO" flag (Dana Q3, P0 #2a) ----


def test_item_only_covered_by_a_late_po_is_called_out() -> None:
    late = po(qty=500, ordered=D(-100), bluetide=D(-40), po_no="PO-LATE")
    p = one(run(lots=[lot(qty=20)], pos=[late]))
    assert p.confirmed.status == "ORDER_THIS_WEEK"  # late stock is NOT counted
    assert [line.reference for line in p.late_incoming] == ["PO-LATE line 1"] and p.incoming == ()
    assert p.if_late_arrive is not None and p.if_late_arrive.status == "OK"
    assert p.covered_only_by_late_po
    assert any("Only covered by the late PO" in s for s in p.explanation)


def test_late_po_not_enough_is_not_flagged_as_covering() -> None:
    late = po(qty=5, ordered=D(-100), bluetide=D(-40))
    p = one(run(lots=[lot(qty=10)], pos=[late]))
    assert p.if_late_arrive is not None and p.if_late_arrive.status != "OK"
    assert not p.covered_only_by_late_po


# ---- Dana's knowledge: handled notes and overrides (§6.10, §6.4) ----------------------------


def test_handled_note_with_qty_and_date_counts_as_incoming() -> None:
    note = HandledNoteInput(1, "X", 100.0, D(9), "Ordered by phone Tuesday", AS_OF)
    p = one(run(lots=[lot(qty=10)], notes=[note]))
    assert [line.source for line in p.incoming] == ["handled_note"]
    assert p.confirmed.status == "OK"
    assert p.active_handled_note == note


def test_handled_note_without_qty_only_changes_display() -> None:
    note = HandledNoteInput(1, "X", None, None, "Called the vendor", AS_OF)
    p = one(run(lots=[lot(qty=10)], notes=[note]))
    assert p.incoming == () and p.confirmed.status == "TOO_LATE" and p.active_handled_note == note


def test_inactive_items_are_never_planned_but_dana_can_revive_one() -> None:
    dormant = item(lifecycle_status="dormant", lifecycle_reason="No real sales since Apr 16, 2026")
    p = one(run(items=[dormant], lots=[lot(qty=10)]))
    assert p.confirmed.status == "NOT_PLANNED" and p.explanation == ("No real sales since Apr 16, 2026",)
    revived = one(run(items=[dormant], lots=[lot(qty=10)], item_settings=[ItemSettingInput("X", "active")]))
    assert revived.confirmed.status == "TOO_LATE"


def test_cushion_override_for_one_item() -> None:
    p = one(run(lots=[lot(qty=38)], item_settings=[ItemSettingInput("X", safety_days_override=21)]))
    assert p.safety_days == 21 and p.confirmed.status == "ORDER_THIS_WEEK"  # order-by moved two weeks earlier


# ---- Stuck with (§6.11, T15, T30) ----------------------------------------------------------


def _stuck(result, code="X"):
    return next((s for s in result.stuck if s.item_code == code), None)


def test_T15_six_month_line_flagged() -> None:
    inside = lot(qty=10, expiry=date(2027, 5, 15), lot_no="A")  # one day inside AS_OF + 6 months
    outside = lot(qty=10, expiry=date(2027, 5, 16), lot_no="B")  # on the line: not inside
    s = _stuck(run(lots=[inside, outside], sales=steady_sales(per_day=5)))
    assert s is not None and [lot_.lot_no for lot_ in s.lots] == ["A"]
    assert s.lots[0].primary_tag == "INSIDE_SIX_MONTHS"


def test_T30_age_uses_expiry_not_received() -> None:
    # The engine only ever sees the expiry date: an old lot (packed long ago) with a far expiry isn't stuck.
    assert _stuck(run(lots=[lot(qty=10, expiry=date(2028, 6, 1))], sales=steady_sales(per_day=5))) is None


def test_harbor_alone_is_not_stuck_but_long_harbor_stock_is() -> None:
    needed = run(lots=[lot(qty=20, location="HCS")], sales=steady_sales(per_day=2))  # 1.4 weeks of cover
    assert _stuck(needed) is None
    long_stock = _stuck(run(lots=[lot(qty=200, location="HCS")], sales=steady_sales(per_day=1)))  # 28 weeks
    assert long_stock is not None and long_stock.primary_tag == "LONG_AT_HARBOR"
    assert long_stock.lots[0].at_harbor and long_stock.value_at_cost == pytest.approx(2000.0)


def test_stuck_tag_precedence_and_harbor_first() -> None:
    dead = item(lifecycle_status="dormant")
    r = run(
        items=[dead],
        lots=[
            lot(qty=5, location="NB", lot_no="NB1"),
            lot(qty=5, location="HCS", lot_no="HCS1"),
            lot(qty=5, expiry=date(2026, 1, 1), lot_no="OLD"),
        ],
    )
    s = _stuck(r)
    assert s is not None and s.primary_tag == "EXPIRED"
    assert [x.lot_no for x in s.lots] == ["OLD", "HCS1", "NB1"]  # expired first, then Harbor before NB


def test_fresh_items_never_in_the_stuck_list() -> None:
    fresh = item(lifecycle_status="fresh_out_of_scope", sell_uom="LB")
    assert _stuck(run(items=[fresh], lots=[lot(qty=50, expiry=date(2026, 11, 1))])) is None


# ---- Trust strip ---------------------------------------------------------------------------------


def test_trust_strip_counts_what_we_did_not_count() -> None:
    late = po(qty=300, ordered=D(-100), bluetide=D(-40))
    r = run(
        lots=[
            lot(qty=50),
            lot(qty=80, location="QA-HOLD", lot_no="H"),
            lot(qty=5, location="DAMAGED", lot_no="D"),
            lot(qty=18, expiry=date(2026, 8, 30), lot_no="E"),
        ],
        pos=[late],
    )
    t = r.trust
    assert (t.on_hold, t.damaged, t.expired, t.late_po_qty) == (
        {"CS": 80},
        {"CS": 5},
        {"CS": 18},
        {"CS": 300},
    )


def test_simulation_floor_tracks_lost_sales() -> None:
    sim = simulate(2.0, {}, {}, [1.0] * 6, floor_before_day=4)
    assert (
        sim.end_of_day_stock[:4] == [1.0, 0.0, 0.0, 0.0]
        and sim.lost_before_floor == 2.0
        and sim.last_lost_day == 3
    )


def test_open_orders_in_selling_rate_switch() -> None:
    # A 60-case pre-booking: counted in the rate by default (spec §6.2), or only on its ship date.
    sales = steady_sales() + [open_order(qty=60, ship=D(30))]
    counted = one(run(sales=sales, lots=[lot(qty=500)]))
    once = one(run(replace(RULES, open_orders_in_selling_rate=False), sales=sales, lots=[lot(qty=500)]))
    assert counted.demand.base_rate_per_day > once.demand.base_rate_per_day == pytest.approx(1.0)
    assert counted.committed_total == once.committed_total == 60  # deducted on ship date either way
