/**
 * The Monday screen (BUILD_PROMPT §9.2): Dana's two questions on one page.
 *   1. What will run out before a new order can arrive?  ("What to order")
 *   2. What is she stuck with?                            ("What you're stuck with")
 * Top: the headline sentence and the counts in traffic-light colours. What to order is split into one
 * dropdown per status (Out of stock, Too late, Overdue, Order this week, Order soon), each holding a
 * grid of item cards (Ishan, 2026-11-26; the red Out of stock and Overdue are ADR-034's, shown only
 * when there are some). Below the order list:
 * Handled, Late or unknown (late POs and on-hold stock, never counted; ADR-021) and Everything else
 * looks fine, each closed until clicked. Two columns from 1024 px; one column on phones.
 * Fed by: GET /dashboard.
 */
import { Link } from "react-router";
import { useDashboard } from "../api/queries";
import type { Dashboard, LateLine, Status } from "../api/types";
import { Disclosure } from "../components/Disclosure";
import { DownloadLink } from "../components/DownloadLink";
import { OrderRow } from "../components/OrderRow";
import { QueryState } from "../components/QueryState";
import { RunwayLegend } from "../components/RunwayBar";
import { SetPoDate } from "../components/SetPoDate";
import { StatusGroup } from "../components/StatusGroup";
import { StuckList } from "../components/StuckList";
import { Term } from "../components/Term";
import { formatShortDate, formatTimestamp } from "../lib/dates";
import { money, qty } from "../lib/format";
import { itemName } from "../lib/names";

function itemLink(code: string, description: string) {
  return (
    <Link to={`/items/${encodeURIComponent(code)}`} className="font-semibold hover:underline">
      {itemName(description)}{" "}
      <span className="whitespace-nowrap text-sm font-normal text-fog">{code}</span>
    </Link>
  );
}

// Item cards: one column on phones, two side by side from 640 px; an opened card spans the row and
// the next cards fill in around it (grid-flow-dense).
const GRID = "grid grid-flow-dense grid-cols-1 gap-3 sm:grid-cols-2";

// What to order, one dropdown per status, most urgent first. All but Order soon start open (they
// need action this week); Order soon starts closed.
const ORDER_GROUPS: [Status, boolean][] = [
  ["OUT_OF_STOCK", true],
  ["TOO_LATE", true],
  ["OVERDUE", true],
  ["ORDER_THIS_WEEK", true],
  ["ORDER_SOON", false],
];

const TONE = {
  red: "border-red bg-red-tint text-red",
  yellow: "border-yellow bg-yellow-tint text-ink",
  green: "border-green bg-green-tint text-green",
} as const;

function Count({
  tone,
  value,
  label,
  wide = false,
}: {
  tone: keyof typeof TONE;
  value: string;
  label: string;
  wide?: boolean;
}) {
  return (
    <div
      className={`rounded-md border-l-4 px-3 py-2 ${TONE[tone]} ${wide ? "col-span-2 sm:col-span-1" : ""}`}
    >
      <p className="text-2xl font-bold leading-tight">{value}</p>
      <p className="text-sm font-semibold text-ink">{label}</p>
    </div>
  );
}

/** Lines not counted because their date passed after the last upload (ADR-034), in Dana's words. */
function sinceUpload(line: LateLine): string | null {
  const flag = line.flags.find(
    (f) => f.startsWith("Due since your last upload") || f.startsWith("Your date has passed"),
  );
  if (!flag) return null;
  return flag.startsWith("Due")
    ? "Due since your last upload: upload this week's files to see if it arrived."
    : "Your date has passed: upload this week's files to confirm it arrived, or set a new date.";
}

function LateOrUnknown({ data }: { data: Dashboard }) {
  const { late_pos, on_hold } = data.late_inventory;
  return (
    <div className="space-y-4">
      <p className="text-fog">
        None of this is counted as stock or as coming. Set a real arrival date once the supplier
        gives you one.
      </p>
      <section>
        <h3 className="font-semibold">
          <Term explain="late">Late POs</Term> with no real arrival date
        </h3>
        {late_pos.length === 0 ? (
          <p className="text-fog">No late POs.</p>
        ) : (
          <ul className="divide-y divide-rope">
            {late_pos.map((line) => (
              <li key={line.reference} className="py-2">
                <div>{itemLink(line.item_code, line.description)}</div>
                <p className="mt-0.5">
                  {line.reference}, {qty(line.qty, line.sell_uom)}.
                  {sinceUpload(line)
                    ? ` ${sinceUpload(line)}`
                    : line.bluetide_date &&
                      ` BlueTide said ${formatShortDate(line.bluetide_date)}, and nothing has arrived.`}
                </p>
                {line.po_no && line.line_no !== null && (
                  <div className="mt-1">
                    <SetPoDate poNo={line.po_no} lineNo={line.line_no} asOf={data.as_of} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h3 className="font-semibold">
          Stock <Term explain="onHold">on hold</Term>
        </h3>
        {on_hold.length === 0 ? (
          <p className="text-fog">Nothing on hold.</p>
        ) : (
          <ul className="divide-y divide-rope">
            {on_hold.map((h) => (
              <li key={h.item_code} className="flex flex-wrap justify-between gap-x-3 py-2">
                {itemLink(h.item_code, h.description)}
                <span>{qty(h.qty, h.sell_uom)} on hold</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Monday({ data }: { data: Dashboard }) {
  const s = data.summary;
  const lateCount = data.late_inventory.late_pos.length + data.late_inventory.on_hold.length;
  const [headline, ...details] = s.sentences;
  return (
    <div className="space-y-5">
      <section aria-label="Summary" className="rounded-lg border border-rope bg-hull px-5 py-4">
        {headline && <p className="text-lg font-bold sm:text-xl">{headline}</p>}
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-[repeat(auto-fit,minmax(8.5rem,1fr))]">
          {s.out_of_stock > 0 && (
            <Count tone="red" value={String(s.out_of_stock)} label="Out of stock (estimated)" />
          )}
          <Count tone="red" value={String(s.too_late)} label="Too late" />
          {s.overdue > 0 && <Count tone="red" value={String(s.overdue)} label="Overdue" />}
          <Count tone="yellow" value={String(s.order_this_week)} label="Order this week" />
          <Count tone="yellow" value={String(s.order_soon)} label="Order soon" />
          <Count tone="green" value={String(s.fine)} label="Fine" />
          <Count
            wide
            tone="red"
            value={money(s.inside_six_months_value)}
            label="Inside the six-month line"
          />
        </div>
        <details className="mt-3 text-sm text-fog">
          <summary className="cursor-pointer">
            What this doesn't count, and where the data came from
          </summary>
          <div className="mt-1 space-y-1">
            {details.map((sentence) => (
              <p key={sentence}>{sentence}</p>
            ))}
            <p>
              <Link to="/data" className="font-semibold text-ink underline underline-offset-2">
                What we cleaned up and why
              </Link>
              {data.last_load_at && (
                <> · BlueTide data loaded {formatTimestamp(data.last_load_at)}</>
              )}
            </p>
          </div>
        </details>
      </section>

      <div className="grid items-start gap-5 lg:grid-cols-[3fr_2fr]">
        <section aria-labelledby="order-heading" className="min-w-0 space-y-3">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h2 id="order-heading" className="text-xl font-bold">
              What to order
            </h2>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
              <RunwayLegend />
              <DownloadLink list="order-list" what="Every item, its status and how much to order" />
            </div>
          </div>
          {data.order_items.length === 0 ? (
            <p className="rounded-lg border border-rope bg-hull px-4 py-3">
              Nothing needs ordering right now.
            </p>
          ) : (
            <div className="space-y-3">
              {ORDER_GROUPS.map(([status, open]) => {
                const cards = data.order_items.filter((c) => c.status === status);
                if (cards.length === 0) return null;
                return (
                  <StatusGroup key={status} status={status} count={cards.length} defaultOpen={open}>
                    <div className={GRID}>
                      {cards.map((card) => (
                        <OrderRow
                          key={card.item_code}
                          card={card}
                          asOf={data.as_of}
                          showStatus={Boolean(card.handled_note)}
                        />
                      ))}
                    </div>
                  </StatusGroup>
                );
              })}
            </div>
          )}

          <Disclosure title={`Handled (${data.handled_items.length})`}>
            {data.handled_items.length === 0 ? (
              <p className="text-fog">
                Nothing marked as handled. Open an item above and use "Mark as handled" once you've
                ordered it.
              </p>
            ) : (
              <div className={GRID}>
                {data.handled_items.map((card) => (
                  <OrderRow key={card.item_code} card={card} asOf={data.as_of} />
                ))}
              </div>
            )}
          </Disclosure>

          <Disclosure title={`Late or unknown (${lateCount})`}>
            <LateOrUnknown data={data} />
          </Disclosure>

          <Disclosure title={`Everything else looks fine (${data.fine_items.length} items)`}>
            <div className={GRID}>
              {data.fine_items.map((card) => (
                <OrderRow key={card.item_code} card={card} asOf={data.as_of} />
              ))}
            </div>
          </Disclosure>
        </section>

        <section aria-labelledby="stuck-heading" className="min-w-0 space-y-3">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4">
            <h2 id="stuck-heading" className="text-xl font-bold">
              What you're stuck with
            </h2>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
              <span className="text-sm text-fog">{money(s.stuck_value)} at cost</span>
              <DownloadLink list="stuck-list" what="Every stuck lot, its building and value" />
            </div>
          </div>
          <div className="overflow-hidden rounded-lg border border-rope bg-hull">
            <StuckList items={data.stuck_items} />
          </div>
        </section>
      </div>
    </div>
  );
}

export function MondayPage() {
  const dashboard = useDashboard();
  return (
    <QueryState query={dashboard} label="Loading Monday's numbers">
      {(data) => <Monday data={data} />}
    </QueryState>
  );
}
