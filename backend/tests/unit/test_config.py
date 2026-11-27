"""Settings and business rules: AS_OF comes from config (never the clock), every rule is explained."""

from __future__ import annotations

import dataclasses
from datetime import date

import pytest

from app.config.business_rules import BusinessRules, get_business_rules
from app.config.settings import Settings
from tests.conftest import clear_config_caches


def test_as_of_defaults_to_monday_nov_16_2026() -> None:
    assert get_business_rules().as_of_date == date(2026, 11, 16)


def test_as_of_comes_from_env_not_the_system_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    # Invariant #1: "today" is configuration. Changing the env changes "today"; the clock doesn't matter.
    monkeypatch.setenv("AS_OF_DATE", "2027-01-04")
    clear_config_caches()
    assert get_business_rules().as_of_date == date(2027, 1, 4)


def test_every_rule_has_an_explanation_and_a_source() -> None:
    # GET /settings shows these to Dana; an undocumented number would be a magic number.
    for f in dataclasses.fields(BusinessRules):
        assert f.metadata.get("doc"), f"{f.name} has no plain-English explanation"
        assert f.metadata.get("source"), f"{f.name} has no source"


def test_rule_defaults_match_build_prompt_section_6() -> None:
    r = BusinessRules()
    assert (r.six_month_line_months, r.dormant_no_sales_days, r.base_window_days) == (6, 60, 56)
    assert (r.seasonal_window_days, r.seasonal_index_min, r.seasonal_index_max) == (365, 0.4, 2.5)
    assert (r.projection_horizon_days, r.cover_forecast_days) == (182, 91)
    assert (r.order_this_week_days, r.order_soon_days) == (7, 21)
    # Dana 2026-11-26: late POs are NOT assumed to arrive (the email default was 7 days).
    assert r.late_po_assumed_days is None
    assert (r.default_lead_time_days, r.default_safety_days, r.default_order_cycle_days) == (28, 7, 7)
    assert (r.overstock_weeks, r.harbor_long_weeks) == (26, 12)


def test_rules_are_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        get_business_rules().overstock_weeks = 1  # type: ignore[misc]


def test_fingerprint_changes_when_a_rule_changes() -> None:
    base = BusinessRules()
    assert base.fingerprint() == BusinessRules().fingerprint()
    assert base.fingerprint() != dataclasses.replace(base, overstock_weeks=30).fingerprint()


def test_describe_lists_every_rule_with_value_and_source() -> None:
    described = {d["name"]: d for d in BusinessRules().describe()}
    assert described["as_of_date"]["value"] == "2026-11-16"
    assert described["six_month_line_months"]["unit"] == "months"
    assert len(described) == len(dataclasses.fields(BusinessRules))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgresql://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
        ("postgres://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("  postgresql://u:p@h/db  ", "postgresql+psycopg://u:p@h/db"),
        ("", ""),
    ],
)
def test_database_url_uses_psycopg3_driver(raw: str, expected: str) -> None:
    assert Settings(database_url=raw).database_url == expected


def test_cors_origins_are_split_and_trailing_slashes_removed() -> None:
    s = Settings(cors_origins="https://kestrel.vercel.app/, http://localhost:5173 ,")
    assert s.cors_origin_list == ["https://kestrel.vercel.app", "http://localhost:5173"]


# ---- "Today" is Boston's calendar date (ADR-034) ---------------------------------------------------


def test_today_is_bostons_date_not_utcs(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime

    from app.config import clock

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001, ANN206
            # 04:30 UTC on Nov 27 is still 11:30 pm on Nov 26 in Boston (EST, UTC-5).
            return datetime(2026, 11, 27, 4, 30, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(clock, "datetime", Frozen)
    assert clock.business_today("America/New_York") == date(2026, 11, 26)
    assert clock.business_today("UTC") == date(2026, 11, 27)


def test_daylight_saving_is_handled(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime

    from app.config import clock

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001, ANN206
            # 03:30 UTC on Jul 1 is 11:30 pm on Jun 30 in Boston (EDT, UTC-4).
            return datetime(2027, 7, 1, 3, 30, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(clock, "datetime", Frozen)
    assert clock.business_today("America/New_York") == date(2027, 6, 30)


def test_server_today_reads_the_clock_unless_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import business_rules as br

    monkeypatch.setenv("AS_OF_DATE", "")
    clear_config_caches()
    monkeypatch.setattr(
        br, "business_today", lambda tz: date(2026, 12, 7) if tz == "America/New_York" else None
    )
    assert br.server_today() == date(2026, 12, 7)
    monkeypatch.setenv("AS_OF_DATE", "2026-11-16")
    clear_config_caches()
    assert br.server_today() == date(2026, 11, 16)


def test_rules_carry_today_and_the_data_date() -> None:
    from app.config.business_rules import rules_for, rules_for_load

    r = rules_for(date(2026, 11, 15), date(2026, 11, 27))
    assert (r.as_of_date, r.data_date, r.day_zero, r.days_since_data) == (
        date(2026, 11, 27),
        date(2026, 11, 16),
        date(2026, 11, 16),
        11,
    )
    same = rules_for(date(2026, 11, 15), date(2026, 11, 16))
    assert same.days_since_data == 0
    # A count newer than "today" (a clock override older than the data) moves today up to the data.
    assert rules_for(date(2026, 11, 22), date(2026, 11, 16)).as_of_date == date(2026, 11, 23)
    assert rules_for(None, date(2026, 11, 27)).data_date == date(2026, 11, 27)  # no load: no gap
    load = rules_for_load(date(2026, 11, 22))
    assert (load.as_of_date, load.data_date) == (date(2026, 11, 23), date(2026, 11, 23))
