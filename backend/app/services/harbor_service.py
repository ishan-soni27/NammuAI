"""Harbor storage cost (P1 #1; ADR-031): what's at Harbor, in pallets and dollars a month.

Dana types how many cases fit on a pallet for each item (remembered in item_settings). The pure
rule in planning/storage.py turns the stock at Harbor into pallets (each lot on its own pallets,
a part pallet charged whole; A47) at the rate in business_rules (Dana: $30 per pallet per month).
She can add any line, or a what-if amount, to her own table (harbor_storage_rows), which keeps
each row exactly as worked out and downloads as a CSV.

The stock is the plan's own merged lots (BlueTide's count plus her receipts and moves), so a
move out of Harbor on the Shipments page lowers the cost here at once.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import schemas as s
from app.config.business_rules import BusinessRules
from app.db import models as m
from app.errors import AppError
from app.planning.storage import StorageLine, monthly_cost, pallets_needed, storage_lines
from app.planning.stuck import TAG_ORDER
from app.planning.types import ItemInput, PlanResult
from app.services import planning_service
from app.services.audit import current_actor, record_change


def item_setting_dict(setting: m.ItemSetting) -> dict:
    """An item's settings as the audit trail records them (shared with the item settings endpoint)."""
    return {
        "item_code": setting.item_code,
        "lifecycle_override": setting.lifecycle_override,
        "safety_days_override": setting.safety_days_override,
        "cases_per_pallet": setting.cases_per_pallet,
        "note": setting.note,
    }


def check_cases_per_pallet(value: int, rules: BusinessRules) -> None:
    if not 1 <= value <= rules.cases_per_pallet_max:
        raise AppError(
            422,
            "out_of_range",
            f"Cases per pallet must be a whole number from 1 to {rules.cases_per_pallet_max:,}.",
        )


def _remembered(db: Session) -> dict[str, int]:
    rows = db.scalars(select(m.ItemSetting).where(m.ItemSetting.cases_per_pallet.is_not(None))).all()
    return {r.item_code: r.cases_per_pallet for r in rows if r.cases_per_pallet}


def _current(db: Session, rules: BusinessRules) -> tuple[list[StorageLine], PlanResult, dict[str, ItemInput]]:
    result, context = planning_service.current_plan_and_context(db, rules)
    inputs = context.inputs
    lines = storage_lines(
        inputs.lots, inputs.locations, inputs.items, _remembered(db), rules.harbor_pallet_cost_per_month
    )
    return lines, result, {i.item_code: i for i in inputs.items}


def _row_dict(row: m.HarborStorageRow) -> dict:
    return {
        "kind": row.kind,
        "as_of_date": row.as_of_date.isoformat(),
        "item_code": row.item_code,
        "cases": float(row.cases),
        "lots": row.lots,
        "cases_per_pallet": row.cases_per_pallet,
        "pallets": row.pallets,
        "rate_per_pallet_month": float(row.rate_per_pallet_month),
        "cost_per_month": float(row.cost_per_month),
    }


def _row_out(row: m.HarborStorageRow) -> s.HarborRowOut:
    return s.HarborRowOut(
        id=row.id,
        description=row.description,
        created_at=row.created_at,
        created_by=row.created_by,
        **{k: v for k, v in _row_dict(row).items() if k != "as_of_date"},
        as_of_date=row.as_of_date,
    )


def saved_rows(db: Session) -> list[m.HarborStorageRow]:
    """Her table, newest first."""
    return list(db.scalars(select(m.HarborStorageRow).order_by(m.HarborStorageRow.id.desc())).all())


def harbor(db: Session, rules: BusinessRules) -> s.HarborOut:
    lines, result, items = _current(db, rules)
    names = {loc.code: loc.name for loc in db.scalars(select(m.Location)).all()}
    paid = sorted({names.get(loc.code, loc.code) for loc in _paid_locations(db)})
    stuck_tag = {
        st.item_code: min((x.primary_tag for x in st.lots if x.at_harbor), key=TAG_ORDER.index, default=None)
        for st in result.stuck
    }
    out = [
        s.HarborItemOut(
            item_code=line.item_code,
            description=items[line.item_code].description,
            sell_uom=items[line.item_code].sell_uom,
            cases=line.cases,
            lots=[
                s.HarborLotOut(
                    lot_no=x.lot_no,
                    location_name=names.get(x.location_code, x.location_code),
                    cases=x.cases,
                    expiry_date=x.expiry_date,
                )
                for x in line.lots
            ],
            cases_per_pallet=line.cases_per_pallet,
            pallets=line.pallets,
            cost_per_month=line.cost_per_month,
            stuck_tag=stuck_tag.get(line.item_code),
            unconverted_lots=line.unconverted_lots,
        )
        for line in lines
    ]
    priced = [x for x in lines if x.pallets is not None]
    return s.HarborOut(
        as_of=rules.as_of_date,
        rate_per_pallet_month=rules.harbor_pallet_cost_per_month,
        cases_per_pallet_max=rules.cases_per_pallet_max,
        location_names=paid,
        items=out,
        totals=s.HarborTotalsOut(
            items=len(lines),
            cases=sum(x.cases for x in lines),
            priced_items=len(priced),
            pallets=sum(x.pallets or 0 for x in priced),
            cost_per_month=round(sum(x.cost_per_month or 0 for x in priced), 2),
        ),
        saved=[_row_out(r) for r in saved_rows(db)],
    )


def _paid_locations(db: Session) -> list[m.Location]:
    return list(db.scalars(select(m.Location).where(m.Location.is_third_party_storage.is_(True))).all())


def _remember(db: Session, item_code: str, cases_per_pallet: int) -> None:
    """Keep her cases per pallet for the item (audited like any other item setting)."""
    setting = db.get(m.ItemSetting, item_code)
    if setting is not None and setting.cases_per_pallet == cases_per_pallet:
        return
    before = item_setting_dict(setting) if setting is not None else None
    if setting is None:
        setting = m.ItemSetting(item_code=item_code, updated_by=current_actor())
        db.add(setting)
    setting.cases_per_pallet = cases_per_pallet
    setting.updated_by = current_actor()
    db.flush()
    record_change(
        db,
        action="item_settings.update",
        entity_type="item_settings",
        entity_id=item_code,
        before=before,
        after=item_setting_dict(setting),
    )


def add_rows(db: Session, rules: BusinessRules, body: s.HarborRowsIn) -> s.HarborOut:
    """Work out each row on the server (never trusting the page's arithmetic) and add it to her table.

    No cases = what's at Harbor now for that item, pallets per lot. Cases = a what-if amount, worked
    out as one lot. Either way her cases per pallet is remembered for the item. All or nothing.
    """
    lines, _, items = _current(db, rules)
    at_harbor = {x.item_code: x for x in lines}
    rate = rules.harbor_pallet_cost_per_month
    for want in body.rows:
        code = planning_service.resolve_item_code(db, want.item_code)
        item = items.get(code)
        if item is None:
            raise AppError(422, "not_planned", f"{code} isn't one of the items the app plans.")
        check_cases_per_pallet(want.cases_per_pallet, rules)
        if want.cases is None:
            line = at_harbor.get(code)
            if line is None or not line.lots:
                raise AppError(
                    422,
                    "nothing_at_harbor",
                    f"There's no {code} at Harbor now. Type an amount to work out a what-if.",
                )
            kind, cases, lots = "at_harbor", line.cases, len(line.lots)
            pallets = pallets_needed((x.cases for x in line.lots), want.cases_per_pallet)
        else:
            kind, cases, lots = "what_if", want.cases, 1
            pallets = pallets_needed([want.cases], want.cases_per_pallet)
        _remember(db, code, want.cases_per_pallet)
        row = m.HarborStorageRow(
            kind=kind,
            as_of_date=rules.as_of_date,
            item_code=code,
            description=item.description,
            cases=Decimal(str(round(cases, 4))),
            lots=lots,
            cases_per_pallet=want.cases_per_pallet,
            pallets=pallets,
            rate_per_pallet_month=Decimal(str(rate)),
            cost_per_month=Decimal(str(monthly_cost(pallets, rate))),
            created_by=current_actor(),
        )
        db.add(row)
        db.flush()
        record_change(
            db,
            action="harbor_storage.add",
            entity_type="harbor_storage_row",
            entity_id=str(row.id),
            before=None,
            after=_row_dict(row),
        )
    db.commit()
    return harbor(db, rules)


def delete_row(db: Session, rules: BusinessRules, row_id: int) -> s.HarborOut:
    row = db.get(m.HarborStorageRow, row_id)
    if row is None:
        raise AppError(404, "row_not_found", "That row isn't in your table any more.")
    record_change(
        db,
        action="harbor_storage.delete",
        entity_type="harbor_storage_row",
        entity_id=str(row.id),
        before=_row_dict(row),
        after=None,
    )
    db.delete(row)
    db.commit()
    return harbor(db, rules)
