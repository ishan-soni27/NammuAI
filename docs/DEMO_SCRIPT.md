# Demo script: 10 minutes for Dana

**Audience:** Dana Okafor (VP Purchasing), skeptical and not technical. Her test (call, 00:11:00): "If I open it and it
doesn't make sense within about a minute, I go back to Excel."
**Goal:** she sees the Monday spreadsheet replaced:
- her two questions answered;
- one item's numbers she can check;
- telling the app what it doesn't know;
- next week's upload;
- the same screen on today's real date.
**Live link:** https://nammu-ai.vercel.app. "Today" is Boston's calendar date (ADR-034). The data is BlueTide's count of
**Sun Nov 15**, so the demo runs **as of Monday, Nov 16, 2026** (the header's **View as of**), then shows today at the
end.

Every number below was read from the live site, viewed as of Nov 16, on 2026-11-27. Viewed as of Nov 16, the numbers
don't change from day to day. They only change if someone edits something or uploads newer files. If newer files are
loaded, Nov 16 can no longer be viewed (the view starts the day after the latest count), so check the numbers again.

## Before the demo (5 minutes early)
1. Open https://nammu-ai.vercel.app/api/v1/health. It should say `"status":"ok","db":"ok"`, `"as_of"` = today's date
   and `"snapshot_date":"2026-11-15"`. The first call can take a few seconds to wake up.
2. Open the site and type **Dana** when it asks who's using it. In the header, set **View as of** to **11/16/2026**. A
   yellow strip says "Viewing as of Monday, November 16, 2026". The choice lasts for this tab only, so stay in it (a
   new tab opens on today).
3. Have BlueTide's stock and sales exports at hand (`data/raw/bluetide_inventory_on_hand.csv`,
   `bluetide_sales_lines.csv`) for the upload step.
4. Open the Monday screen with nothing expanded, and close other tabs.

## 0:00 to 1:00 · Monday: the two questions in one sentence
- **Say:** "This replaces your Monday spreadsheet. Read the top line."
- **She sees:**
  - the header: "Monday, November 16, 2026 · BlueTide count of Sun Nov 15 (yesterday)";
  - "3 items will run out before a new order can arrive. 1 order is overdue. 5 more need an order this week and 5
    should be ordered soon.";
  - the tiles: **3 Too late, 1 Overdue, 5 Order this week, 5 Order soon, 16 Fine, $108,799 inside the six-month
    line.**
- **Say:** "Red means it's too late, or the order date has passed. Yellow means order this week or soon. Green is fine.
  Nothing else." The Overdue one is lobster meat (LOB-MEAT): its order-by date was Fri Nov 13, so it's 3 days overdue,
  but an order today still lands before it runs out on Dec 11.
- Open "What this doesn't count" under the tiles: **420 cases on hold, 20 damaged, 78 expired, 59 of old ZZ stock and
  1,500 cases on late POs with no arrival date.** "These are the numbers your reports count and this one doesn't."

## 1:00 to 3:00 · The 16/20 shrimp, as numbers
- **Say:** "Last December you ran out of 16/20 shrimp ten days before Christmas (your words on the call). It says it's
  about to happen again."
- In **Too late**, click the card **White shrimp 16/20 ez peel 10X2 lb (SHR-1620)**. It opens to short labels:
  - Runs out **Mon Dec 14 (in 4 weeks)**;
  - Order at least **0 cases**;
  - New order lands **Mon Feb 8**;
  - Short **382 cases until Mon Jan 25**;
  - On hold **80 cases, not counted**.
- Click **See why and all the numbers**. The **Why** table, top to bottom:
  - Can sell now: **480 cases** (HCS 140 · NB 260 · PVD 80);
  - Not counted: **80** on hold;
  - Promised to customers: **201 cases**, 7 open orders; the largest is **Seabright Markets, 120 on Mon Dec 14**;
  - On the way: PO-260443 line 1: **600 cases, Mon Jan 25** (BlueTide says Mon Dec 28; the real lead time says later);
  - Selling now: **53 cases a week**; season ahead **Dec 1.6×**;
  - Runs out **Mon Dec 14**; a new order placed today lands **Mon Feb 8**;
  - Short: **382 cases** from Dec 14 until Jan 25, when the stock on the way lands;
  - Order at least: **0**, because an order today lands Feb 8, after that stock.
- **If she asks "where's that from?":** click the row's label. It jumps to the table with the source rows: every lot,
  every promised order, the PO with BlueTide's date struck through.
- Point at the chart: stock hits zero on Dec 14, the pink band is out of stock (Christmas sits inside it), and it's
  back at about **594 cases on Jan 25**.

## 3:00 to 4:00 · One instruction, and telling it what it doesn't know
- Back on Monday, open **SHR-2125** (21/25 shrimp). It reads: *"Order at least 127 cases, unless PO-260394 (800 cases)
  is really coming. Ask the supplier for its date and set it here, and these numbers update."*
- Click **On the way** in the menu. PO-260394 is at the top, **Late: not counted** (BlueTide said Mon Oct 5).
- Click **Set real date** and enter **Dec 4, 2026**, as if Bien Xanh confirmed it on the phone. Open SHR-2125 again:
  - the instruction is gone;
  - it's still too late (it runs out Nov 24);
  - but it's **short 123 cases until Dec 4** instead of 562 until Feb 8;
  - order at least is now **0**.
- **Undo before moving on:** on On the way, click **Clear date** on that line.
- Optional: on SHR-1620, **Mark as handled** with Quantity **400**, Arrives **Dec 4**. "Too late" shows **2**, and
  the item moves to Handled (grey), not hidden. Then **Clear this note**.

## 4:00 to 4:45 · Suppliers: "BlueTide says 8 weeks, you say 12"
- Click **Suppliers**. Bien Xanh Export Co. (Vietnam): **BlueTide says 8 weeks; you say 12 weeks to arrive**, plus a
  2-week cushion. "This is the number from your email. Change it here and every item from that supplier is recalculated."
- Optional: **Activity** shows every change, who made it and when, with before and after.

## 4:45 to 6:00 · What you're stuck with
- Back on Monday, right-hand list: **Atl salmon portion 6 oz skin-on (SAL-POR6)**, the Chilean salmon from Austral Frío.
  **1,350 cases, 1,050 of them at Harbor, $81,232 at cost, inside the six-month line.** "This is the stock you bought
  heavy over the summer."
- Top of the list, **Expired**: the 8 oz portions (SAL-POR8). 60 cases at Harbor expired on Oct 20, and its other 380
  cases at Harbor expire in March ($47,838 at cost for the item).
- Click **Harbor**: "2,095 cases of 14 items at Harbor now." Type a cases-per-pallet number for SAL-POR6 to show the
  cost appear. Say it's an example, because the real number is hers. With 60, it reads **18 pallets, $540 a month**.
  **Don't press Add to table** unless she wants to keep it.

## 6:00 to 7:00 · Any day: back to today
- **Say:** "You don't have to wait for Monday. Open it any day and it judges everything against today's date."
- Click **Back to today** in the yellow strip. On Fri Nov 27 it read as follows (the numbers move with the date, so
  check them the morning of the demo):
  - the header: "Friday, November 27, 2026 · BlueTide count of Sun Nov 15 (12 days ago)";
  - a yellow banner: "BlueTide's latest stock count is from Sun Nov 15, 12 days ago. Stock since then is estimated";
  - "1 item is probably out of stock now. 5 items will run out before a new order can arrive. 7 orders are
    overdue."
- Open **SHR-2125** under **Out of stock**:
  - "At the count (Sun Nov 15): 90 cases";
  - "Can sell now (estimated): 0 cases";
  - "Out of stock since about Tue Nov 24".
- **Say:** "If you skip a week, it doesn't go quiet. Things that have run out, or should have been ordered, turn red,
  and it asks for this week's files. After two weeks the banner turns red."
- Set **View as of** back to **11/16/2026** for the rest of the demo.

## 7:00 to 8:00 · Next Monday: the upload
- **Say:** "Next Monday you export BlueTide like always and drop the files here. Nothing changes until you've seen the
  check."
- Click **Data**, then **Load new BlueTide files**. Choose the stock file and the sales file (the others reuse last
  week's), then **Check these files**. She sees:
  - "Stock count in these files: Sun Nov 15 (N days ago) … Loaded, the numbers start from Mon Nov 16" (next week's
    files would say Mon Nov 23);
  - "Sales lines: 0 new, 0 changed, 15,750 the same, 0 older ones kept … 12.6 months of sales history";
  - a warning that it's the same night as the one loaded now, because these are this week's files.
- **Say:** "If BlueTide only exported the last few weeks of sales, the older history is kept, so the season pattern
  doesn't break."
- Click **Start over** (don't load in the demo; it would change nothing anyway).

## 8:00 to 9:00 · Data: everything it didn't count, and why
- On **Data**, open **What we cleaned up and why**: "4,047 notes from the latest load".
- Pick four she'll recognise:
  - **Transfers recorded as sales**: 378 rows that moved stock between buildings, not sales;
  - **Samples as $0 orders**: 104;
  - **the cruise line one-off**: 2 rows, kept out of the selling rate;
  - **hold and damaged**: 8 rows, not counted.
- "Every number on Monday traces back to these rules. Each one has the file and line it came from."
- **Download data notes for Excel** if she wants the list.

## 9:00 to 10:00 · Close
- "One screen on Monday morning that tells us what we need to order and what we're stuck with." (Walt, call 00:04:40.)
  "Every number clicks through to why, and BlueTide stays your system: you upload, look, adjust, and order the way
  you do today."
- **Next:**
  - a "what if the QA hold clears" switch;
  - a daily BlueTide export, so the estimate between counts barely matters;
  - flagging stock projected to expire before it sells;
  - suggested stockout weeks for her to confirm;
  - rounding orders to supplier minimums once we have them.
  The full list is in the README.
- Ask: "What would make you open this instead of Excel next Monday?"

## If something goes wrong
- **A slow first load or "couldn't reach the server":** wait 10 seconds and refresh. The site wakes up on the first call.
- **A number looks different from this script:** check the header first. Is it viewing Nov 16? A new tab opens on
  today. Otherwise someone changed something (a handled note, a supplier setting, a PO date), or a newer upload moved
  the count. **Activity** shows who changed what; undo it there or on the item page.
- **"You can view from … to today" error:** the view date is outside the range. Use **Back to today**, then pick Nov
  16 again (or the day after the latest count, if newer files were loaded).
- **Anything else:** each error shows a reference id. Note it and keep going on another page.
