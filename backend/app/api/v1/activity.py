"""Data notes, activity and settings: the "show me why" pages (BUILD_PROMPT §8.5, §9.4, §10).

GET  /data-issues/summary   what we cleaned up and why, grouped by trap (latest successful load)
GET  /data-issues           the individual rows, filterable, each with its original CSV values
GET  /audit-log             who changed what, before and after
GET  /events                notable events and errors (api, loader, web)
GET  /load-runs             every load attempt, with file checksums and counts
GET  /settings              the business rules and where each number comes from (read-only in v1)
POST /client-events         the website reports its own errors here (source "web")
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import request_rules
from app.api.v1 import schemas as s
from app.config.business_rules import BusinessRules
from app.db import models as m
from app.db.session import get_db
from app.loader.report import TRAP_TITLES
from app.services.audit import record_event
from app.services.planning_inputs import latest_load

router = APIRouter(tags=["Data notes, activity and settings"])


@router.get("/data-issues/summary", response_model=s.DataIssueSummaryOut)
def data_issue_summary(db: Session = Depends(get_db)) -> s.DataIssueSummaryOut:
    run_id = latest_load(db).load_run_id
    if run_id is None:
        return s.DataIssueSummaryOut(load_run_id=None, total=0, by_trap=[])
    rows = db.execute(
        select(
            m.DataIssue.trap_id,
            m.DataIssue.rule_code,
            m.DataIssue.severity,
            m.DataIssue.action,
            func.count(),
            func.min(m.DataIssue.message),
        )
        .where(m.DataIssue.load_run_id == run_id)
        .group_by(m.DataIssue.trap_id, m.DataIssue.rule_code, m.DataIssue.severity, m.DataIssue.action)
    ).all()
    traps: dict[str | None, list[s.IssueRuleOut]] = {}
    for trap_id, rule, severity, action, count, example in rows:
        traps.setdefault(trap_id, []).append(
            s.IssueRuleOut(rule_code=rule, severity=severity, action=action, count=count, example=example)
        )
    by_trap = [
        s.IssueTrapOut(
            trap_id=trap_id,
            title=TRAP_TITLES.get(trap_id or "", "Rows we couldn't read"),
            count=sum(r.count for r in rules),
            rules=sorted(rules, key=lambda r: -r.count),
        )
        for trap_id, rules in sorted(traps.items(), key=lambda kv: kv[0] or "zz")
    ]
    return s.DataIssueSummaryOut(load_run_id=run_id, total=sum(t.count for t in by_trap), by_trap=by_trap)


@router.get("/data-issues", response_model=s.DataIssuePage)
def list_data_issues(
    trap_id: str | None = None,
    file: str | None = None,
    item: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> s.DataIssuePage:
    run_id = latest_load(db).load_run_id
    if run_id is None:
        return s.DataIssuePage(total=0, limit=limit, offset=offset, items=[])
    filters = [m.DataIssue.load_run_id == run_id]
    if trap_id:
        filters.append(m.DataIssue.trap_id == trap_id.upper())
    if file:
        filters.append(m.DataIssue.source_file == file)
    if item:
        filters.append(m.DataIssue.item_code == item.strip().upper())
    total = db.execute(select(func.count()).select_from(m.DataIssue).where(*filters)).scalar_one()
    rows = db.execute(
        select(m.DataIssue, m.RawRow.data)
        .outerjoin(m.RawRow, m.RawRow.id == m.DataIssue.raw_row_id)
        .where(*filters)
        .order_by(m.DataIssue.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return s.DataIssuePage(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            s.DataIssueOut(
                id=i.id,
                source_file=i.source_file,
                source_line_number=i.source_line_number,
                trap_id=i.trap_id,
                rule_code=i.rule_code,
                severity=i.severity,
                action=i.action,
                item_code=i.item_code,
                field=i.field,
                original_value=i.original_value,
                new_value=i.new_value,
                message=i.message,
                raw=raw,
            )
            for i, raw in rows
        ],
    )


@router.get("/audit-log", response_model=list[s.AuditOut])
def audit_log(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)) -> list[s.AuditOut]:
    rows = db.scalars(select(m.AuditLog).order_by(m.AuditLog.id.desc()).limit(limit)).all()
    return [s.AuditOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/events", response_model=list[s.EventOut])
def events(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)) -> list[s.EventOut]:
    rows = db.scalars(select(m.EventLog).order_by(m.EventLog.id.desc()).limit(limit)).all()
    return [s.EventOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/load-runs", response_model=list[s.LoadRunOut])
def load_runs(db: Session = Depends(get_db)) -> list[s.LoadRunOut]:
    rows = db.scalars(select(m.LoadRun).order_by(m.LoadRun.id.desc())).all()
    return [s.LoadRunOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/settings", response_model=list[s.RuleOut])
def settings(rules: BusinessRules = Depends(request_rules)) -> list[s.RuleOut]:
    return [s.RuleOut(**rule) for rule in rules.describe()]


@router.post("/client-events", status_code=202)
def client_event(body: s.ClientEventIn, db: Session = Depends(get_db)) -> dict[str, str]:
    record_event(db, level=body.level, source="web", event=body.event, details=body.details)
    db.commit()
    return {"status": "accepted"}
