"""Request dependencies shared by the routers.

`request_rules`: the business rules for this request, with "today" following the data (ADR-032):
the day after the latest successful load's BlueTide stock count (business_rules.rules_for_snapshot,
cached per snapshot, so in practice once per load). The AS_OF_DATE override still wins if set.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config.business_rules import BusinessRules, rules_for_snapshot
from app.db.session import get_db
from app.services.planning_inputs import latest_load


def request_rules(db: Session = Depends(get_db)) -> BusinessRules:
    return rules_for_snapshot(latest_load(db).snapshot_date)
