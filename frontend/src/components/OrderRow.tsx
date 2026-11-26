/**
 * One item in "What to order" (and in Handled / Fine), as a dropdown row (Ishan, 2026-11-26: "I
 * shouldn't have to scroll for each item"). Closed, it shows the name, one key date, the runway bar
 * and the status. Open, it shows how much to order and from whom, the shortfall, the late-PO note,
 * stock on hold, Dana's handled note, and the buttons. The item page has the full "why".
 * Native <details>, so it opens with the keyboard and screen readers for free.
 * Fed by: ItemCard from GET /dashboard.
 */
import { useState } from "react";
import { Link } from "react-router";
import type { ItemCard } from "../api/types";
import { formatShortDate } from "../lib/dates";
import { dayWithRelative, duration, qty, weeks } from "../lib/format";
import { itemName } from "../lib/names";
import { HandledNoteView } from "./HandledNoteView";
import { MarkHandledDialog } from "./MarkHandledDialog";
import { RunwayBar } from "./RunwayBar";
import { StatusChip } from "./StatusChip";
import { Term } from "./Term";

/** The one date that matters most, for the closed row. */
function keyDate(card: ItemCard, asOf: string): string {
  if (card.status === "NO_RECENT_SALES") return "No recent sales";
  if ((card.status === "ORDER_THIS_WEEK" || card.status === "ORDER_SOON") && card.order_by_date) {
    // An order-by date before today means the order is already overdue: say so, don't show a past date.
    return card.order_by_date < asOf
      ? `Order now (was due ${formatShortDate(card.order_by_date)})`
      : `Order by ${formatShortDate(card.order_by_date)}`;
  }
  if (card.run_out_date) return `Runs out ${formatShortDate(card.run_out_date)}`;
  return `Lasts more than ${duration(card.runway.horizon_days)}`;
}

function whenSentence(card: ItemCard, asOf: string): string {
  const runsOut = card.run_out_date
    ? `Runs out about ${dayWithRelative(card.run_out_date, asOf)}.`
    : `Lasts more than ${duration(card.runway.horizon_days)}.`;
  const lands = `An order placed today arrives about ${dayWithRelative(card.new_order_arrival, asOf)}.`;
  if ((card.status === "ORDER_THIS_WEEK" || card.status === "ORDER_SOON") && card.order_by_date) {
    return card.order_by_date < asOf
      ? `${runsOut} The order was due ${dayWithRelative(card.order_by_date, asOf)}, so order now.`
      : `${runsOut} Order by ${dayWithRelative(card.order_by_date, asOf)} so it arrives in time.`;
  }
  return card.status === "TOO_LATE" ? `${runsOut} ${lands}` : runsOut;
}

/**
 * What to do about the order. "Order at least 0" happens in two cases: stock lasts long enough for
 * now, or it's too late and stock already on the way lands before a new order could, so ordering more
 * today wouldn't close the gap (SHR-1620: PO-260443 lands Jan 25, a new order Feb 8).
 */
function orderSentence(card: ItemCard, asOf: string): string {
  if (card.order_at_least > 0) return `Order at least ${qty(card.order_at_least, card.sell_uom)}.`;
  if (card.status !== "TOO_LATE") return "Nothing needs ordering today.";
  const backFirst = card.back_in_stock_date && card.back_in_stock_date < card.new_order_arrival;
  return backFirst && card.back_in_stock_date
    ? `Ordering more today won't close the gap: stock already on the way arrives first, about ${dayWithRelative(card.back_in_stock_date, asOf)}.`
    : "Ordering more today won't close the gap.";
}

export function OrderRow({ card, asOf }: { card: ItemCard; asOf: string }) {
  const [handling, setHandling] = useState(false);
  const uom = card.sell_uom;
  const itemLink = `/items/${encodeURIComponent(card.item_code)}`;

  return (
    <details className="group">
      <summary className="grid cursor-pointer list-none grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-2 px-4 py-3 hover:bg-ice sm:grid-cols-[auto_minmax(0,19rem)_minmax(0,1fr)_auto]">
        <span
          aria-hidden="true"
          className="text-lg leading-none text-fog transition-transform group-open:rotate-90"
        >
          ›
        </span>
        <span className="min-w-0">
          <span className="block font-semibold">
            {itemName(card.description)}{" "}
            <span className="whitespace-nowrap text-sm font-normal text-fog">{card.item_code}</span>
          </span>
          <span className="block text-sm text-fog">{keyDate(card, asOf)}</span>
        </span>
        <span className="col-span-full col-start-2 row-start-2 sm:col-span-1 sm:col-start-3 sm:row-start-1">
          <RunwayBar card={card} compact />
        </span>
        <span className="col-start-3 row-start-1 justify-self-end sm:col-start-4">
          <StatusChip status={card.handled_note ? "HANDLED" : card.status} />
        </span>
      </summary>

      <div className="space-y-2 px-4 pb-4 pl-11">
        <p>{whenSentence(card, asOf)}</p>
        <p>
          <span className="font-semibold">{orderSentence(card, asOf)}</span> {card.vendor_name}
          {card.country ? `, ${card.country}` : ""}: {weeks(card.lead_time_days)}{" "}
          <Term explain="arrive">to arrive</Term> plus {weeks(card.cushion_days)}{" "}
          <Term explain="cushion">cushion</Term>.
        </p>
        {card.status === "TOO_LATE" && card.short_qty > 0 && (
          <p className="text-red">
            Expect to be short about {qty(card.short_qty, uom)} until it's back in stock
            {card.back_in_stock_date
              ? ` about ${dayWithRelative(card.back_in_stock_date, asOf)}`
              : ""}
            . Ask the supplier to speed it up, or find another source.
          </p>
        )}
        {card.covered_only_by_late_po && (
          <p className="rounded-md bg-yellow-tint px-3 py-2">
            <span className="font-semibold">Only covered by a late PO.</span>{" "}
            {qty(card.late_qty, uom)} on a <Term explain="late">late PO</Term> would cover it if it
            really shows up. It isn't counted until you set a real arrival date.
          </p>
        )}
        {card.on_hold > 0 && (
          <p className="text-sm text-fog">
            {qty(card.on_hold, uom)} <Term explain="onHold">on hold</Term> isn't counted.
          </p>
        )}
        {card.handled_note && <HandledNoteView note={card.handled_note} uom={uom} />}
        <div className="flex flex-wrap gap-3 pt-1">
          {!card.handled_note && (
            <button
              type="button"
              onClick={() => setHandling(true)}
              className="rounded-md border border-ink px-3 py-1.5 font-semibold hover:bg-ice"
            >
              Mark as handled
            </button>
          )}
          <Link to={itemLink} className="px-1 py-1.5 font-semibold underline underline-offset-2">
            See why and all the numbers
          </Link>
        </div>
      </div>
      {handling && (
        <MarkHandledDialog card={card} asOf={asOf} open onClose={() => setHandling(false)} />
      )}
    </details>
  );
}
