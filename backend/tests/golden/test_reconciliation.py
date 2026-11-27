"""The chart reconciles with its parts (ADR-033), on the REAL BlueTide exports.

For several items and dates X, the item page's stock line must equal what Dana can add up herself:

    can sell now
  - promised orders shipping on or before X      (an overdue ship date counts on day 0, T22)
  + counted arrivals on or before X               (dated POs and handled notes; late POs aren't counted)
  - forecast demand through X
  + sales lost while out of stock, through X      (lost sales aren't paid back when stock lands, §6.9)
  = the chart's stock on X

The parts come from the plan's own fields (on_hand, committed_lines, incoming, demand), so this proves
nothing is counted twice or left out between the numbers on screen and the chart.

With a gap between the count and today (ADR-034), the same sum runs from the data date: the chart's
first point is today, and "can sell now (estimated)" is the sum at the end of yesterday.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from app.config.business_rules import BusinessRules
from app.loader.pipeline import build_dataset
from app.loader.read_raw import read_all_raw
from app.loader.reference import load_reference
from app.planning.demand import daily_forecast
from app.planning.engine import plan
from app.planning.types import ItemPlan, PlanResult
from app.services.planning_inputs import inputs_from_dataset

RULES = BusinessRules()  # AS_OF 2026-11-16
# Eleven days with no upload: the count of Sun Nov 15, viewed on Fri Nov 27 (ADR-034).
LATER = replace(RULES, as_of_date=RULES.as_of_date + timedelta(days=11), data_date=RULES.as_of_date)
ITEMS = ["SHR-1620", "LOB-T56", "SAL-POR6", "CRAB-SNW5", "SHR-2125"]
DAYS = [0, 7, 30, 60, 120]


def _plan(rules: BusinessRules) -> PlanResult:
    loaded = build_dataset(read_all_raw(), load_reference(), RULES)  # the load itself is Nov 16's
    return plan(inputs_from_dataset(loaded.dataset, load_reference().vendor_settings), rules)


@pytest.fixture(scope="module")
def result() -> PlanResult:
    return _plan(RULES)


@pytest.fixture(scope="module")
def later() -> PlanResult:
    return _plan(LATER)


def _parts(p: ItemPlan, x: int, rules: BusinessRules = RULES) -> tuple[float, float, float, float, float]:
    """(can sell, promised shipping by X, arrivals by X, forecast through X, lost through X), X days after
    TODAY, summed from the data date (day 0; today is day `gap`)."""
    day0, gap = rules.day_zero, rules.days_since_data
    last = gap + x
    forecast = daily_forecast(p.demand, day0, rules.projection_horizon_days + gap)

    def day(d: object) -> int:
        return max(0, ((d or day0) - day0).days)  # type: ignore[operator]

    promised = sum(c.qty for c in p.committed_lines if day(c.ship_date) <= last)
    arrivals = sum(line.qty for line in p.incoming if line.eta and day(line.eta) <= last)
    # Lost sales: before an order placed today could land, a day's demand the shelf can't meet is lost.
    shelf, lost = p.on_hand.sellable, 0.0
    for d in range(last + 1):
        shelf += sum(line.qty for line in p.incoming if line.eta and day(line.eta) == d)
        shelf -= sum(c.qty for c in p.committed_lines if day(c.ship_date) == d)
        shelf -= forecast[d]
        if d < gap + p.lead_time_days and shelf < 0:
            lost += -shelf
            shelf = 0.0
    return p.on_hand.sellable, promised, arrivals, sum(forecast[: last + 1]), lost


@pytest.mark.parametrize("code", ITEMS)
@pytest.mark.parametrize("x", DAYS)
def test_the_chart_equals_can_sell_minus_promised_plus_arrivals_minus_forecast_plus_lost(
    result: PlanResult, code: str, x: int
) -> None:
    p = next(i for i in result.items if i.item.item_code == code)
    can_sell, promised, arrivals, forecast, lost = _parts(p, x)
    chart = p.confirmed.points[x]
    assert chart.day == RULES.as_of_date + timedelta(days=x)
    assert can_sell - promised + arrivals - forecast + lost == pytest.approx(chart.stock, abs=0.01)


def test_with_no_stockout_nothing_is_lost_and_the_sum_is_plain(result: PlanResult) -> None:
    p = next(i for i in result.items if i.item.item_code == "SAL-POR6")  # lasts beyond the chart
    assert p.confirmed.run_out_date is None
    for x in DAYS:
        can_sell, promised, arrivals, forecast, lost = _parts(p, x)
        assert lost == 0
        assert can_sell - promised + arrivals - forecast == pytest.approx(
            p.confirmed.points[x].stock, abs=0.01
        )


def test_shr_1620_on_the_chart_lands_at_about_590_when_its_po_arrives(result: PlanResult) -> None:
    # The fix behind this test (ADR-033): the chart used to carry the ~382 lost cases forward and show
    # ~218 on Jan 25. Lost sales are lost, so the 600 cases land on an empty shelf.
    p = next(i for i in result.items if i.item.item_code == "SHR-1620")
    jan25 = (p.incoming[0].eta - RULES.as_of_date).days
    assert p.confirmed.points[jan25 - 1].stock == pytest.approx(0, abs=0.01)
    assert 580 < p.confirmed.points[jan25].stock < 600


@pytest.mark.parametrize("code", ITEMS)
@pytest.mark.parametrize("x", DAYS)
def test_eleven_days_after_the_count_the_chart_still_adds_up(later: PlanResult, code: str, x: int) -> None:
    p = next(i for i in later.items if i.item.item_code == code)
    can_sell, promised, arrivals, forecast, lost = _parts(p, x, LATER)
    chart = p.confirmed.points[x]
    assert chart.day == LATER.as_of_date + timedelta(days=x)  # the chart starts today
    assert can_sell - promised + arrivals - forecast + lost == pytest.approx(chart.stock, abs=0.01)


@pytest.mark.parametrize("code", ITEMS)
def test_can_sell_now_is_the_same_sum_at_the_end_of_yesterday(later: PlanResult, code: str) -> None:
    p = next(i for i in later.items if i.item.item_code == code)
    can_sell, promised, arrivals, forecast, lost = _parts(p, -1, LATER)
    assert p.confirmed.stock_now == pytest.approx(can_sell - promised + arrivals - forecast + lost, abs=0.01)
    # And the item page's bridge says the same: the count, minus what sold and shipped since, is "now".
    rows = {r.key: r for r in p.breakdown}
    assert rows["at_count"].qty == pytest.approx(p.on_hand_at_count.sellable)
    expired = rows["expired_since"].qty if "expired_since" in rows else 0
    sold = rows["sold_since"].qty if "sold_since" in rows else 0
    assert rows["can_sell_now"].qty == pytest.approx(
        p.on_hand_at_count.sellable
        - expired
        - sold
        + sum(line.qty for line in p.incoming if line.eta and line.eta < LATER.as_of_date),
        abs=0.01,
    )
