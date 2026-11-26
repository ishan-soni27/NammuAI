# Demo script: 10 minutes for Dana

**Audience:** Dana Okafor (VP Purchasing), skeptical and not technical. Her test (call, 00:11:00): "If I open it and it
doesn't make sense within about a minute, I go back to Excel."
**Goal:** she sees her two Monday questions answered, clicks into one item and believes the number, and sees she can
tell the app what it doesn't know.
**Live link:** https://nammu-ai.vercel.app (business day fixed at **Monday, Nov 16, 2026**).

Every number below was read from the live site on 2026-11-26 (load run #7). If the data is reloaded, check the numbers
again before the demo.

## Before the demo (5 minutes early)
1. Open https://nammu-ai.vercel.app/api/v1/health. It should say `"status":"ok","db":"ok"`. The first call can take a
   few seconds to wake up.
2. Open the site and type **Dana** when it asks who's using it.
3. Have the Monday screen open, nothing expanded. Close other tabs.

## 0:00 to 1:00 · Monday: the two questions in one sentence
- **Say:** "This is the Monday screen. Read the top line."
- **She sees:** "3 items will run out before a new order can arrive. 6 more need an order this week and 5 should be
  ordered soon." Then the tiles: **3 Too late, 6 Order this week, 5 Order soon, 16 Fine, $108,799 inside the
  six-month line.**
- **Say:** "Red is too late, yellow is order now or soon, green is fine. Nothing else."
- Open "What this doesn't count" under the tiles: **420 cases on hold, 20 damaged, 78 expired, 59 of old ZZ stock and
  1,500 cases on late POs with no arrival date.** "These are the numbers your reports count and this one doesn't."

## 1:00 to 3:30 · The 16/20 shrimp: why it says Too late
- **Say:** "Last December you ran out of 16/20 shrimp ten days before Christmas (your words on the call). It says it's
  about to happen again."
- In **Too late**, click the card **White shrimp 16/20 ez peel 10X2 lb (SHR-1620)**, then **See why and all the
  numbers**.
- Walk the **Why** steps, one line each:
  1. You can sell **480 cases** now (Harbor 140, New Bedford 260, Providence 80). The **80 cases on QA hold aren't
     counted**.
  2. **201 cases** are promised on 7 open orders. The largest is **Seabright Markets, 120 cases on Mon Dec 14**.
  3. **600 cases** are on PO-260443, arriving about **Mon Jan 25**. BlueTide says Dec 28, but that's earlier than 12
     weeks from Vietnam allows, so it's corrected.
  4. It sells about **53 cases a week**, and December runs **1.6×** a normal month for shrimp.
  5. So it runs out about **Mon Dec 14**.
  6. A new order placed today lands about **Mon Feb 8**.
  7. Too late: **short about 382 cases** from Dec 14 to Jan 25. "Ask Bien Xanh to expedite or find another source."
- Point at the chart: the line hits zero on Dec 14, the pink band is out of stock, and the Christmas shading sits
  inside it.
- **If she asks "where's that from?":** the **What you have** table (every lot, building, expiry, counted or not) and
  **On the way** (BlueTide's date struck through next to the real one).

## 3:30 to 4:30 · Tell it what it doesn't know
- On the same page, click **Mark as handled**: Quantity ordered **400**, Arrives **Dec 4, 2026**, note "Air freight from
  Bien Xanh, confirmed by phone".
- Back on Monday the item has moved to **Handled** (grey) with her note, and "Too late" shows **2**. Nothing is
  hidden; it's under Handled.
- **Undo before moving on:** on the item page, click **Clear this note**, so the demo data stays clean.

## 4:30 to 5:30 · Suppliers: "BlueTide says 8 weeks, you say 12"
- Click **Suppliers**. Bien Xanh Export Co. (Vietnam): **BlueTide says 8 weeks; you say 12 weeks to arrive**, plus a
  2-week cushion. "This is the number from your email. Change it here and every item from that supplier is recalculated."
- Optional: show **Activity**. Every change says who made it and when, with before and after.

## 5:30 to 7:00 · What you're stuck with
- Back on Monday, right-hand list: **Atl salmon portion 6 oz skin-on (SAL-POR6)**, the Chilean salmon from Austral Frío.
  **1,350 cases, 1,050 of them at Harbor, $81,232 at cost, inside the six-month line.** "This is the stock you bought
  heavy over the summer."
- Top of the list, **Expired**: the 8 oz portions (SAL-POR8). 60 cases at Harbor expired on Oct 20, and its other 380
  cases at Harbor expire in March ($47,838 at cost for the item).
- Click **Harbor** in the menu. "2,095 cases of 14 items at Harbor now." Type a cases-per-pallet number for SAL-POR6 to
  show the cost appear (say it's an example: the real number is hers). With 60, it reads **18 pallets, $540 a
  month**. **Don't press Add to table** unless she wants to keep it.

## 7:00 to 8:30 · Data: everything it didn't count, and why
- Click **Data**, then open **What we cleaned up and why**: "4,047 notes from the latest load".
- Pick four she'll recognise:
  - **Transfers recorded as sales**: 378 rows that moved stock between buildings, not sales;
  - **Samples as $0 orders**: 104;
  - **the cruise line one-off**: 2 rows, kept out of the selling rate;
  - **hold and damaged**: 8 rows, not counted.
- "Every number on Monday traces back to these rules. Each one has the file and line it came from."
- **Download data notes for Excel** if she wants the list.

## 8:30 to 9:30 · Her own work (new since the call)
- **Purchase orders:** BlueTide's POs and hers in one list. "New PO" counts as on the way the moment it's saved, and
  "Receive" puts it into stock.
- **Shipments:** orders going out. Open orders count as promised, and shipping takes the stock (soonest to expire first).
- **Data:** next week's BlueTide files are loaded here. Checking changes nothing until she presses Load.
- **Download for Excel** is on every list.
- Don't create anything live unless she asks. If you do, cancel it afterwards.

## 9:30 to 10:00 · Close
- "One screen on Monday morning that tells us what we need to order and what we're stuck with." (Walt, call 00:04:40.)
  "And every number clicks through to why."
- **Next:**
  - a "what if the QA hold clears" switch;
  - flagging stock projected to expire before it sells;
  - suggested stockout weeks for her to confirm;
  - rounding orders to supplier minimums once we have them.
  The full list is in the README.
- Ask: "What would make you open this instead of Excel next Monday?"

## If something goes wrong
- **A slow first load or "couldn't reach the server":** wait 10 seconds and refresh. The site wakes up on the first call.
- **A number looks different from this script:** someone changed data (a handled note, a supplier setting, a PO).
  **Activity** shows who changed what; undo it there or on the item page.
- **Anything else:** each error shows a reference id. Note it and keep going on another page.
