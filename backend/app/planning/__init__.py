"""The planning engine: PURE functions over dataclasses (no database, no clock, no I/O).

BUILD_PROMPT §8.4 / ADR-004. Inputs come in as plain dataclasses; results go out as
dataclasses. That keeps every rule unit-testable with tiny fixtures and easy to change
live. Phase 2 adds the on-hand breakdown (supply.py) and date helpers (calendar.py); Phase 3
adds seasonality, demand, projection, ordering, stuck and explain.
"""
