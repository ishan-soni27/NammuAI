/**
 * The Monday screen (BUILD_PROMPT §9.2): Dana's two questions on one page.
 *   1. What will run out before a new order can arrive?  ("What to order")
 *   2. What is she stuck with?                            ("What you're stuck with")
 * Top: the summary sentences and what isn't counted (links to Data notes).
 * Below the order list: Handled, Late or unknown (late POs and on-hold stock, never counted;
 * ADR-021), and everything that looks fine. Two columns from 1024 px; one column on phones,
 * order list first.
 * Fed by: GET /dashboard.
 */
import { Link } from "react-router";
import { useDashboard } from "../api/queries";
import type { Dashboard, ItemCard } from "../api/types";
import { Disclosure } from "../components/Disclosure";
import { OrderCard } from "../components/OrderCard";
import { QueryState } from "../components/QueryState";
import { SetPoDate } from "../components/SetPoDate";
import { StatusChip } from "../components/StatusChip";
import { StuckList } from "../components/StuckList";
import { Term } from "../components/Term";
import { formatShortDate, formatTimestamp } from "../lib/dates";
import { dayWithRelative, qty } from "../lib/format";
import { itemName } from "../lib/names";

function itemLink(code: string, description: string) {
  return (
    <Link to={`/items/${encodeURIComponent(code)}`} className="font-semibold hover:underline">
      {itemName(description)}{" "}
      <span className="whitespace-nowrap text-sm font-normal text-fog">{code}</span>
    </Link>
  );
}

function FineRow({ card, asOf }: { card: ItemCard; asOf: string }) {
  const detail =
    card.status === "NO_RECENT_SALES"
      ? "No recent sales and nothing promised."
      : card.run_out_date
        ? `Runs out about ${dayWithRelative(card.run_out_date, asOf)}.`
        : card.weeks_of_cover !== null
          ? `About ${Math.round(card.weeks_of_cover)} weeks of stock.`
          : "";
  return (
    <li className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 py-2">
      <span>{itemLink(card.item_code, card.description)}</span>
      <span className="flex items-center gap-2 text-sm text-fog">
        {detail}
        <StatusChip status={card.status} />
      </span>
    </li>
  );
}

function LateOrUnknown({ data }: { data: Dashboard }) {
  const { late_pos, on_hold } = data.late_inventory;
  return (
    <div className="space-y-4">
      <p className="text-fog">
        None of this is counted as stock or as coming. Set a real arrival date once the vendor gives
        you one.
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
                  {line.bluetide_date &&
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
  const lateCount = data.late_inventory.late_pos.length + data.late_inventory.on_hold.length;
  return (
    <div className="space-y-6">
      <section aria-label="Summary" className="rounded-lg border border-rope bg-hull px-5 py-4">
        {data.summary.sentences.map((sentence, i) => (
          <p key={sentence} className={i === 0 ? "text-xl font-bold" : "mt-1"}>
            {sentence}
          </p>
        ))}
        <p className="mt-2 text-sm text-fog">
          <Link to="/data-notes" className="font-semibold text-soon underline underline-offset-2">
            What we cleaned up and why
          </Link>
          {data.last_load_at && <> · BlueTide data loaded {formatTimestamp(data.last_load_at)}</>}
        </p>
      </section>

      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <section aria-labelledby="order-heading" className="space-y-4">
          <h2 id="order-heading" className="text-xl font-bold">
            What to order
          </h2>
          {data.order_items.length === 0 ? (
            <p className="rounded-lg border border-rope bg-hull px-4 py-4">
              Nothing needs ordering right now.
            </p>
          ) : (
            data.order_items.map((card) => (
              <OrderCard key={card.item_code} card={card} asOf={data.as_of} />
            ))
          )}

          <Disclosure title={`Handled (${data.handled_items.length})`}>
            {data.handled_items.length === 0 ? (
              <p className="text-fog">
                Nothing marked as handled. Use "Mark as handled" on an item once you've ordered it.
              </p>
            ) : (
              <div className="space-y-3">
                {data.handled_items.map((card) => (
                  <OrderCard key={card.item_code} card={card} asOf={data.as_of} />
                ))}
              </div>
            )}
          </Disclosure>

          <Disclosure title={`Late or unknown (${lateCount})`}>
            <LateOrUnknown data={data} />
          </Disclosure>

          <Disclosure title={`Everything else looks fine (${data.fine_items.length} items)`}>
            <ul className="divide-y divide-rope">
              {data.fine_items.map((card) => (
                <FineRow key={card.item_code} card={card} asOf={data.as_of} />
              ))}
            </ul>
          </Disclosure>
        </section>

        <section aria-labelledby="stuck-heading" className="space-y-4">
          <h2 id="stuck-heading" className="text-xl font-bold">
            What you're stuck with
          </h2>
          <div className="rounded-lg border border-rope bg-hull px-4 py-3">
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
