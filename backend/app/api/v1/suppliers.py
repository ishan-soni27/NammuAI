"""Lead times and PO arrival dates: what Dana knows that BlueTide doesn't (BUILD_PROMPT §8.5, P0 #7).

GET   /vendors                                  suppliers, BlueTide's and Dana's: lead time vs Dana's
POST  /vendors                                  add a supplier (Phase 6: the app works without BlueTide)
PATCH /vendors/{vendor_code}                    change lead time / cushion / order cycle
PATCH /purchase-orders/{po_no}/lines/{line_no}  type in the real arrival date (null clears it), for
                                                BlueTide's PO lines and Dana's own (one date table, R1)

Walt 00:02:25: "Half of what we actually know lives in Dana's head, not the system." These edits
live in app-layer tables that the loader never touches (invariant #5), and each one is audited
in the same transaction.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import schemas as s
from app.config.business_rules import BusinessRules, get_business_rules
from app.db import models as m
from app.db.session import get_db
from app.db.sql import utc_now
from app.errors import AppError
from app.services import records_service
from app.services.audit import current_actor, record_change
from app.services.planning_inputs import build_context

router = APIRouter(tags=["Lead times and PO dates"])

# API field name -> vendor_settings column (Dana says "cushion"; the table says safety_days).
_VENDOR_FIELDS = {
    "lead_time_days": "lead_time_days",
    "cushion_days": "safety_days",
    "order_cycle_days": "order_cycle_days",
}


def _vendor_out(
    vendor: m.Vendor | None, setting: m.VendorSetting, mine: m.AppVendor | None = None
) -> s.VendorOut:
    """BlueTide's supplier, Dana's, or both (her name and country win)."""
    return s.VendorOut(
        vendor_code=setting.vendor_code,
        name=mine.name if mine else vendor.name if vendor else setting.vendor_code,
        country=mine.country if mine else vendor.country if vendor else None,
        lead_time_days_bluetide=vendor.lead_time_days_system if vendor else None,
        lead_time_bluetide_text=vendor.lead_time_raw if vendor else None,
        lead_time_days=setting.lead_time_days,
        cushion_days=setting.safety_days,
        order_cycle_days=setting.order_cycle_days,
        source=setting.source,
        note=setting.note,
        updated_at=setting.updated_at,
        updated_by=setting.updated_by,
    )


def _setting_dict(setting: m.VendorSetting) -> dict:
    return {
        "lead_time_days": setting.lead_time_days,
        "cushion_days": setting.safety_days,
        "order_cycle_days": setting.order_cycle_days,
        "source": setting.source,
        "note": setting.note,
    }


def _all_vendors(db: Session) -> list[s.VendorOut]:
    bluetide = {v.vendor_code: v for v in db.scalars(select(m.Vendor)).all()}
    mine = {v.vendor_code: v for v in db.scalars(select(m.AppVendor)).all()}
    out = [
        _vendor_out(bluetide.get(setting.vendor_code), setting, mine.get(setting.vendor_code))
        for setting in db.scalars(select(m.VendorSetting)).all()
        if setting.vendor_code in bluetide or setting.vendor_code in mine
    ]
    return sorted(out, key=lambda v: v.name.lower())


@router.get("/vendors", response_model=list[s.VendorOut])
def list_vendors(db: Session = Depends(get_db)) -> list[s.VendorOut]:
    return _all_vendors(db)


@router.post("/vendors", response_model=s.VendorOut, status_code=201)
def create_vendor(
    body: s.VendorCreateIn,
    db: Session = Depends(get_db),
    rules: BusinessRules = Depends(get_business_rules),
) -> s.VendorOut:
    """A supplier BlueTide doesn't have. Time to arrive and cushion are required (in days)."""
    code = records_service.create_vendor(db, rules, body)
    return next(v for v in _all_vendors(db) if v.vendor_code == code)


@router.patch("/vendors/{vendor_code}", response_model=s.VendorOut)
def update_vendor(
    vendor_code: str,
    body: s.VendorPatchIn,
    db: Session = Depends(get_db),
    rules: BusinessRules = Depends(get_business_rules),
) -> s.VendorOut:
    """Dana's real numbers. Only the fields sent change. Days must be within the limits in business_rules."""
    code = vendor_code.strip().upper()
    vendor = db.get(m.Vendor, code)
    mine = db.get(m.AppVendor, code)
    setting = db.get(m.VendorSetting, code)
    if (vendor is None and mine is None) or setting is None:
        raise AppError(
            404, "vendor_not_found", f"We couldn't find supplier {vendor_code!r} on the Lead times list."
        )
    sent = body.model_fields_set
    if not sent:
        raise AppError(422, "nothing_to_change", "Send at least one value to change.")
    for field in sent & _VENDOR_FIELDS.keys():
        value = getattr(body, field)
        if value is None or not (rules.setting_days_min <= value <= rules.setting_days_max):
            label = field.replace("_days", "").replace("_", " ")
            raise AppError(
                422,
                "out_of_range",
                f"The {label} must be between {rules.setting_days_min} and {rules.setting_days_max} days.",
            )
    before = _setting_dict(setting)
    for field in sent & _VENDOR_FIELDS.keys():
        setattr(setting, _VENDOR_FIELDS[field], getattr(body, field))
    if "note" in sent:
        setting.note = body.note
    setting.source = f"Set by {current_actor()}"
    setting.updated_by = current_actor()
    setting.updated_at = utc_now()  # type: ignore[assignment]  # audit time, set by the database
    db.flush()
    db.refresh(setting)
    record_change(
        db,
        action="vendor_settings.update",
        entity_type="vendor_settings",
        entity_id=code,
        before=before,
        after=_setting_dict(setting),
    )
    db.commit()
    return _vendor_out(vendor, setting, mine)


@router.patch("/purchase-orders/{po_no}/lines/{line_no}", response_model=s.PoEtaOut)
def set_po_arrival(
    po_no: str,
    line_no: int,
    body: s.PoEtaPatchIn,
    db: Session = Depends(get_db),
    rules: BusinessRules = Depends(get_business_rules),
) -> s.PoEtaOut:
    """The email promised Dana she could type in a real arrival date for late POs (Q3). Null clears it."""
    ctx = build_context(db, rules)
    line = next((x for x in ctx.reconciled.lines if (x.po_no, x.line_no) == (po_no, line_no)), None)
    if line is None:
        raise AppError(404, "po_line_not_found", f"We couldn't find {po_no} line {line_no}.")
    if line.status in ("received", "cancelled"):
        raise AppError(409, "po_not_open", f"{po_no} line {line_no} is {line.status}, so nothing is coming.")
    override = db.get(m.PoEtaOverride, (po_no, line_no))
    before = {"eta": override.eta, "note": override.note} if override else None

    if body.eta is None:
        if override is not None:
            db.delete(override)
            record_change(
                db,
                action="po_eta.clear",
                entity_type="po_eta_override",
                entity_id=f"{po_no}/{line_no}",
                before=before,
                after=None,
            )
        db.commit()
        return s.PoEtaOut(
            po_no=po_no,
            line_no=line_no,
            item_code=line.item_code,
            eta=None,
            note=None,
            updated_at=None,
            updated_by=None,
        )

    if body.eta < rules.as_of_date:
        raise AppError(
            422,
            "date_in_past",
            "That date has already passed. If the PO has arrived, it will show after the next BlueTide load.",
        )
    if override is None:
        override = m.PoEtaOverride(
            po_no=po_no, line_no=line_no, eta=body.eta, note=body.note, updated_by=current_actor()
        )
        db.add(override)
    else:
        override.eta = body.eta
        override.note = body.note
        override.updated_by = current_actor()
        override.updated_at = utc_now()  # type: ignore[assignment]
    db.flush()
    db.refresh(override)
    record_change(
        db,
        action="po_eta.set",
        entity_type="po_eta_override",
        entity_id=f"{po_no}/{line_no}",
        before=before,
        after={"eta": override.eta, "note": override.note},
    )
    db.commit()
    return s.PoEtaOut(
        po_no=po_no,
        line_no=line_no,
        item_code=line.item_code,
        eta=override.eta,
        note=override.note,
        updated_at=override.updated_at,
        updated_by=override.updated_by,
    )
