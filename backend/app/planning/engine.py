"""The planning engine entry point: PlanningInputs -> PlanResult (pure; ADR-004).

One call computes everything the Monday screen and the drill-down need, for every item:
on hand, promised orders, incoming (dated vs late), seasonal demand, the run-out projection
and status, "order at least", the late-PO what-if, the stuck list and the trust strip.
About 45 items × 183 days: milliseconds, so it runs on every request (ADR-004).

Late POs (Dana's Q3, 2026-11-26; P0 #2a): the status comes from the CONFIRMED scenario, which
counts only supply with a date. If an item has late POs, a second scenario counts them as if
they arrived today (the best case). When that turns a red/amber item green, the item is
"covered only by a late PO", which Dana asked to see.

Lifecycle: only ACTIVE items are planned. Legacy, discontinued, dormant and fresh items get
status NOT_PLANNED and never reach the order list (golden fact G17); their stock still feeds the
stuck list. Dana can revive an item with item_settings.lifecycle_override = "active".
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from app.config.business_rules import BusinessRules
from app.planning.demand import daily_forecast, demand_profile
from app.planning.explain import breakdown, late_po_instruction
from app.planning.projection import build_scenario
from app.planning.seasonality import compute_seasonal_index, real_demand_by_day, stockout_days
from app.planning.stuck import stuck_list
from app.planning.supply import incoming_for_item, summarize_on_hand, vendor_terms
from app.planning.types import (
    BreakdownRow,
    CommittedLine,
    HandledNoteInput,
    ItemPlan,
    OnHand,
    PlanningInputs,
    PlanResult,
    POLineInput,
    Scenario,
    TrustStrip,
)

URGENT = {"OUT_OF_STOCK", "TOO_LATE", "OVERDUE", "ORDER_THIS_WEEK", "ORDER_SOON"}


def plan(inputs: PlanningInputs, rules: BusinessRules) -> PlanResult:
    as_of = rules.as_of_date  # today (ADR-034): deadlines, expiry, when an order placed today lands
    day0 = rules.day_zero  # the data date: the projection starts here, from the counted stock
    gap = rules.days_since_data  # days between the two (0 when the count is from last night)
    horizon = rules.projection_horizon_days
    items = {i.item_code: i for i in inputs.items}
    vendors = {v.vendor_code: v for v in inputs.vendors}
    vendor_settings = {s.vendor_code: s for s in inputs.vendor_settings}
    item_settings = {s.item_code: s for s in inputs.item_settings}
    overrides = {(o.po_no, o.line_no): o for o in inputs.eta_overrides}

    lifecycle = {
        code: (
            item_settings[code].lifecycle_override
            if code in item_settings and item_settings[code].lifecycle_override
            else item.lifecycle_status
        )
        for code, item in items.items()
    }
    # What's good TODAY starts the projection (a lot that expired since the count drops out:
    # conservative); what the count itself said is shown next to the estimate.
    on_hand = summarize_on_hand(inputs.lots, inputs.locations, as_of)
    on_hand_at_count = summarize_on_hand(inputs.lots, inputs.locations, day0)
    # Selling-rate history: open orders included or not (business_rules.open_orders_in_selling_rate).
    # Either way they are deducted from stock on their ship date below (T22).
    history = [s for s in inputs.sales if rules.open_orders_in_selling_rate or not s.is_open]
    demand_by_item = real_demand_by_day(history)
    out_days = stockout_days(inputs.stockouts)
    active = [items[c] for c in items if lifecycle[c] == "active"]
    seasonal = compute_seasonal_index(active, demand_by_item, out_days, rules)

    po_by_item: dict[str, list[POLineInput]] = defaultdict(list)
    for line in inputs.po_lines:
        po_by_item[line.item_code].append(line)
    notes_by_item: dict[str, list[HandledNoteInput]] = defaultdict(list)
    for note in inputs.handled_notes:
        notes_by_item[note.item_code].append(note)
    committed_by_item: dict[str, list[CommittedLine]] = defaultdict(list)
    for sale in inputs.sales:
        if sale.is_open:  # T22: promised to a customer, still in the building
            committed_by_item[sale.item_code].append(
                CommittedLine(sale.order_no, sale.customer_name, sale.ship_date, sale.qty)
            )

    plans: list[ItemPlan] = []
    for code, item in sorted(items.items()):
        vendor = vendors.get(item.vendor_code)
        lead, lead_source, safety, cycle = vendor_terms(
            vendor, vendor_settings.get(item.vendor_code), item_settings.get(code), rules
        )
        stock = on_hand.get(code, OnHand())
        committed = tuple(
            sorted(committed_by_item.get(code, []), key=lambda c: (c.ship_date or day0, c.order_no))
        )
        notes = sorted(notes_by_item.get(code, []), key=lambda n: (n.created_on, n.note_id))
        incoming, late = incoming_for_item(po_by_item.get(code, []), lead, overrides, notes, rules)
        index = seasonal.get(item.category, {m: 1.0 for m in range(1, 13)})
        profile = demand_profile(demand_by_item.get(code, {}), out_days.get(code, set()), index, rules)
        forecast = daily_forecast(profile, day0, horizon + gap)  # from the data date to 26 weeks after today
        if lifecycle[code] != "active":
            forecast = [0.0] * len(forecast)

        # Days are counted from the data date (day 0); today is day `gap`.
        shipments: dict[int, float] = defaultdict(float)
        for line in committed:
            offset = (line.ship_date - day0).days if line.ship_date else 0
            if offset <= horizon + gap:
                shipments[max(0, offset)] += line.qty  # T22: overdue shipments count on day 0
        arrivals: dict[int, float] = defaultdict(float)
        for line in incoming:
            assert line.eta is not None
            offset = (line.eta - day0).days
            if offset <= horizon + gap:
                arrivals[max(0, offset)] += line.qty

        confirmed = build_scenario(
            stock.sellable, arrivals, shipments, forecast, lead, safety, cycle, rules, gap
        )
        if_late: Scenario | None = None
        if late:
            with_late = dict(arrivals)  # the best case: every late PO shows up TODAY
            with_late[gap] = with_late.get(gap, 0.0) + sum(line.qty for line in late)
            if_late = build_scenario(
                stock.sellable, with_late, shipments, forecast, lead, safety, cycle, rules, gap
            )

        if lifecycle[code] != "active":
            confirmed = _not_planned(confirmed)
            if_late = None
        elif profile.base_rate_per_day == 0 and not committed and confirmed.status not in URGENT:
            confirmed = _with_status(confirmed, "NO_RECENT_SALES")

        covered_only = bool(if_late is not None and confirmed.status in URGENT and if_late.status == "OK")
        cover_days = forecast[gap : gap + rules.cover_forecast_days]  # measured from today
        mean_daily = sum(cover_days) / len(cover_days) if cover_days else 0.0
        weeks_of_cover = confirmed.stock_now / (mean_daily * 7) if mean_daily > 0 else None
        # Between the count and today (estimated): expected sales and the orders due to ship in it.
        sales_expected_since = sum(forecast[:gap])
        orders_scheduled_since = sum(qty for d, qty in shipments.items() if d < gap)
        arrived_since = sum(qty for d, qty in arrivals.items() if d < gap)
        # Whole units on screen (an estimate, not a count); "sold since" is derived from the rounded
        # estimate so the item page's bridge adds up exactly: count - expired - sold = now.
        sold_and_shipped_since = max(0.0, stock.sellable + arrived_since - round(confirmed.stock_now))
        new_order_arrival = as_of + timedelta(days=lead)
        vendor_name = vendor.name if vendor else item.vendor_code

        plans.append(
            ItemPlan(
                item=item,
                lifecycle_status=lifecycle[code],
                vendor_name=vendor_name,
                vendor_country=vendor.country if vendor else None,
                lead_time_days=lead,
                lead_time_source=lead_source,
                lead_time_days_system=vendor.lead_time_days_system if vendor else None,
                safety_days=safety,
                order_cycle_days=cycle,
                on_hand=stock,
                on_hand_at_count=on_hand_at_count.get(code, OnHand()),
                data_date=day0,
                sold_and_shipped_since=round(sold_and_shipped_since, 3),
                sales_expected_since=round(sales_expected_since, 3),
                orders_scheduled_since=round(orders_scheduled_since, 3),
                committed_total=sum(c.qty for c in committed),
                promised_still=sum(
                    c.qty for c in committed if max(0, ((c.ship_date or day0) - day0).days) >= gap
                ),
                committed_lines=committed,
                incoming=tuple(incoming),
                late_incoming=tuple(late),
                demand=profile,
                weeks_of_cover=weeks_of_cover,
                new_order_arrival=new_order_arrival,
                confirmed=confirmed,
                if_late_arrive=if_late,
                covered_only_by_late_po=covered_only,
                active_handled_note=notes[-1] if notes else None,
                breakdown=breakdown(
                    as_of=as_of,
                    data_date=day0,
                    sell_uom=item.sell_uom,
                    on_hand=stock,
                    on_hand_at_count=on_hand_at_count.get(code, OnHand()),
                    sold_and_shipped_since=sold_and_shipped_since,
                    sales_expected_since=sales_expected_since,
                    orders_scheduled_since=orders_scheduled_since,
                    committed=committed,
                    incoming=tuple(incoming),
                    late=tuple(late),
                    demand=profile,
                    category=item.category,
                    vendor_name=vendor_name,
                    lead_time_days=lead,
                    safety_days=safety,
                    horizon_days=horizon,
                    new_order_arrival=new_order_arrival,
                    confirmed=confirmed,
                    if_late_arrive=if_late,
                )
                if lifecycle[code] == "active"
                else (BreakdownRow("not_planned", "Not planned", detail=item.lifecycle_reason),),
                # One instruction instead of two contradicting lines (Dana Q3; ADR-033).
                instruction=late_po_instruction(item.sell_uom, confirmed.order_at_least, tuple(late))
                if covered_only
                else None,
            )
        )

    stuck = stuck_list(
        inputs.lots,
        items,
        lifecycle,
        {p.item.item_code: p.weeks_of_cover for p in plans},
        inputs.locations,
        rules,
    )
    return PlanResult(
        as_of=as_of,
        items=tuple(plans),
        stuck=tuple(stuck),
        trust=_trust_strip(plans, inputs),
        seasonal_index=seasonal,
    )


def _with_status(scenario: Scenario, status: str) -> Scenario:
    from dataclasses import replace

    return replace(scenario, status=status)  # type: ignore[arg-type]


def _not_planned(scenario: Scenario) -> Scenario:
    from dataclasses import replace

    return replace(
        scenario,
        status="NOT_PLANNED",
        run_out_date=None,
        order_by_date=None,
        order_at_least=0.0,
        gap_qty=0.0,
        back_in_stock_date=None,
    )


def _trust_strip(plans: list[ItemPlan], inputs: PlanningInputs) -> TrustStrip:
    """What BlueTide would call "on hand" that we did not count, grouped by unit (§9.2)."""
    on_hold: dict[str, float] = defaultdict(float)
    damaged: dict[str, float] = defaultdict(float)
    expired: dict[str, float] = defaultdict(float)
    legacy: dict[str, float] = defaultdict(float)
    late: dict[str, float] = defaultdict(float)
    for p in plans:
        u = p.item.sell_uom
        if p.lifecycle_status == "fresh_out_of_scope":
            continue
        on_hold[u] += p.on_hand.on_hold
        damaged[u] += p.on_hand.damaged
        if p.lifecycle_status == "legacy":
            legacy[u] += p.on_hand.expired + p.on_hand.sellable
        else:
            expired[u] += p.on_hand.expired
        late[u] += sum(line.qty for line in p.late_incoming)
    clean = lambda d: {k: v for k, v in d.items() if v}  # noqa: E731
    return TrustStrip(clean(on_hold), clean(damaged), clean(expired), clean(legacy), clean(late))
