"""Database → engine inputs → planning engine → API responses (BUILD_PROMPT §8.4).

Computed on every request (ADR-004): the clean-layer inputs are cached per load run (they only
change when the loader runs), Dana's edits are read fresh, and the engine itself takes about 60 ms.
Every computation logs the item count, duration, counts by status and the rules fingerprint (§10).

How to change this: new screen data → engine (planning/) → schema → presenters.py; this module only
fetches and wires.
"""

from __future__ import annotations

import logging
import time
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import schemas as s
from app.config.business_rules import BusinessRules
from app.db import models as m
from app.errors import AppError
from app.loader.normalize import canonical_code
from app.planning.calendar import add_months
from app.planning.engine import plan
from app.planning.stuck import TAG_ORDER, lot_tags
from app.planning.supply import lot_status
from app.planning.types import LocationInput, LotInput, PlanResult, Scenario
from app.services import presenters
from app.services.planning_inputs import LoadInfo, inputs_from_db

logger = logging.getLogger(__name__)


def current_plan(session: Session, rules: BusinessRules) -> tuple[PlanResult, LoadInfo]:
    """Run the engine on the latest load plus Dana's current edits."""
    started = time.perf_counter()
    inputs, load = inputs_from_db(session, rules)
    result = plan(inputs, rules)
    logger.info(
        "plan computed",
        extra={
            "items": len(result.items),
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "by_status": dict(Counter(p.confirmed.status for p in result.items)),
            "rules_fingerprint": rules.fingerprint(),
            "load_run_id": load.load_run_id,
        },
    )
    return result, load


def handled_notes_by_item(session: Session, rules: BusinessRules) -> dict[str, s.HandledNoteOut]:
    """The newest active "I've handled this" note per item, with the "BlueTide now shows PO-x" hint."""
    flags = session.scalars(
        select(m.HandledFlag).where(m.HandledFlag.cleared_at.is_(None)).order_by(m.HandledFlag.id)
    ).all()
    if not flags:
        return {}
    # A note is written "today" in business time (AS_OF). A newer open PO for the same item means
    # BlueTide caught up: suggest clearing the note, never auto-delete it.
    newer_pos: dict[str, list[str]] = {}
    for po in session.scalars(
        select(m.PurchaseOrderLine).where(
            m.PurchaseOrderLine.status == "open", m.PurchaseOrderLine.order_date >= rules.as_of_date
        )
    ).all():
        newer_pos.setdefault(po.item_code, []).append(po.po_no)
    return {f.item_code: presenters.handled_out(f, newer_pos.get(f.item_code)) for f in flags}


def dashboard(session: Session, rules: BusinessRules) -> s.DashboardOut:
    result, load = current_plan(session, rules)
    return presenters.dashboard(
        result,
        horizon_days=rules.projection_horizon_days,
        handled_by_item=handled_notes_by_item(session, rules),
        snapshot_date=load.snapshot_date,
        last_load_at=load.finished_at,
        location_names={loc.code: loc.name for loc in session.scalars(select(m.Location)).all()},
    )


def all_items(session: Session, rules: BusinessRules) -> list[s.ItemCard]:
    result, _ = current_plan(session, rules)
    handled = handled_notes_by_item(session, rules)
    return [
        presenters.card(p, result.as_of, rules.projection_horizon_days, handled.get(p.item.item_code))
        for p in sorted(result.items, key=lambda p: p.item.item_code)
    ]


def resolve_item_code(session: Session, raw: str) -> str:
    """Find an item by code, case- and space-insensitively, or by a recorded variant ("shr-1620 ", T02)."""
    code = canonical_code(raw)
    if session.get(m.Item, code) is not None:
        return code
    alias = session.get(m.ItemAlias, raw)
    if alias is not None:
        return alias.item_code
    raise AppError(404, "item_not_found", f"We couldn't find item {raw.strip()!r}.")


def _points(scenario: Scenario) -> list[s.PointOut]:
    return [s.PointOut(day=p.day, stock=p.stock) for p in scenario.points]


def item_detail(session: Session, rules: BusinessRules, raw_code: str) -> s.ItemDetailOut:
    code = resolve_item_code(session, raw_code)
    result, _ = current_plan(session, rules)
    plan_ = next(p for p in result.items if p.item.item_code == code)
    handled = handled_notes_by_item(session, rules)
    as_of = result.as_of
    six_month_line = add_months(as_of, rules.six_month_line_months)

    locations = {loc.code: loc for loc in session.scalars(select(m.Location)).all()}
    lot_rows = session.scalars(
        select(m.InventoryLot).where(m.InventoryLot.item_code == code).order_by(m.InventoryLot.expiry_date)
    ).all()
    lots_out = []
    for row in lot_rows:
        loc = locations.get(row.location_code)
        loc_in = (
            LocationInput(loc.code, loc.is_sellable, loc.may_return_to_stock, loc.is_third_party_storage)
            if loc
            else None
        )
        qty = float(row.qty_sell_uom) if row.qty_sell_uom is not None else None
        cost = float(row.unit_cost_sell_uom) if row.unit_cost_sell_uom is not None else None
        lot_in = LotInput(code, row.location_code, row.lot_no, qty, row.expiry_date, row.is_adjustment, cost)
        counted, reason = lot_status(lot_in, loc_in, as_of, six_month_line)
        tags = (
            lot_tags(lot_in, plan_.lifecycle_status, plan_.weeks_of_cover, loc_in, rules)
            if loc_in
            and loc_in.is_sellable
            and qty
            and qty > 0
            and not row.is_adjustment
            and plan_.lifecycle_status != "fresh_out_of_scope"
            else []
        )
        lots_out.append(
            s.LotOut(
                lot_no=row.lot_no,
                location_code=row.location_code,
                location_name=loc.name if loc else row.location_code,
                qty=qty,
                qty_source=float(row.qty_source),
                uom_source=row.uom_source,
                pack_date=row.pack_date,
                expiry_date=row.expiry_date,
                received_date=row.received_date,
                unit_cost=cost,
                value_at_cost=round(qty * cost, 2) if qty is not None and cost is not None else None,
                counted=counted,
                reason=reason,
                stuck_tags=sorted(tags, key=TAG_ORDER.index),
            )
        )

    settings = session.get(m.ItemSetting, code)
    vendor = plan_.vendor_name
    flags = session.scalars(
        select(m.HandledFlag).where(m.HandledFlag.item_code == code, m.HandledFlag.cleared_at.is_(None))
    ).all()
    return s.ItemDetailOut(
        as_of=as_of,
        card=presenters.card(plan_, as_of, rules.projection_horizon_days, handled.get(code)),
        lifecycle_reason=plan_.item.lifecycle_reason,
        vendor=s.VendorTermsOut(
            vendor_code=plan_.item.vendor_code,
            vendor_name=vendor,
            country=plan_.vendor_country,
            lead_time_days=plan_.lead_time_days,
            lead_time_source=plan_.lead_time_source,
            lead_time_days_bluetide=plan_.lead_time_days_system,
            cushion_days=plan_.safety_days,
            order_cycle_days=plan_.order_cycle_days,
        ),
        sellable_by_location=plan_.on_hand.sellable_by_location,
        damaged=plan_.on_hand.damaged,
        expired=plan_.on_hand.expired,
        lots=lots_out,
        promised=[
            s.CommittedOut(
                order_no=c.order_no, customer_name=c.customer_name, ship_date=c.ship_date, qty=c.qty
            )
            for c in plan_.committed_lines
        ],
        incoming=[presenters.incoming_out(line) for line in plan_.incoming],
        late=[presenters.incoming_out(line) for line in plan_.late_incoming],
        demand=s.DemandOut(
            selling_per_week=round(plan_.demand.base_rate_per_day * 7, 2),
            measured_over_days=plan_.demand.base_days,
            season_now=round(plan_.demand.base_index, 3),
            normal_per_week=round(plan_.demand.level_per_day * 7, 2),
            season_by_month={k: round(v, 3) for k, v in plan_.demand.index_by_month.items()},
            monthly_history={k: round(v, 2) for k, v in plan_.demand.monthly_history.items()},
        ),
        projection=_points(plan_.confirmed),
        if_late_arrive_projection=_points(plan_.if_late_arrive) if plan_.if_late_arrive else None,
        explanation=list(plan_.explanation),
        settings=(
            s.ItemSettingsOut(
                item_code=code,
                lifecycle_override=settings.lifecycle_override,
                safety_days_override=settings.safety_days_override,
                note=settings.note,
                updated_at=settings.updated_at,
                updated_by=settings.updated_by,
            )
            if settings
            else None
        ),
        aliases=sorted(
            a.alias_code for a in session.scalars(select(m.ItemAlias).where(m.ItemAlias.item_code == code))
        ),
        handled_notes=[presenters.handled_out(f) for f in flags],
        season_markers=[
            s.SeasonMarkerOut(label=label, start=start, end=end) for label, start, end in rules.season_markers
        ],
    )
