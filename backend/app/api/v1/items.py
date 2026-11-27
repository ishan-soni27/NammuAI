"""The Monday screen, the item drill-down, and Dana's per-item actions (BUILD_PROMPT §8.5).

GET    /dashboard                   everything the Monday screen shows
GET    /items                       every item with its status (the "show everything" view)
GET    /items/{item_code}           the full "why" for one item ("shr-1620 " finds SHR-1620)
POST   /items/{item_code}/handled   "I've handled this" (optional qty + arrival date + note)
DELETE /handled/{note_id}           clear a handled note (optional reason)
PATCH  /items/{item_code}/settings  revive an item / change its cushion / cases per pallet

Items come from BlueTide's uploads only (ADR-032); Dana adds what BlueTide doesn't know.

Every write records an audit row in the same transaction (services/audit.py). Business dates are
checked against AS_OF, never the clock.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.api.deps import request_rules
from app.api.v1 import schemas as s
from app.config.business_rules import BusinessRules
from app.db import models as m
from app.db.session import get_db
from app.db.sql import utc_now
from app.errors import AppError
from app.services import harbor_service, planning_service, presenters
from app.services.audit import current_actor, record_change

router = APIRouter(tags=["Monday screen and items"])


@router.get("/dashboard", response_model=s.DashboardOut)
def get_dashboard(
    db: Session = Depends(get_db), rules: BusinessRules = Depends(request_rules)
) -> s.DashboardOut:
    """What will run out before a new order can arrive, and what you're stuck with."""
    return planning_service.dashboard(db, rules)


@router.get("/items", response_model=list[s.ItemCard])
def list_items(
    db: Session = Depends(get_db), rules: BusinessRules = Depends(request_rules)
) -> list[s.ItemCard]:
    return planning_service.all_items(db, rules)


@router.get("/items/{item_code}", response_model=s.ItemDetailOut)
def get_item(
    item_code: str, db: Session = Depends(get_db), rules: BusinessRules = Depends(request_rules)
) -> s.ItemDetailOut:
    return planning_service.item_detail(db, rules, item_code)


def _flag_dict(flag: m.HandledFlag) -> dict:
    return {
        "item_code": flag.item_code,
        "qty": flag.qty,
        "eta": flag.eta,
        "note": flag.note,
        "cleared_at": flag.cleared_at,
        "cleared_by": flag.cleared_by,
        "clear_reason": flag.clear_reason,
    }


@router.post("/items/{item_code}/handled", response_model=s.HandledNoteOut, status_code=201)
def mark_handled(
    item_code: str,
    body: s.HandledIn,
    db: Session = Depends(get_db),
    rules: BusinessRules = Depends(request_rules),
) -> s.HandledNoteOut:
    """Dana: "I want to be able to tell it 'I've handled this one'" (00:09:45, §6.10).

    With BOTH a quantity and a date, the note counts as stock on the way. Otherwise it only moves the
    item to the Handled section.
    """
    code = planning_service.resolve_item_code(db, item_code)
    if body.eta is not None and body.eta < rules.as_of_date:
        raise AppError(
            422, "date_in_past", "That arrival date has already passed. Pick today or a later date."
        )
    flag = m.HandledFlag(
        item_code=code,
        qty=Decimal(str(body.qty)) if body.qty is not None else None,
        eta=body.eta,
        note=body.note,
        created_on=rules.as_of_date,  # business day, so "BlueTide now shows PO-x" compares like with like
        created_by=current_actor(),
    )
    db.add(flag)
    db.flush()  # get the id for the audit row
    record_change(
        db,
        action="handled.create",
        entity_type="handled_flag",
        entity_id=str(flag.id),
        before=None,
        after=_flag_dict(flag),
    )
    db.commit()
    db.refresh(flag)
    return presenters.handled_out(flag, as_of=rules.as_of_date)


@router.delete("/handled/{note_id}", response_model=s.HandledNoteOut)
def clear_handled(
    note_id: int,
    body: s.HandledClearIn | None = Body(default=None),
    db: Session = Depends(get_db),
) -> s.HandledNoteOut:
    """Clear a handled note. Notes are never deleted, only cleared, so the history stays (§6.10)."""
    flag = db.get(m.HandledFlag, note_id)
    if flag is None:
        raise AppError(404, "note_not_found", f"We couldn't find note #{note_id}.")
    if flag.cleared_at is not None:
        raise AppError(409, "already_cleared", f"Note #{note_id} was already cleared.")
    before = _flag_dict(flag)
    flag.cleared_at = utc_now()  # type: ignore[assignment]  # audit time: real UTC, set by the database
    flag.cleared_by = current_actor()
    flag.clear_reason = body.reason if body else None
    db.flush()
    db.refresh(flag)
    record_change(
        db,
        action="handled.clear",
        entity_type="handled_flag",
        entity_id=str(flag.id),
        before=before,
        after=_flag_dict(flag),
    )
    db.commit()
    return presenters.handled_out(flag)


@router.patch("/items/{item_code}/settings", response_model=s.ItemSettingsOut)
def update_item_settings(
    item_code: str,
    body: s.ItemSettingsPatchIn,
    db: Session = Depends(get_db),
    rules: BusinessRules = Depends(request_rules),
) -> s.ItemSettingsOut:
    """Per-item overrides: "this item is still active" (revive a dormant item), or its own cushion."""
    code = planning_service.resolve_item_code(db, item_code)
    sent = body.model_fields_set
    if not sent:
        raise AppError(422, "nothing_to_change", "Send at least one setting to change.")
    if (
        "safety_days_override" in sent
        and body.safety_days_override is not None
        and not (rules.setting_days_min <= body.safety_days_override <= rules.setting_days_max)
    ):
        raise AppError(
            422,
            "out_of_range",
            f"Cushion must be between {rules.setting_days_min} and {rules.setting_days_max} days.",
        )
    if "cases_per_pallet" in sent and body.cases_per_pallet is not None:
        harbor_service.check_cases_per_pallet(body.cases_per_pallet, rules)
    setting = db.get(m.ItemSetting, code)
    before = None
    if setting is None:
        setting = m.ItemSetting(item_code=code, updated_by=current_actor())
        db.add(setting)
    else:
        before = _setting_dict(setting)
    for field in sent:
        setattr(setting, field, getattr(body, field))
    setting.updated_by = current_actor()
    setting.updated_at = utc_now()  # type: ignore[assignment]
    db.flush()
    db.refresh(setting)
    record_change(
        db,
        action="item_settings.update",
        entity_type="item_settings",
        entity_id=code,
        before=before,
        after=_setting_dict(setting),
    )
    db.commit()
    return s.ItemSettingsOut(
        item_code=code,
        **{k: v for k, v in _setting_dict(setting).items() if k != "item_code"},
        updated_at=setting.updated_at,
        updated_by=setting.updated_by,
    )


def _setting_dict(setting: m.ItemSetting) -> dict:
    return harbor_service.item_setting_dict(setting)
