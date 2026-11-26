"""Print the planning engine's results next to the answer key in BUILD_PROMPT §7.

The answer key came from a ROUGH pandas model in the planning chat. It is a sanity check, NOT a
target (BUILD_PROMPT §0 rule 5: never tune logic to match it). This script exists to EXPLAIN
differences. It runs the engine three ways:

  current   the rules as they are today (Dana's late-PO answer; open orders in the rate per §6.2)
  key-like  late POs assumed to arrive in 7 days, as the answer key (and the email default) did
  once      open orders counted once (on their ship date only), not also in the selling rate

Run from the repo root with the backend's Python (no database needed; reads data/raw):
    backend/.venv/bin/python scripts/compare_answer_key.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config.business_rules import BusinessRules  # noqa: E402
from app.loader.pipeline import build_dataset  # noqa: E402
from app.loader.read_raw import read_all_raw  # noqa: E402
from app.loader.reference import load_reference  # noqa: E402
from app.planning.engine import plan  # noqa: E402
from app.services.planning_inputs import inputs_from_dataset  # noqa: E402

# BUILD_PROMPT §7: (item, expected status, expected run-out "about")
ORDER_KEY = [
    ("SHR-2125", "TOO_LATE", date(2026, 11, 21)),
    ("LOB-T56", "TOO_LATE", date(2026, 11, 25)),
    ("SHR-1620", "TOO_LATE", date(2026, 12, 14)),
    ("PAN-0507", "TOO_LATE", date(2026, 12, 27)),
    ("CRAB-SNW5", "ORDER_THIS_WEEK", date(2026, 11, 30)),
    ("LOB-MEAT", "ORDER_THIS_WEEK", date(2026, 12, 7)),
    ("HAD-FIL", "ORDER_THIS_WEEK", date(2026, 12, 9)),
    ("POL-FIL", "ORDER_THIS_WEEK", date(2026, 12, 26)),
    ("SAL-SIDE-SK", "ORDER_THIS_WEEK", date(2027, 1, 5)),
]
SHORT = {
    "TOO_LATE": "too late",
    "ORDER_THIS_WEEK": "this week",
    "ORDER_SOON": "soon",
    "OK": "fine",
    "NO_RECENT_SALES": "no sales",
    "NOT_PLANNED": "not planned",
}


def main() -> None:
    rules = BusinessRules()
    ref = load_reference()
    inputs = inputs_from_dataset(build_dataset(read_all_raw(), ref, rules).dataset, ref.vendor_settings)
    runs = {
        "current": plan(inputs, rules),
        "key-like": plan(inputs, replace(rules, late_po_assumed_days=7)),
        "once": plan(inputs, replace(rules, open_orders_in_selling_rate=False)),
    }
    by_item = {name: {p.item.item_code: p for p in r.items} for name, r in runs.items()}

    print("WHAT TO ORDER (answer key vs engine; Δ = engine run-out minus key, in days)\n")
    print(f"{'item':12} {'key':22} " + " ".join(f"{name:26}" for name in runs))
    for code, status, about in ORDER_KEY:
        cells = []
        for name in runs:
            p = by_item[name][code]
            ro = p.confirmed.run_out_date
            delta = f"{(ro - about).days:+d}d" if ro else "  —"
            shown = str(ro) if ro else ">6 mo"  # str() first: a date with a width spec goes through strftime
            cells.append(f"{SHORT[p.confirmed.status]:9} {shown:10} {delta:>4}".ljust(26))
        print(f"{code:12} {SHORT[status]:10} {about!s:11} " + " ".join(cells))

    urgent_now = {
        p.item.item_code
        for p in runs["current"].items
        if p.confirmed.status in {"TOO_LATE", "ORDER_THIS_WEEK"}
    }
    extra = sorted(urgent_now - {c for c, _, _ in ORDER_KEY})
    print("\nIn today's order list but not in the key's:", ", ".join(extra) or "none")
    flagged = [p.item.item_code for p in runs["current"].items if p.covered_only_by_late_po]
    print("Covered only by a late PO (Dana's Q3):", ", ".join(flagged) or "none")

    print("\nWHAT YOU'RE STUCK WITH (current rules)\n")
    for s in runs["current"].stuck:
        print(
            f"  {s.item_code:12} {s.primary_tag:18} {s.qty:7,.0f} {s.sell_uom.lower()}"
            f"  at Harbor {s.qty_at_harbor:6,.0f}  ${s.value_at_cost:>9,.0f}"
        )
    t = runs["current"].trust
    print(
        f"\nTRUST STRIP: on hold {t.on_hold}, damaged {t.damaged}, expired {t.expired}, old ZZ {t.legacy}, "
        f"late POs not counted {t.late_po_qty}"
    )
    print(
        "Key: 420 cs on hold, 20 damaged, 78 expired, 59 ZZ; SAL-POR6 1,350 cs (1,050 at Harbor, ~$81K); "
        "SHR-1620 at Harbor NOT stuck."
    )


if __name__ == "__main__":
    main()
