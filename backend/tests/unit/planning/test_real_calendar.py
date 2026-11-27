"""Today is Boston's calendar date, the data is the last upload's (ADR-034, Ishan 2026-11-26).

The projection starts at the data date (the day after the stock count) from the counted stock; deadlines
are judged against today. Between the two the engine estimates: counted stock - expected sales - scheduled
customer shipments + confirmed arrivals, with sales lost while out of stock written off (§6.9).

Ishan's example: "if Dana doesn't log anything for 3 weeks and something says to order by November 22nd, it
should say that it is overdue or out of stock with some sort of indicator that it is urgent."
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from app.planning.types import EtaOverrideInput, ItemPlan
from tests.unit.planning.builders import AS_OF, RULES, lot, one, open_order, po, run, steady_sales

DATA = AS_OF  # Mon Nov 16: the day after Sunday's count
D = lambda n: DATA + timedelta(days=n)  # noqa: E731


def at(days_later: int):
    """Rules for a visit `days_later` days after the data date, with no upload in between."""
    return replace(RULES, as_of_date=D(days_later), data_date=DATA)


def by_key(p: ItemPlan) -> dict[str, object]:
    return {row.key: row for row in p.breakdown}


# ---- Ishan's example: three weeks with no upload ------------------------------------------


def test_order_by_nov_22_three_weeks_later_is_overdue_by_15_days() -> None:
    # 1 case a day, 41 cases: runs out day 41 (Dec 27). Lead 14 + a 21-day cushion: order by day 6 (Nov 22).
    # On Dec 7 an order still lands Dec 21, before Dec 27, so it's OVERDUE (not too late), by 15 days.
    p = one(run(rules=at(21), lots=[lot(qty=41)], safety=21))
    assert p.confirmed.order_by_date == D(6) and p.confirmed.order_by_date.isoformat() == "2026-11-22"
    assert p.confirmed.status == "OVERDUE"
    assert (at(21).as_of_date - p.confirmed.order_by_date).days == 15
    # On Nov 16 (the data date) the same item was fine to order within the week.
    assert one(run(rules=at(0), lots=[lot(qty=41)], safety=21)).confirmed.status == "ORDER_THIS_WEEK"


def test_order_by_nov_22_with_the_usual_cushion_is_too_late_three_weeks_later() -> None:
    # Lead 14 + cushion 7: order by Nov 22 means it runs out Dec 13; an order on Dec 7 lands Dec 21.
    p = one(run(rules=at(21), lots=[lot(qty=27)]))
    assert p.confirmed.order_by_date == D(6) and p.confirmed.status == "TOO_LATE"
    assert p.confirmed.run_out_date == D(27)
    assert p.confirmed.back_in_stock_date == D(21 + 14)  # the new order placed today
    assert p.confirmed.gap_qty == pytest.approx(35 - 27)  # demand missed from Dec 13 until Dec 21


def test_stock_that_ran_out_since_the_count_is_out_of_stock_now() -> None:
    # 15 cases at 1 a day, no upload for 3 weeks: gone on day 15 (Dec 1), estimated out of stock today.
    p = one(run(rules=at(21), lots=[lot(qty=15)]))
    assert p.confirmed.status == "OUT_OF_STOCK" and p.confirmed.run_out_date == D(15)
    assert p.confirmed.stock_now == 0  # the shelf can't go below zero: lost sales are lost
    assert p.on_hand.sellable == 15  # the count as BlueTide reported it (nothing expired)
    assert p.confirmed.back_in_stock_date == D(21 + 14)
    assert p.confirmed.order_at_least > 0
    assert by_key(p)["runs_out"].label.startswith("Out of stock since")


# ---- The estimate between the count and today ---------------------------------------------


def test_the_estimate_is_the_count_minus_expected_sales_and_scheduled_orders() -> None:
    sales = steady_sales() + [open_order(qty=20, ship=D(3)), open_order(qty=30, ship=D(10))]
    p = one(run(rules=at(7), lots=[lot(qty=100)], sales=sales))
    assert p.on_hand_at_count.sellable == 100
    assert p.sales_expected_since == pytest.approx(7)  # 7 days at 1 a day
    assert p.orders_scheduled_since == 20  # Nov 19's order shipped before today; Nov 26's hasn't
    assert p.confirmed.stock_now == pytest.approx(100 - 7 - 20)
    assert p.sold_and_shipped_since == pytest.approx(27)
    assert p.promised_still == 30  # only what's still to ship counts as promised now
    rows = by_key(p)
    assert rows["at_count"].qty == 100 and rows["at_count"].on == DATA - timedelta(days=1)
    assert rows["sold_since"].qty == pytest.approx(27)
    assert rows["can_sell_now"].qty == pytest.approx(73)
    assert "can_sell" not in rows


def test_the_chart_starts_today_and_continues_from_the_estimate() -> None:
    p = one(run(rules=at(7), lots=[lot(qty=100)]))
    assert p.confirmed.points[0].day == D(7)
    assert p.confirmed.points[0].stock == pytest.approx(100 - 8)  # end of today: 8 days of sales
    assert len(p.confirmed.points) == RULES.projection_horizon_days + 1


def test_weeks_of_cover_comes_from_the_estimate_not_the_count() -> None:
    p = one(run(rules=at(14), lots=[lot(qty=70)]))
    assert p.weeks_of_cover == pytest.approx(8.0)  # 56 cases left at 1 a day


def test_a_new_order_placed_today_lands_lead_time_after_today() -> None:
    p = one(run(rules=at(10), lots=[lot(qty=100)]))
    assert p.new_order_arrival == D(10 + 14)


def test_a_lot_that_expired_since_the_count_isnt_sellable_today() -> None:
    lots = [lot(qty=40, lot_no="OLD", expiry=D(3)), lot(qty=60, lot_no="NEW")]
    p = one(run(rules=at(7), lots=lots))
    assert p.on_hand_at_count.sellable == 100  # the count: both lots were good on Nov 16
    assert p.on_hand.sellable == 60 and p.on_hand.expired == 40  # today: the old lot is past its date
    assert by_key(p)["expired_since"].qty == 40


# ---- Supply between the count and today ----------------------------------------------------


def test_a_po_due_since_the_count_isnt_counted_until_an_upload_confirms_it() -> None:
    # Ordered 10 days before the count, 14-day lead time: due day 4 (Nov 20). Today is day 7.
    due = po(qty=500, ordered=D(-10), bluetide=D(4), po_no="PO-DUE")
    p = one(run(rules=at(7), lots=[lot(qty=30)], pos=[due]))
    assert p.incoming == ()  # Ishan (2026-11-26): don't count it
    [line] = p.late_incoming
    assert line.eta is None and line.eta_source == "Due since your last upload"
    assert any(f.startswith("Due since your last upload") for f in line.flags)
    assert p.confirmed.status != "OK"  # without it, 30 cases don't last
    # On the data date itself the same PO is simply on the way.
    same_day = one(run(rules=at(0), lots=[lot(qty=30)], pos=[due]))
    assert [x.eta for x in same_day.incoming] == [D(4)]


def test_a_po_still_due_after_today_is_counted_on_its_day() -> None:
    later = po(qty=500, ordered=D(-10), bluetide=D(12), po_no="PO-LATER")
    p = one(run(rules=at(7), lots=[lot(qty=30)], pos=[later]))
    assert [x.eta for x in p.incoming] == [D(12)] and p.late_incoming == ()


def test_danas_date_that_has_passed_isnt_counted() -> None:
    late = po(qty=500, ordered=D(-100), bluetide=D(-40), po_no="PO-LATE")
    mine = EtaOverrideInput("PO-LATE", 1, D(5))  # she set Nov 21; today is Nov 23
    p = one(run(rules=at(7), lots=[lot(qty=30)], pos=[late], overrides=[mine]))
    assert p.incoming == ()
    [line] = p.late_incoming
    assert line.eta_source == "Your date has passed"
    # Before her date, it counts.
    before = one(run(rules=at(3), lots=[lot(qty=30)], pos=[late], overrides=[mine]))
    assert [x.eta for x in before.incoming] == [D(5)]


# ---- No gap: exactly as before ---------------------------------------------------------------


def test_with_no_gap_the_numbers_are_the_same_as_without_a_data_date() -> None:
    kw = {
        "lots": [lot(qty=45)],
        "sales": steady_sales() + [open_order(qty=12, ship=D(4))],
        "pos": [po(qty=80, ordered=D(-5), bluetide=D(30))],
    }
    a, b = one(run(**kw)), one(run(rules=at(0), **kw))
    assert a.confirmed == b.confirmed
    assert a.breakdown == b.breakdown
    assert a.confirmed.stock_now == 45 and a.sales_expected_since == 0
