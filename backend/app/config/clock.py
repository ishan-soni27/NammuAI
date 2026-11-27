"""The one place the app reads the clock for a BUSINESS date (ADR-034).

"Today" is Boston's calendar date (Kestrel Bay is in New Bedford, MA). The server runs in UTC, so a
plain date.today() would flip to tomorrow at 7 or 8 pm Boston time; reading the date in the
business timezone avoids that. Everything else gets "today" from BusinessRules.as_of_date, never
from the clock (tests/unit/test_invariants.py enforces this outside app/config/).

Overrides: AS_OF_DATE in the environment (tests, a fixed demo) and a viewer's "view as of" date
(X-As-Of, per request) both replace it; see business_rules.server_today and api/deps.request_rules.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


def business_today(timezone: str) -> date:
    """Today's date in `timezone` (e.g. "America/New_York"), with daylight saving handled by zoneinfo."""
    return datetime.now(ZoneInfo(timezone)).date()  # clock-ok: the one sanctioned read (ADR-034)
