# Dana's replies

> Ishan pastes Dana's replies here exactly as received, newest at the bottom, with the date received.
> After each reply: update the matching seed CSV or `business_rules.py`, flip the row in `docs/ASSUMPTIONS.md`
> from "Pending Dana" to "Confirmed by Dana (date)", re-run the loader if needed, update tests, and log it in
> `docs/PROMPT_LOG.md` (BUILD_PROMPT §4.4).

---

## Reply 1, received 2026-11-26 (answers the six questions in `email-to-dana.md`)

```
Hi Ishan,

1. Those are all right. Use the full 12 for Vietnam.
2. One week is right for all three.
3. They're still coming, but I can't tell you which week. The dates are the vendor's original quote and nobody updates them. Flag them as late, but please don't assume they'll arrive within a week. If an item is only covered by a late PO, I want to see that.
4. I can't say when or if they'll be released. Some of it passes and comes back, but until it does I can't sell it. So yes, leave it out and show it separately.
5. Yes, we've stopped carrying all three. Flag what's left at Harbor so I can clear it.
6. No, just the 16/20

P.S. Harbor charges $30 per pallet per month.

Thanks,
Dana
```

### What each answer changed

| Q | Dana said | Our default was | Result | Where |
|---|---|---|---|---|
| 1 Lead times | All right; full 12 weeks for Vietnam | Alaska 4 wk, Maine 3 wk, Vietnam 12 wk | **Confirmed.** No number changes | `vendor_settings_seed.csv`, A01 |
| 2 Cushion | One week is right for all three | 1 week for Canada, Alaska, Maine | **Confirmed.** No number changes | `vendor_settings_seed.csv`, A02 |
| 3 Late POs | Still coming, week unknown. Flag as late, **don't assume within a week**, show items only covered by a late PO | Assume arrival 7 days after today | **Rule changed.** A late PO is not counted as coming until Dana types a real date. It stays flagged, and any item that only a late PO would cover is called out. | `late_po_assumed_days = None` in `business_rules.py`, A03 |
| 4 QA-HOLD | Can't sell it until released; leave it out, show separately | Not counted, shown separately | **Confirmed** | `locations.csv`, A04 |
| 5 Stopped items | Stopped carrying all three; flag what's left at Harbor so she can clear it | Treated as stopped selling | **Confirmed.** The Harbor stock of these items is called out in "stuck with" | `dormant_no_sales_days`, A05 |
| 6 Other stockouts | No, just the 16/20 | Only SHR-1620 | **Confirmed** | `stockout_periods.csv`, A06 |
| P.S. Harbor cost | $30 per pallet per month | Hidden until known | **Rate known.** We still need pallets (or cases per pallet) per item to turn stock into $ per month; see A16 | A16 |
