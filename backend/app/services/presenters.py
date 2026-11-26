"""Turn engine results (planning/types.py) into API responses (api/v1/schemas.py).

Pure mapping: no database access and no business decisions. Anything that changes a number
belongs in planning/. This is where the Monday screen is ASSEMBLED: which items go in which
section, in what order, and the summary sentences (§9.2).

How to change this ("show a new number on the dashboard", BUILD_PROMPT §17): compute it in the
engine, add it to the schema, set it here.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from app.api.v1 import schemas as s
from app.db import models as m
from app.planning.types import IncomingLine, ItemPlan, PlanResult, StuckItem, TrustStrip

URGENT = ("TOO_LATE", "ORDER_THIS_WEEK", "ORDER_SOON")
STATUS_RANK = {status: rank for rank, status in enumerate((*URGENT, "OK", "NO_RECENT_SALES", "NOT_PLANNED"))}


def handled_out(flag: m.HandledFlag, bluetide_now_shows: list[str] | None = None) -> s.HandledNoteOut:
    return s.HandledNoteOut(
        id=flag.id,
        item_code=flag.item_code,
        qty=float(flag.qty) if flag.qty is not None else None,
        eta=flag.eta,
        note=flag.note,
        created_at=flag.created_at,
        created_by=flag.created_by,
        counts_as_incoming=flag.qty is not None and flag.eta is not None,
        bluetide_now_shows=bluetide_now_shows or [],
    )


def card(p: ItemPlan, as_of: date, horizon_days: int, handled: s.HandledNoteOut | None) -> s.ItemCard:
    c = p.confirmed
    return s.ItemCard(
        item_code=p.item.item_code,
        description=p.item.description,
        category=p.item.category,
        sell_uom=p.item.sell_uom,
        vendor_code=p.item.vendor_code,
        vendor_name=p.vendor_name,
        country=p.vendor_country,
        lifecycle_status=p.lifecycle_status,
        status=c.status,
        run_out_date=c.run_out_date,
        order_by_date=c.order_by_date,
        new_order_arrival=p.new_order_arrival,
        back_in_stock_date=c.back_in_stock_date,
        lead_time_days=p.lead_time_days,
        cushion_days=p.safety_days,
        order_at_least=c.order_at_least,
        short_qty=c.gap_qty,
        sellable=p.on_hand.sellable,
        on_hold=p.on_hand.on_hold,
        promised_to_customers=p.committed_total,
        on_the_way=sum(line.qty for line in p.incoming),
        late_qty=sum(line.qty for line in p.late_incoming),
        weeks_of_cover=p.weeks_of_cover,
        covered_only_by_late_po=p.covered_only_by_late_po,
        if_late_arrive_status=p.if_late_arrive.status if p.if_late_arrive else None,
        if_late_arrive_order_at_least=p.if_late_arrive.order_at_least if p.if_late_arrive else None,
        handled_note=handled,
        runway=s.RunwayOut(
            stock_lasts_days=(c.run_out_date - as_of).days if c.run_out_date else None,
            lead_time_days=p.lead_time_days,
            cushion_days=p.safety_days,
            horizon_days=horizon_days,
        ),
    )


def stuck_out(item: StuckItem) -> s.StuckItemOut:
    return s.StuckItemOut(
        item_code=item.item_code,
        description=item.description,
        sell_uom=item.sell_uom,
        primary_tag=item.primary_tag,
        qty=item.qty,
        qty_at_harbor=item.qty_at_harbor,
        value_at_cost=round(item.value_at_cost, 2),
        lots=[
            s.StuckLotOut(
                lot_no=lot.lot_no,
                location_code=lot.location_code,
                qty=lot.qty,
                expiry_date=lot.expiry_date,
                value_at_cost=round(lot.value_at_cost, 2) if lot.value_at_cost is not None else None,
                tags=list(lot.tags),
                primary_tag=lot.primary_tag,
                at_harbor=lot.at_harbor,
            )
            for lot in item.lots
        ],
    )


def trust_out(t: TrustStrip) -> s.TrustStripOut:
    return s.TrustStripOut(
        on_hold=t.on_hold,
        damaged=t.damaged,
        expired=t.expired,
        old_zz_stock=t.legacy,
        late_po_qty=t.late_po_qty,
    )


def _money(value: float) -> str:
    return f"${value:,.0f}"


def _qty_by_unit(by_unit: dict[str, float]) -> str:
    return " + ".join(f"{round(v):,} {u.lower()}" for u, v in sorted(by_unit.items()) if v)


def summary_sentences(
    too_late: int,
    this_week: int,
    soon: int,
    inside_value: float,
    inside_harbor: float,
    trust: TrustStrip,
    covered_by_late: int,
) -> list[str]:
    """The Monday screen's opening lines (§9.2), in Dana's words."""
    items = lambda n: f"{n} item{'s' if n != 1 else ''}"  # noqa: E731
    sentences = []
    first = (
        f"{items(too_late)} will run out before a new order can arrive."
        if too_late
        else ("Nothing will run out before a new order can arrive.")
    )
    more = []
    if this_week:
        more.append(f"{this_week} more need an order this week")
    if soon:
        more.append(f"{soon} should be ordered soon")
    sentences.append(first + (" " + " and ".join(more) + "." if more else ""))
    if covered_by_late:
        sentences.append(f"{items(covered_by_late)} would only be covered if a late PO shows up.")
    if inside_value:
        sentences.append(
            f"{_money(inside_value)} of stock is inside the six-month line, "
            f"{_money(inside_harbor)} of it at Harbor."
        )
    parts = [
        (trust.on_hold, "on hold"),
        (trust.damaged, "damaged"),
        (trust.expired, "expired"),
        (trust.legacy, "of old ZZ stock"),
        (trust.late_po_qty, "on late POs with no arrival date"),
    ]
    shown = [f"{_qty_by_unit(v)} {label}" for v, label in parts if any(v.values())]
    if shown:
        sentences.append("Not counted: " + ", ".join(shown) + ".")
    return sentences


def late_line_out(p: ItemPlan, line: IncomingLine) -> s.LateLineOut:
    po_no, line_no = _po_ref(line)
    return s.LateLineOut(
        item_code=p.item.item_code,
        description=p.item.description,
        sell_uom=p.item.sell_uom,
        po_no=po_no,
        line_no=line_no,
        reference=line.reference,
        qty=line.qty,
        bluetide_date=line.bluetide_date,
        flags=list(line.flags),
    )


def _po_ref(line: IncomingLine) -> tuple[str | None, int | None]:
    """'PO-260443 line 1' -> ('PO-260443', 1); notes have no PO."""
    if line.source != "po":
        return None, None
    po_no, _, rest = line.reference.partition(" line ")
    return po_no, int(rest) if rest.isdigit() else None


def incoming_out(line: IncomingLine) -> s.IncomingOut:
    po_no, line_no = _po_ref(line)
    return s.IncomingOut(
        source=line.source,
        reference=line.reference,
        po_no=po_no,
        line_no=line_no,
        qty=line.qty,
        eta=line.eta,
        eta_source=line.eta_source,
        bluetide_date=line.bluetide_date,
        is_late=line.is_late,
        flags=list(line.flags),
    )


def dashboard(
    result: PlanResult,
    *,
    horizon_days: int,
    handled_by_item: dict[str, s.HandledNoteOut],
    snapshot_date: date | None,
    last_load_at: object,
) -> s.DashboardOut:
    as_of = result.as_of
    planned = [p for p in result.items if p.lifecycle_status == "active"]
    order, handled, fine = [], [], []
    for p in sorted(
        planned, key=lambda p: (STATUS_RANK[p.confirmed.status], p.confirmed.run_out_date or date.max)
    ):
        note = handled_by_item.get(p.item.item_code)
        row = card(p, as_of, horizon_days, note)
        if note is not None:
            handled.append(row)  # §6.10: handled items move to their own section, never hidden
        elif p.confirmed.status in URGENT:
            order.append(row)
        else:
            fine.append(row)

    late_pos = [late_line_out(p, line) for p in planned for line in p.late_incoming]
    on_hold = [
        s.OnHoldOut(
            item_code=p.item.item_code,
            description=p.item.description,
            sell_uom=p.item.sell_uom,
            qty=p.on_hand.on_hold,
        )
        for p in result.items
        if p.on_hand.on_hold > 0 and p.lifecycle_status != "fresh_out_of_scope"
    ]

    inside = sum(
        lot.value_at_cost or 0 for st in result.stuck for lot in st.lots if "INSIDE_SIX_MONTHS" in lot.tags
    )
    inside_harbor = sum(
        lot.value_at_cost or 0
        for st in result.stuck
        for lot in st.lots
        if "INSIDE_SIX_MONTHS" in lot.tags and lot.at_harbor
    )
    counts = defaultdict(int)
    for row in order:
        counts[row.status] += 1
    covered = sum(1 for p in planned if p.covered_only_by_late_po)
    summary = s.SummaryOut(
        too_late=counts["TOO_LATE"],
        order_this_week=counts["ORDER_THIS_WEEK"],
        order_soon=counts["ORDER_SOON"],
        handled=len(handled),
        fine=len(fine),
        covered_only_by_late_po=covered,
        inside_six_months_value=round(inside, 2),
        inside_six_months_value_at_harbor=round(inside_harbor, 2),
        stuck_value=round(sum(st.value_at_cost for st in result.stuck), 2),
        sentences=summary_sentences(
            counts["TOO_LATE"],
            counts["ORDER_THIS_WEEK"],
            counts["ORDER_SOON"],
            inside,
            inside_harbor,
            result.trust,
            covered,
        ),
    )
    return s.DashboardOut(
        as_of=as_of,
        data_snapshot_date=snapshot_date,
        last_load_at=last_load_at,  # type: ignore[arg-type]
        summary=summary,
        order_items=order,
        handled_items=handled,
        fine_items=fine,
        late_inventory=s.LateInventoryOut(late_pos=late_pos, on_hold=on_hold),
        stuck_items=[stuck_out(st) for st in result.stuck],
        trust_strip=trust_out(result.trust),
    )
