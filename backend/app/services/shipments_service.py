"""Orders going out, and stock moving between buildings (Phase 6 step 2; ADR-026, ADR-028).

Dana logs a customer order (or a sample) from a building. While it's open it counts as promised on
its ship date. When she ships it, the lots to take are worked out soonest-to-expire first and shown
before she confirms (she can change them); the picks come out of those lots and the order joins the
selling-rate history if it's real demand (loader/classify.py decides, like BlueTide's sales).
Moving stock (e.g. Harbor -> New Bedford, or releasing a QA hold) is a paired out and in.

Every write is audited in the same transaction; mistakes are undone with reversing rows (the
history stays). The matching with BlueTide's orders is in planning/records.py (R7-R10).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import schemas as s
from app.config.business_rules import BusinessRules
from app.db import models as m
from app.db.sql import utc_now
from app.errors import AppError
from app.loader.normalize import canonical_code
from app.planning.calendar import add_months
from app.planning.explain import day
from app.planning.records import EPSILON, LotRecord
from app.planning.supply import lot_status
from app.planning.types import LocationInput
from app.services.audit import current_actor, record_change
from app.services.planning_inputs import PlanningContext, all_customers, build_context


def _f(v: Decimal | float | None) -> float | None:
    return float(v) if v is not None else None


def _locations(db: Session) -> dict[str, m.Location]:
    return {x.code: x for x in db.scalars(select(m.Location)).all()}


def _word(uom: str) -> str:
    return "cases" if uom == "CS" else "lb"


# ---- Customers --------------------------------------------------------------------------


def customers(db: Session) -> list[s.CustomerOut]:
    bluetide = {c.customer_code: c for c in db.scalars(select(m.Customer)).all()}
    mine = {c.customer_code: c for c in db.scalars(select(m.AppCustomer)).all()}
    out = []
    for code, (name, ctype) in all_customers(db).items():
        source = "both" if code in bluetide and code in mine else "app" if code in mine else "bluetide"
        out.append(s.CustomerOut(customer_code=code, name=name, customer_type=ctype, source=source))  # type: ignore[arg-type]
    return sorted(out, key=lambda c: c.name.lower())


def create_customer(db: Session, rules: BusinessRules, body: s.CustomerCreateIn) -> s.CustomerOut:
    ctype = body.customer_type.strip().upper()
    if ctype == rules.internal_customer_type.upper():
        raise AppError(
            422,
            "internal_customer",
            "Our own buildings aren't customers. Use Move stock to send stock between them.",
        )
    taken = set(all_customers(db))
    code = canonical_code(body.customer_code) if body.customer_code and body.customer_code.strip() else ""
    if not code:
        base = "".join(w[0] for w in body.name.split() if w[:1].isalnum()).upper()[:4] or "CUST"
        code, n = base, 2
        while code in taken:
            code, n = f"{base}{n}", n + 1
    if code in taken:
        raise AppError(409, "customer_exists", f"There's already a customer with the code {code}.")
    actor = current_actor()
    db.add(
        m.AppCustomer(
            customer_code=code,
            name=body.name.strip(),
            customer_type=ctype,
            created_by=actor,
            updated_by=actor,
        )
    )
    record_change(
        db,
        action="customer.create",
        entity_type="customer",
        entity_id=code,
        before=None,
        after={"name": body.name.strip(), "customer_type": ctype},
    )
    db.commit()
    return next(c for c in customers(db) if c.customer_code == code)


# ---- Current stock, and picks soonest-to-expire first -----------------------------------------


def _countable(ctx: PlanningContext, rules: BusinessRules, db: Session) -> list[tuple[LotRecord, bool, str]]:
    """Every lot the plan counts now, with whether it's sellable stock and its building's name."""
    locs = _locations(db)
    six = add_months(rules.as_of_date, rules.six_month_line_months)
    out = []
    for r in ctx.lot_records:
        if not r.lot.qty or r.lot.qty <= 0 or r.lot.is_adjustment:
            continue
        loc = locs.get(r.lot.location_code)
        loc_in = (
            LocationInput(loc.code, loc.is_sellable, loc.may_return_to_stock, loc.is_third_party_storage)
            if loc
            else None
        )
        counted, _ = lot_status(r.lot, loc_in, rules.as_of_date, six)
        out.append((r, counted, loc.name if loc else r.lot.location_code))
    return out


def stock_lots(db: Session, rules: BusinessRules, item_code: str) -> list[s.StockLotOut]:
    ctx = build_context(db, rules)
    locs = _locations(db)
    return [
        s.StockLotOut(
            item_code=r.lot.item_code,
            location_code=r.lot.location_code,
            location_name=name,
            lot_no=r.lot.lot_no,
            qty=r.lot.qty or 0.0,
            expiry_date=r.lot.expiry_date,
            unit_cost=r.lot.unit_cost,
            counted=counted,
            at_harbor=bool(
                locs.get(r.lot.location_code) and locs[r.lot.location_code].is_third_party_storage
            ),
        )
        for r, counted, name in sorted(
            _countable(ctx, rules, db),
            key=lambda x: (x[0].lot.location_code, x[0].lot.expiry_date or date.max),
        )
        if r.lot.item_code == item_code
    ]


def _plan_picks(
    ctx: PlanningContext, rules: BusinessRules, db: Session, shipment: m.Shipment, lines: list[m.ShipmentLine]
) -> s.PickPlanOut:
    """Soonest-to-expire sellable lots in the shipment's building, never more than each lot has."""
    left: dict[tuple[str, str], float] = {}
    by_item: dict[str, list[tuple[LotRecord, str]]] = defaultdict(list)
    for r, counted, name in _countable(ctx, rules, db):
        if counted and r.lot.location_code == shipment.location_code:
            by_item[r.lot.item_code].append((r, name))
            left[(r.lot.item_code, r.lot.lot_no)] = left.get((r.lot.item_code, r.lot.lot_no), 0.0) + (
                r.lot.qty or 0
            )
    picks: list[s.PickOut] = []
    short: dict[int, float] = {}
    for line in sorted(lines, key=lambda x: x.line_no):
        need = float(line.qty)
        seen: set[str] = set()
        for r, name in sorted(
            by_item[line.item_code], key=lambda x: (x[0].lot.expiry_date or date.max, x[0].lot.lot_no)
        ):
            if r.lot.lot_no in seen:
                continue
            seen.add(r.lot.lot_no)
            key = (line.item_code, r.lot.lot_no)
            take = min(left[key], need)
            if take < EPSILON:
                continue
            left[key] -= take
            need -= take
            picks.append(
                s.PickOut(
                    line_no=line.line_no,
                    item_code=line.item_code,
                    location_code=shipment.location_code,
                    location_name=name,
                    lot_no=r.lot.lot_no,
                    expiry_date=r.lot.expiry_date,
                    qty=take,
                )
            )
            if need < EPSILON:
                break
        if need >= EPSILON:
            short[line.line_no] = need
    return s.PickPlanOut(picks=picks, short=short)


# ---- Reading shipments ------------------------------------------------------------------------


def _shipment_out(
    db: Session, ctx: PlanningContext, sh: m.Shipment, lines: list[m.ShipmentLine]
) -> s.ShipmentOut:
    names = all_customers(db)
    locs = _locations(db)
    items = {i.item_code: i for i in ctx.inputs.items}
    records = {(r.order_no, r.line_no): r for r in (ctx.shipments.lines if ctx.shipments else ())}
    moves = db.scalars(select(m.StockMovement).where(m.StockMovement.shipment_id == sh.id)).all()
    reversed_ids = {x.reverses_id for x in moves if x.reverses_id is not None}
    picks: dict[int, list[s.PickOut]] = defaultdict(list)
    for x in moves:
        if x.reverses_id is None and x.id not in reversed_ids:
            picks[x.shipment_line_no or 0].append(
                s.PickOut(
                    line_no=x.shipment_line_no or 0,
                    item_code=x.item_code,
                    location_code=x.location_code,
                    location_name=locs[x.location_code].name if x.location_code in locs else x.location_code,
                    lot_no=x.lot_no,
                    expiry_date=x.expiry_date,
                    qty=-float(x.qty),
                )
            )
    out_lines = []
    for line in sorted(lines, key=lambda x: x.line_no):
        rec = records.get((sh.order_no, line.line_no))
        item = items.get(line.item_code)
        out_lines.append(
            s.ShipmentLineOut(
                line_no=line.line_no,
                item_code=line.item_code,
                description=item.description if item else line.item_code,
                sell_uom=item.sell_uom if item else "CS",
                qty=float(line.qty),
                unit_price=_f(line.unit_price),
                promised=bool(rec and rec.promised),
                taken_from_stock=bool(rec and rec.taken_from_stock),
                counts_as_demand=bool(rec and rec.counts_as_demand),
                flags=list(rec.flags) if rec else [],
                picks=picks.get(line.line_no, []),
            )
        )
    return s.ShipmentOut(
        order_no=sh.order_no,
        customer_code=sh.customer_code,
        customer_name=names.get(sh.customer_code, (sh.customer_code, ""))[0],
        kind=sh.kind,  # type: ignore[arg-type]
        order_date=sh.order_date,
        ship_date=sh.ship_date,
        location_code=sh.location_code,
        location_name=locs[sh.location_code].name if sh.location_code in locs else sh.location_code,
        status=sh.status,  # type: ignore[arg-type]
        shipped_on=sh.shipped_on,
        cancel_reason=sh.cancel_reason,
        note=sh.note,
        created_by=sh.created_by,
        lines=out_lines,
    )


def _lines_by_shipment(db: Session) -> dict[int, list[m.ShipmentLine]]:
    out: dict[int, list[m.ShipmentLine]] = defaultdict(list)
    for line in db.scalars(select(m.ShipmentLine)).all():
        out[line.shipment_id].append(line)
    return out


def shipments(
    db: Session, rules: BusinessRules, status: str = "open", q: str | None = None
) -> list[s.ShipmentOut]:
    ctx = build_context(db, rules)
    lines = _lines_by_shipment(db)
    query = select(m.Shipment)
    if status != "all":
        query = query.where(m.Shipment.status == status)
    out = [_shipment_out(db, ctx, sh, lines[sh.id]) for sh in db.scalars(query).all()]
    if q:
        needle = q.strip().lower()
        out = [
            x
            for x in out
            if needle in x.order_no.lower()
            or needle in x.customer_name.lower()
            or any(needle in ln.item_code.lower() or needle in ln.description.lower() for ln in x.lines)
        ]
    return sorted(out, key=lambda x: (x.ship_date, x.order_no), reverse=status != "open")


def _get(db: Session, order_no: str) -> tuple[m.Shipment, list[m.ShipmentLine]]:
    sh = db.execute(select(m.Shipment).where(m.Shipment.order_no == order_no)).scalar_one_or_none()
    if sh is None:
        raise AppError(404, "shipment_not_found", f"We couldn't find order {order_no}.")
    lines = db.scalars(select(m.ShipmentLine).where(m.ShipmentLine.shipment_id == sh.id)).all()
    return sh, list(lines)


def shipment(db: Session, rules: BusinessRules, order_no: str) -> s.ShipmentOut:
    sh, lines = _get(db, order_no)
    return _shipment_out(db, build_context(db, rules), sh, lines)


def pick_plan(db: Session, rules: BusinessRules, order_no: str) -> s.PickPlanOut:
    sh, lines = _get(db, order_no)
    return _plan_picks(build_context(db, rules), rules, db, sh, lines)


# ---- Writing shipments --------------------------------------------------------------------------


def _next_order_no(db: Session, rules: BusinessRules) -> str:
    prefix = rules.app_shipment_prefix
    numbers = [
        int(n[len(prefix) :])
        for n in db.scalars(select(m.Shipment.order_no).where(m.Shipment.order_no.startswith(prefix)))
        if n[len(prefix) :].isdigit()
    ]
    return f"{prefix}{max(numbers, default=0) + 1:05d}"


def create_shipment(db: Session, rules: BusinessRules, body: s.ShipmentCreateIn) -> s.ShipmentOut:
    ctx = build_context(db, rules)
    as_of = rules.as_of_date
    names = all_customers(db)
    code = canonical_code(body.customer_code)
    if code not in names:
        raise AppError(
            404, "customer_not_found", f"We couldn't find customer {body.customer_code!r}. Add them first."
        )
    if names[code][1].upper() == rules.internal_customer_type.upper():
        raise AppError(
            422,
            "internal_customer",
            "That's one of our own buildings. Use Move stock to send stock between them.",
        )
    loc = _locations(db).get(canonical_code(body.location_code))
    if loc is None or not loc.is_sellable:
        raise AppError(422, "location_not_allowed", "Orders ship from a building with sellable stock.")
    order_date = body.order_date or as_of
    ship_date = body.ship_date or as_of
    if order_date > as_of:
        raise AppError(422, "date_in_future", "The order date can't be after today.")
    if ship_date < order_date:
        raise AppError(422, "ship_before_order", "The ship date can't be before the order date.")
    items = {i.item_code for i in ctx.inputs.items}
    codes = [canonical_code(x.item_code) for x in body.lines]
    for raw, c in zip(body.lines, codes, strict=True):
        if c not in items:
            raise AppError(404, "item_not_found", f"We couldn't find item {raw.item_code!r}.")
    dupes = {c for c in codes if codes.count(c) > 1}
    if dupes:
        raise AppError(422, "duplicate_item", f"{', '.join(sorted(dupes))} is on this order twice.")
    order_no = (
        canonical_code(body.order_no)
        if body.order_no and body.order_no.strip()
        else _next_order_no(db, rules)
    )
    if db.execute(select(m.Shipment.id).where(m.Shipment.order_no == order_no)).first():
        raise AppError(409, "order_exists", f"There's already an order {order_no} in the app.")
    actor = current_actor()
    sh = m.Shipment(
        order_no=order_no,
        customer_code=code,
        kind=body.kind,
        order_date=order_date,
        ship_date=ship_date,
        location_code=loc.code,
        status="open",
        note=body.note,
        created_by=actor,
        updated_by=actor,
    )
    db.add(sh)
    db.flush()
    for n, (line, c) in enumerate(zip(body.lines, codes, strict=True), start=1):
        db.add(
            m.ShipmentLine(
                shipment_id=sh.id,
                line_no=n,
                item_code=c,
                qty=Decimal(str(line.qty)),
                unit_price=Decimal(str(line.unit_price)) if line.unit_price is not None else None,
            )
        )
    record_change(
        db,
        action="shipment.create",
        entity_type="shipment",
        entity_id=order_no,
        before=None,
        after={
            "customer_code": code,
            "kind": body.kind,
            "order_date": order_date,
            "ship_date": ship_date,
            "location": loc.code,
            "lines": [{"item_code": c, "qty": x.qty} for c, x in zip(codes, body.lines, strict=True)],
        },
    )
    db.commit()
    return shipment(db, rules, order_no)


def ship(db: Session, rules: BusinessRules, order_no: str, body: s.ShipIn) -> s.ShipmentOut:
    sh, lines = _get(db, order_no)
    if sh.status != "open":
        raise AppError(409, "not_open", f"Order {order_no} is {sh.status}, so it can't be shipped.")
    shipped_on = body.shipped_on or rules.as_of_date
    if shipped_on > rules.as_of_date:
        raise AppError(422, "date_in_future", "The shipped date can't be after today.")
    if shipped_on < sh.order_date:
        raise AppError(422, "ship_before_order", "The shipped date can't be before the order date.")
    ctx = build_context(db, rules)
    units = {i.item_code: i.sell_uom for i in ctx.inputs.items}
    if body.picks is None:
        plan = _plan_picks(ctx, rules, db, sh, lines)
        if plan.short:
            line_no, missing = next(iter(plan.short.items()))
            line = next(x for x in lines if x.line_no == line_no)
            raise AppError(
                422,
                "not_enough_stock",
                f"{sh.location_code} is short {round(missing):,} {_word(units.get(line.item_code, 'CS'))} of "
                f"{line.item_code}. Ship less, ship from another building, or move stock first.",
            )
        picks = [(p.line_no, p.lot_no, p.qty) for p in plan.picks]
    else:
        picks = [(p.line_no, p.lot_no.strip(), p.qty) for p in body.picks]

    by_line = {x.line_no: x for x in lines}
    available: dict[tuple[str, str], tuple[float, LotRecord]] = {}
    for r, counted, _ in _countable(ctx, rules, db):
        if counted and r.lot.location_code == sh.location_code:
            key = (r.lot.item_code, r.lot.lot_no)
            have = available.get(key, (0.0, r))[0]
            available[key] = (have + (r.lot.qty or 0), r)
    totals: dict[int, float] = defaultdict(float)
    used: dict[tuple[str, str], float] = defaultdict(float)
    for line_no, lot_no, qty in picks:
        line = by_line.get(line_no)
        if line is None:
            raise AppError(422, "bad_pick", f"Order {order_no} has no line {line_no}.")
        key = (line.item_code, lot_no)
        if key not in available:
            raise AppError(
                422,
                "lot_not_found",
                f"There's no lot {lot_no} of {line.item_code} to sell at {sh.location_code}.",
            )
        used[key] += qty
        if used[key] > available[key][0] + EPSILON:
            raise AppError(
                422,
                "lot_too_small",
                f"Lot {lot_no} has only {round(available[key][0]):,} "
                f"{_word(units.get(line.item_code, 'CS'))}.",
            )
        totals[line_no] += qty
    for line in lines:
        if abs(totals[line.line_no] - float(line.qty)) >= EPSILON:
            raise AppError(
                422,
                "picks_dont_add_up",
                f"Line {line.line_no} is {round(float(line.qty)):,} but the lots picked add up to "
                f"{round(totals[line.line_no]):,}.",
            )

    actor = current_actor()
    kind = "sample" if sh.kind == "sample" else "shipment"
    for line_no, lot_no, qty in picks:
        line = by_line[line_no]
        lot = available[(line.item_code, lot_no)][1].lot
        db.add(
            m.StockMovement(
                movement_date=shipped_on,
                kind=kind,
                item_code=line.item_code,
                location_code=sh.location_code,
                lot_no=lot_no,
                qty=-Decimal(str(qty)),
                expiry_date=lot.expiry_date,
                unit_cost=Decimal(str(lot.unit_cost)) if lot.unit_cost is not None else None,
                shipment_id=sh.id,
                shipment_line_no=line_no,
                created_by=actor,
            )
        )
    sh.status, sh.shipped_on, sh.updated_by = "shipped", shipped_on, actor
    sh.updated_at = utc_now()  # type: ignore[assignment]
    record_change(
        db,
        action="shipment.ship",
        entity_type="shipment",
        entity_id=order_no,
        before={"status": "open"},
        after={
            "status": "shipped",
            "shipped_on": shipped_on,
            "picks": [{"line_no": n, "lot_no": lot_no, "qty": q} for n, lot_no, q in picks],
        },
    )
    db.commit()
    return shipment(db, rules, order_no)


def cancel(db: Session, rules: BusinessRules, order_no: str, body: s.CancelIn) -> s.ShipmentOut:
    sh, _ = _get(db, order_no)
    if sh.status != "open":
        raise AppError(
            409,
            "not_open",
            f"Order {order_no} is {sh.status}. Undo the shipment first if it really didn't go.",
        )
    sh.status, sh.cancel_reason, sh.updated_by = "cancelled", body.reason, current_actor()
    sh.updated_at = utc_now()  # type: ignore[assignment]
    record_change(
        db,
        action="shipment.cancel",
        entity_type="shipment",
        entity_id=order_no,
        before={"status": "open"},
        after={"status": "cancelled", "reason": body.reason},
    )
    db.commit()
    return shipment(db, rules, order_no)


def undo_ship(db: Session, rules: BusinessRules, order_no: str, body: s.CancelIn) -> s.ShipmentOut:
    """It didn't go after all: the picks go back into their lots, and the order is open again."""
    sh, _ = _get(db, order_no)
    if sh.status != "shipped":
        raise AppError(409, "not_shipped", f"Order {order_no} isn't shipped.")
    actor = current_actor()
    moves = db.scalars(select(m.StockMovement).where(m.StockMovement.shipment_id == sh.id)).all()
    reversed_ids = {x.reverses_id for x in moves if x.reverses_id is not None}
    for x in moves:
        if x.reverses_id is None and x.id not in reversed_ids:
            db.add(
                m.StockMovement(
                    movement_date=x.movement_date,
                    kind=x.kind,
                    item_code=x.item_code,
                    location_code=x.location_code,
                    lot_no=x.lot_no,
                    qty=-x.qty,
                    expiry_date=x.expiry_date,
                    unit_cost=x.unit_cost,
                    shipment_id=sh.id,
                    shipment_line_no=x.shipment_line_no,
                    reverses_id=x.id,
                    note=body.reason,
                    created_by=actor,
                )
            )
    before = {"status": "shipped", "shipped_on": sh.shipped_on}
    sh.status, sh.shipped_on, sh.updated_by = "open", None, actor
    sh.updated_at = utc_now()  # type: ignore[assignment]
    record_change(
        db,
        action="shipment.undo_ship",
        entity_type="shipment",
        entity_id=order_no,
        before=before,
        after={"status": "open", "reason": body.reason},
    )
    db.commit()
    return shipment(db, rules, order_no)


# ---- Moving stock between buildings -----------------------------------------------------------


def move_stock(db: Session, rules: BusinessRules, body: s.MoveIn) -> list[s.MovementOut]:
    ctx = build_context(db, rules)
    locs = _locations(db)
    item_code = canonical_code(body.item_code)
    src, dst = canonical_code(body.from_location), canonical_code(body.to_location)
    if src not in locs or dst not in locs:
        raise AppError(404, "location_not_found", "We couldn't find one of those buildings.")
    if src == dst:
        raise AppError(422, "same_building", "Pick a different building to move it to.")
    moved_on = body.moved_on or rules.as_of_date
    if moved_on > rules.as_of_date:
        raise AppError(422, "date_in_future", "The move date can't be after today.")
    if ctx.load.snapshot_date is not None and moved_on <= ctx.load.snapshot_date:
        raise AppError(
            422,
            "before_stock_count",
            f"BlueTide's stock count from {day(ctx.load.snapshot_date)} already includes moves made "
            "on or before that day. Use a later date.",
        )
    lot = next(
        (
            r.lot
            for r in ctx.lot_records
            if (r.lot.item_code, r.lot.location_code, r.lot.lot_no) == (item_code, src, body.lot_no.strip())
            and not r.lot.is_adjustment
            and (r.lot.qty or 0) > 0
        ),
        None,
    )
    if lot is None:
        raise AppError(
            404, "lot_not_found", f"There's no lot {body.lot_no} of {item_code} at {locs[src].name}."
        )
    if body.qty > (lot.qty or 0) + EPSILON:
        raise AppError(
            422, "lot_too_small", f"Lot {lot.lot_no} at {locs[src].name} has only {round(lot.qty or 0):,}."
        )
    actor = current_actor()
    cost = Decimal(str(lot.unit_cost)) if lot.unit_cost is not None else None
    out_row = m.StockMovement(
        movement_date=moved_on,
        kind="move_out",
        item_code=item_code,
        location_code=src,
        lot_no=lot.lot_no,
        qty=-Decimal(str(body.qty)),
        expiry_date=lot.expiry_date,
        unit_cost=cost,
        note=body.note,
        created_by=actor,
    )
    db.add(out_row)
    db.flush()
    in_row = m.StockMovement(
        movement_date=moved_on,
        kind="move_in",
        item_code=item_code,
        location_code=dst,
        lot_no=lot.lot_no,
        qty=Decimal(str(body.qty)),
        expiry_date=lot.expiry_date,
        unit_cost=cost,
        pair_id=out_row.id,
        note=body.note,
        created_by=actor,
    )
    db.add(in_row)
    db.flush()
    record_change(
        db,
        action="stock.move",
        entity_type="stock_movement",
        entity_id=str(out_row.id),
        before=None,
        after={
            "item_code": item_code,
            "lot_no": lot.lot_no,
            "qty": body.qty,
            "from": src,
            "to": dst,
            "moved_on": moved_on,
        },
    )
    db.commit()
    return [
        s.MovementOut(
            id=x.id,
            movement_date=x.movement_date,
            kind=x.kind,
            item_code=x.item_code,
            location_code=x.location_code,
            lot_no=x.lot_no,
            qty=float(x.qty),
            reverses_id=x.reverses_id,
            created_by=x.created_by,
        )
        for x in (out_row, in_row)
    ]
