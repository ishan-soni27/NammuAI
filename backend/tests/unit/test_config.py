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
