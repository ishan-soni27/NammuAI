"""Dana's own spreadsheets, imported from the app's templates (Phase 6 step 3; ADR-029).

Ishan, 2026-11-26: the system "should be able to be its own independent system as well where Dana
can upload her own information which the system can then calculate with". So everything BlueTide
gives can also come from Dana, as simple CSV templates she downloads, fills in Excel and uploads:

    suppliers        supplier_code, name, country, weeks_to_arrive, cushion_weeks
    items            item_code, name, category, sold_by, lb_per_case, supplier_code, still_selling
    customers        customer_code, name, type
    stock_count      count_date, item_code, building, lot_no, quantity, expiry_date, unit_cost
    purchase_orders  po_no, supplier_code, order_date, expected_date, item_code, quantity, unit_cost
    sales_history    order_no, order_date, ship_date, customer_code, item_code, quantity, unit_price

The check validates every row (and rows in one file may use codes from another in the same import).
Any problem blocks the load, with the file, line and what to fix; the load is all-or-nothing in one
transaction. Her records win over BlueTide's on the same code. A stock count becomes the starting
stock for the items it lists, from its date (services/planning_inputs.py); sales history feeds the
selling rate (never stock: it's history).
"""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.business_rules import BusinessRules
from app.db import models as m
from app.db.sql import utc_now
from app.errors import AppError
from app.loader.normalize import canonical_code, normalize_category
from app.services.audit import current_actor


@dataclass(frozen=True)
class Template:
    slot: str
    label: str
    columns: tuple[str, ...]
    required: tuple[str, ...]


TEMPLATES: dict[str, Template] = {
    t.slot: t
    for t in (
        Template(
            "suppliers",
            "Suppliers",
            ("supplier_code", "name", "country", "weeks_to_arrive", "cushion_weeks"),
            ("name", "weeks_to_arrive", "cushion_weeks"),
        ),
        Template(
            "items",
            "Items",
            ("item_code", "name", "category", "sold_by", "lb_per_case", "supplier_code", "still_selling"),
            ("item_code", "name", "category", "sold_by", "supplier_code"),
        ),
        Template("customers", "Customers", ("customer_code", "name", "type"), ("name", "type")),
        Template(
            "stock_count",
            "Stock count",
            ("count_date", "item_code", "building", "lot_no", "quantity", "expiry_date", "unit_cost"),
            ("count_date", "item_code", "building", "lot_no", "quantity"),
        ),
        Template(
            "purchase_orders",
            "Purchase orders",
            ("po_no", "supplier_code", "order_date", "expected_date", "item_code", "quantity", "unit_cost"),
            ("po_no", "supplier_code", "order_date", "item_code", "quantity"),
        ),
        Template(
            "sales_history",
            "Sales history",
            ("order_no", "order_date", "ship_date", "customer_code", "item_code", "quantity", "unit_price"),
            ("order_no", "order_date", "customer_code", "item_code", "quantity"),
        ),
    )
}
LOAD_ORDER = ("suppliers", "items", "customers", "stock_count", "purchase_orders", "sales_history")


def template_csv(slot: str) -> str:
    """The empty template (just the header row), for Excel."""
    return ",".join(TEMPLATES[slot].columns) + "\r\n"


# ---- Reading ---------------------------------------------------------------------------------


def _rows(slot: str, content: bytes) -> list[tuple[int, dict[str, str]]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise AppError(
            422, "wrong_file", "That file isn't a text CSV. In Excel, save it as CSV UTF-8."
        ) from error
    reader = csv.DictReader(io.StringIO(text, newline=""))
    header = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
    t = TEMPLATES[slot]
    missing = [c for c in t.required if c not in header]
    if missing:
        raise AppError(
            422,
            "wrong_file",
            f"This doesn't look like the {t.label.lower()} template: it has no {', '.join(missing)} column. "
            "Download the template and keep its first row.",
        )
    out = []
    for row in reader:
        values = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items() if k}
        if any(values.values()):
            out.append((reader.line_num, values))
    return out


def count_rows(slot: str, content: bytes) -> int:
    rows = _rows(slot, content)
    if not rows:
        raise AppError(422, "file_empty", "That file has the header row but no rows.")
    return len(rows)


def _date(v: str) -> date | None:
    v = v.strip()
    if not v:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(v, fmt).date()  # parsing a typed date, not reading the clock
        except ValueError:
            continue
    raise ValueError(f"{v!r} isn't a date (use 2026-11-16 or 11/16/2026)")


def _num(v: str) -> Decimal | None:
    v = v.strip().replace(",", "").replace("$", "")
    if not v:
        return None
    try:
        return Decimal(v)
    except InvalidOperation as error:
        raise ValueError(f"{v!r} isn't a number") from error


def _yes(v: str) -> bool:
    return v.strip().lower() not in ("no", "n", "false", "0", "stopped")


# ---- Check -----------------------------------------------------------------------------------


@dataclass
class _Ctx:
    rules: BusinessRules
    vendors: set[str]
    items: dict[str, str]  # code -> sell uom
    customers: dict[str, str]  # code -> type
    locations: dict[str, str]  # code or lower-case name -> code
    app_pos: set[str]
    sales_done: set[tuple[str, str]]


def _context(db: Session, rules: BusinessRules) -> _Ctx:
    items = {i.item_code: i.sell_uom for i in db.scalars(select(m.Item)).all()}
    items.update({i.item_code: i.sell_uom for i in db.scalars(select(m.AppItem)).all()})
    customers = {c.customer_code: c.customer_type for c in db.scalars(select(m.Customer)).all()}
    customers.update({c.customer_code: c.customer_type for c in db.scalars(select(m.AppCustomer)).all()})
    locations: dict[str, str] = {}
    for loc in db.scalars(select(m.Location)).all():
        locations[loc.code.upper()] = loc.code
        locations[loc.name.strip().lower()] = loc.code
    return _Ctx(
        rules=rules,
        vendors=set(db.scalars(select(m.Vendor.vendor_code)).all())
        | set(db.scalars(select(m.AppVendor.vendor_code)).all()),
        items=items,
        customers=customers,
        locations=locations,
        app_pos=set(db.scalars(select(m.PurchaseOrder.po_no)).all()),
        sales_done={(x.order_no, x.item_code) for x in db.scalars(select(m.AppSalesLine)).all()},
    )


def _code_from_name(name: str, taken: set[str], fallback: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", name)
    base = "".join(w[0] for w in words).upper()[:4] or fallback
    code, n = base, 2
    while code in taken:
        code, n = f"{base}{n}", n + 1
    return code


def _parse_all(
    db: Session, rules: BusinessRules, up: m.Upload
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Every row of every uploaded template, parsed and checked. (rows by slot, problems, file summaries)."""
    files = {f.slot: f for f in db.scalars(select(m.UploadFile).where(m.UploadFile.upload_id == up.id)).all()}
    ctx = _context(db, rules)
    problems: list[dict[str, Any]] = []
    parsed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    summaries = []

    def bad(slot: str, line: int, message: str) -> None:
        problems.append({"slot": slot, "label": TEMPLATES[slot].label, "line": line, "message": message})

    for slot in LOAD_ORDER:
        f = files.get(slot)
        if f is None:
            continue
        rows = _rows(slot, f.content)
        summaries.append(
            {"slot": slot, "label": TEMPLATES[slot].label, "file_name": f.file_name, "rows": len(rows)}
        )
        seen: set[Any] = set()
        for line, r in rows:
            try:
                rec = _parse_row(slot, r, ctx, seen)
            except ValueError as error:
                bad(slot, line, str(error))
                continue
            rec["line"] = line
            parsed[slot].append(rec)
    return parsed, problems, summaries


def _need(r: dict[str, str], col: str) -> str:
    v = r.get(col, "").strip()
    if not v:
        raise ValueError(f"{col.replace('_', ' ')} is blank")
    return v


def _parse_row(slot: str, r: dict[str, str], ctx: _Ctx, seen: set[Any]) -> dict[str, Any]:
    """One row, checked against what exists (and what earlier files in this import add)."""
    rules = ctx.rules
    today = rules.as_of_date
    if slot == "suppliers":
        name = _need(r, "name")
        weeks, cushion = _num(_need(r, "weeks_to_arrive")), _num(_need(r, "cushion_weeks"))
        assert weeks is not None and cushion is not None
        lead, safety = round(weeks * 7), round(cushion * 7)
        for label, days in (("weeks to arrive", lead), ("cushion weeks", safety)):
            if not rules.setting_days_min <= days <= rules.setting_days_max:
                raise ValueError(
                    f"{label} must be between {rules.setting_days_min} and {rules.setting_days_max} days"
                )
        code = canonical_code(r.get("supplier_code", "")) or _code_from_name(name, ctx.vendors | seen, "SUP")
        if code in seen:
            raise ValueError(f"supplier {code} is in this file twice")
        seen.add(code)
        ctx.vendors.add(code)
        return {
            "code": code,
            "name": name,
            "country": r.get("country") or None,
            "lead": lead,
            "safety": safety,
        }
    if slot == "items":
        code = canonical_code(_need(r, "item_code"))
        if code in seen:
            raise ValueError(f"item {code} is in this file twice")
        sold_by = _need(r, "sold_by").lower()
        uom = (
            "CS"
            if sold_by in ("case", "cases", "cs")
            else "LB"
            if sold_by in ("lb", "lbs", "pound", "pounds")
            else None
        )
        if uom is None:
            raise ValueError("sold by must be case or lb")
        lb = _num(r.get("lb_per_case", ""))
        if uom == "CS" and not lb:
            raise ValueError("pounds per case is needed for items sold by the case")
        if lb is not None and lb <= 0:
            raise ValueError("pounds per case must be more than 0")
        vendor = canonical_code(_need(r, "supplier_code"))
        if vendor not in ctx.vendors:
            raise ValueError(
                f"supplier {vendor} doesn't exist (add it in the suppliers file or on the Suppliers page)"
            )
        seen.add(code)
        ctx.items[code] = uom
        return {
            "code": code,
            "name": _need(r, "name"),
            "category": normalize_category(_need(r, "category")),
            "uom": uom,
            "lb": lb,
            "vendor": vendor,
            "active": _yes(r.get("still_selling", "yes") or "yes"),
        }
    if slot == "customers":
        name = _need(r, "name")
        ctype = _need(r, "type").upper()
        if ctype == rules.internal_customer_type.upper():
            raise ValueError("our own buildings aren't customers (use Move stock)")
        code = canonical_code(r.get("customer_code", "")) or _code_from_name(
            name, set(ctx.customers) | seen, "CUST"
        )
        if code in seen:
            raise ValueError(f"customer {code} is in this file twice")
        seen.add(code)
        ctx.customers[code] = ctype
        return {"code": code, "name": name, "type": ctype}
    if slot == "stock_count":
        count_date = _date(_need(r, "count_date"))
        assert count_date is not None
        if count_date > today:
            raise ValueError("the count date is after today")
        item = canonical_code(_need(r, "item_code"))
        if item not in ctx.items:
            raise ValueError(f"item {item} doesn't exist (add it in the items file or on the Items page)")
        building_raw = _need(r, "building")
        building = ctx.locations.get(building_raw.upper()) or ctx.locations.get(building_raw.lower())
        if building is None:
            raise ValueError(f"building {building_raw!r} isn't one of ours")
        lot = _need(r, "lot_no")
        key = (count_date, item, building, lot)
        if key in seen:
            raise ValueError(f"lot {lot} of {item} at {building} is counted twice")
        seen.add(key)
        qty = _num(_need(r, "quantity"))
        assert qty is not None
        if qty < 0:
            raise ValueError("quantity can't be negative")
        cost = _num(r.get("unit_cost", ""))
        return {
            "date": count_date,
            "item": item,
            "building": building,
            "lot": lot,
            "qty": qty,
            "expiry": _date(r.get("expiry_date", "")),
            "cost": cost,
        }
    if slot == "purchase_orders":
        po = canonical_code(_need(r, "po_no"))
        if po in ctx.app_pos:
            raise ValueError(f"PO {po} is already in the app")
        vendor = canonical_code(_need(r, "supplier_code"))
        if vendor not in ctx.vendors:
            raise ValueError(f"supplier {vendor} doesn't exist")
        order_date = _date(_need(r, "order_date"))
        assert order_date is not None
        if order_date > today:
            raise ValueError("the order date is after today")
        expected = _date(r.get("expected_date", ""))
        if expected is not None and expected < today:
            raise ValueError(
                "the expected date has passed (leave it blank, or type the date the supplier gave)"
            )
        item = canonical_code(_need(r, "item_code"))
        if item not in ctx.items:
            raise ValueError(f"item {item} doesn't exist")
        if (po, item) in seen:
            raise ValueError(f"{item} is on PO {po} twice")
        seen.add((po, item))
        qty = _num(_need(r, "quantity"))
        if qty is None or qty <= 0:
            raise ValueError("quantity must be more than 0")
        return {
            "po": po,
            "vendor": vendor,
            "order_date": order_date,
            "expected": expected,
            "item": item,
            "qty": qty,
            "cost": _num(r.get("unit_cost", "")),
        }
    # sales_history
    order = _need(r, "order_no")
    order_date = _date(_need(r, "order_date"))
    assert order_date is not None
    if order_date > today:
        raise ValueError("the order date is after today")
    ship = _date(r.get("ship_date", ""))
    if ship is not None and (ship > today or ship < order_date):
        raise ValueError("the ship date must be between the order date and today")
    customer = canonical_code(_need(r, "customer_code"))
    if customer not in ctx.customers:
        raise ValueError(f"customer {customer} doesn't exist (add them in the customers file)")
    item = canonical_code(_need(r, "item_code"))
    if item not in ctx.items:
        raise ValueError(f"item {item} doesn't exist")
    if (order, item) in seen or (order, item) in ctx.sales_done:
        raise ValueError(f"{item} on order {order} is already in the sales history")
    seen.add((order, item))
    qty = _num(_need(r, "quantity"))
    if qty is None or qty <= 0:
        raise ValueError("quantity must be more than 0")
    return {
        "order": order,
        "order_date": order_date,
        "ship": ship,
        "customer": customer,
        "item": item,
        "qty": qty,
        "price": _num(r.get("unit_price", "")),
    }


def check(db: Session, rules: BusinessRules, up: m.Upload) -> dict[str, Any]:
    parsed, problems, files = _parse_all(db, rules, up)
    blockers = (
        [
            f"{len(problems):,} {'rows have problems' if len(problems) != 1 else 'row has a problem'}. "
            "Fix them in the file and upload it again; nothing is loaded until every row is right."
        ]
        if problems
        else []
    )
    existing_vendors = set(db.scalars(select(m.AppVendor.vendor_code)).all()) | set(
        db.scalars(select(m.Vendor.vendor_code)).all()
    )
    existing_items = set(db.scalars(select(m.AppItem.item_code)).all()) | set(
        db.scalars(select(m.Item.item_code)).all()
    )
    existing_customers = set(db.scalars(select(m.AppCustomer.customer_code)).all()) | set(
        db.scalars(select(m.Customer.customer_code)).all()
    )
    changes = []
    for slot, label, existing in (
        ("suppliers", "Suppliers", existing_vendors),
        ("items", "Items", existing_items),
        ("customers", "Customers", existing_customers),
    ):
        rows = parsed.get(slot, [])
        if rows:
            updated = sum(1 for r in rows if r["code"] in existing)
            changes.append({"what": f"{label}: new", "count": len(rows) - updated})
            changes.append({"what": f"{label}: updated (yours win over BlueTide's)", "count": updated})
    if parsed.get("stock_count"):
        dates = sorted({r["date"] for r in parsed["stock_count"]})
        changes.append(
            {
                "what": f"Stock count lots ({', '.join(d.isoformat() for d in dates)})",
                "count": len(parsed["stock_count"]),
            }
        )
    if parsed.get("purchase_orders"):
        changes.append(
            {"what": "Purchase orders", "count": len({r["po"] for r in parsed["purchase_orders"]})}
        )
    if parsed.get("sales_history"):
        changes.append({"what": "Sales history lines", "count": len(parsed["sales_history"])})
    warnings = []
    snapshot = _snapshot(db)
    if snapshot and any(r["date"] <= snapshot for r in parsed.get("stock_count", [])):
        warnings.append(
            f"BlueTide's stock count ({snapshot.isoformat()}) is as new as or newer than this count. "
            "For items in "
            "both, BlueTide's stays the starting stock; your count applies to items only you count."
        )
    return {
        "kind": "template",
        "files": files,
        "blockers": blockers,
        "warnings": warnings,
        "problems": problems[:200],
        "changes": changes,
    }


def _snapshot(db: Session) -> date | None:
    run = db.scalars(
        select(m.LoadRun).where(m.LoadRun.status == "succeeded").order_by(m.LoadRun.id.desc()).limit(1)
    ).first()
    snap = (run.summary or {}).get("snapshot_date") if run else None
    return date.fromisoformat(snap) if snap else None


# ---- Load (one transaction; the caller commits) -----------------------------------------------


def load(db: Session, rules: BusinessRules, up: m.Upload) -> dict[str, Any]:
    parsed, problems, _ = _parse_all(db, rules, up)
    if problems:
        raise AppError(409, "blocked", "Some rows have problems now. Check the files again.")
    actor = current_actor()
    counts: dict[str, int] = defaultdict(int)
    for r in parsed.get("suppliers", []):
        mine = db.get(m.AppVendor, r["code"])
        if mine is None:
            db.add(
                m.AppVendor(
                    vendor_code=r["code"],
                    name=r["name"],
                    country=r["country"],
                    created_by=actor,
                    updated_by=actor,
                )
            )
        else:
            mine.name, mine.country, mine.updated_by = r["name"], r["country"], actor
            mine.updated_at = utc_now()  # type: ignore[assignment]
        setting = db.get(m.VendorSetting, r["code"])
        if setting is None:
            db.add(
                m.VendorSetting(
                    vendor_code=r["code"],
                    lead_time_days=r["lead"],
                    safety_days=r["safety"],
                    order_cycle_days=rules.default_order_cycle_days,
                    source=f"Imported by {actor}",
                    updated_by=actor,
                )
            )
        else:
            setting.lead_time_days, setting.safety_days = r["lead"], r["safety"]
            setting.source, setting.updated_by = f"Imported by {actor}", actor
            setting.updated_at = utc_now()  # type: ignore[assignment]
        counts["suppliers"] += 1
    db.flush()
    for r in parsed.get("items", []):
        item = db.get(m.AppItem, r["code"])
        fields = {
            "description": r["name"],
            "category": r["category"],
            "sell_uom": r["uom"],
            "lb_per_case": r["lb"],
            "vendor_code": r["vendor"],
            "status": "active" if r["active"] else "discontinued",
        }
        if item is None:
            db.add(m.AppItem(item_code=r["code"], created_by=actor, updated_by=actor, **fields))
        else:
            for k, v in fields.items():
                setattr(item, k, v)
            item.updated_by = actor
            item.updated_at = utc_now()  # type: ignore[assignment]
        counts["items"] += 1
    for r in parsed.get("customers", []):
        c = db.get(m.AppCustomer, r["code"])
        if c is None:
            db.add(
                m.AppCustomer(
                    customer_code=r["code"],
                    name=r["name"],
                    customer_type=r["type"],
                    created_by=actor,
                    updated_by=actor,
                )
            )
        else:
            c.name, c.customer_type, c.updated_by = r["name"], r["type"], actor
        counts["customers"] += 1
    db.flush()
    by_date: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for r in parsed.get("stock_count", []):
        by_date[r["date"]].append(r)
    for count_date, rows in by_date.items():
        sc = m.StockCount(count_date=count_date, upload_id=up.id, created_by=actor)
        db.add(sc)
        db.flush()
        for r in rows:
            db.add(
                m.StockCountLine(
                    count_id=sc.id,
                    item_code=r["item"],
                    location_code=r["building"],
                    lot_no=r["lot"],
                    qty=r["qty"],
                    expiry_date=r["expiry"],
                    unit_cost=r["cost"],
                )
            )
            counts["stock_count_lines"] += 1
    by_po: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in parsed.get("purchase_orders", []):
        by_po[r["po"]].append(r)
    for po_no, rows in by_po.items():
        first = rows[0]
        po = m.PurchaseOrder(
            po_no=po_no,
            vendor_code=first["vendor"],
            order_date=first["order_date"],
            note="Imported",
            created_by=actor,
            updated_by=actor,
        )
        db.add(po)
        db.flush()
        setting = db.get(m.VendorSetting, first["vendor"])
        lead = setting.lead_time_days if setting else rules.default_lead_time_days
        for n, r in enumerate(rows, start=1):
            db.add(
                m.PurchaseOrderLineApp(
                    po_id=po.id, line_no=n, item_code=r["item"], qty_ordered=r["qty"], unit_cost=r["cost"]
                )
            )
            eta = r["expected"] or (r["order_date"] + timedelta(days=lead))
            if eta >= rules.as_of_date:
                db.add(m.PoEtaOverride(po_no=po_no, line_no=n, eta=eta, note="Imported", updated_by=actor))
        counts["purchase_orders"] += 1
    by_order: dict[str, int] = defaultdict(int)
    for r in parsed.get("sales_history", []):
        by_order[r["order"]] += 1
        db.add(
            m.AppSalesLine(
                upload_id=up.id,
                order_no=r["order"],
                line_no=by_order[r["order"]],
                order_date=r["order_date"],
                ship_date=r["ship"],
                customer_code=r["customer"],
                item_code=r["item"],
                qty=r["qty"],
                unit_price=r["price"],
                created_by=actor,
            )
        )
        counts["sales_history_lines"] += 1
    db.flush()
    return dict(counts)
