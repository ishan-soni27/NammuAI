/**
 * One item in "What to order" (and in Handled / Fine), as a card in a grid (Ishan, 2026-11-26: "I
 * want the Items in What to Order to be in grid layout"). Closed, it shows the status, the name, one
 * key date, the runway bar and how much to order. Clicking it opens it across the full row with how
 * much to order and from whom, the shortfall, the late-PO note, stock on hold, Dana's handled note,
 * and the buttons. The item page has the full "why".
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

// The card's left edge in its traffic-light colour (always with the chip's words too).
const ACCENT: Record<ItemCard["status"] | "HANDLED", string> = {
  TOO_LATE: "border-l-red",
  ORDER_THIS_WEEK: "border-l-yellow",
  ORDER_SOON: "border-l-yellow",
  OK: "border-l-green",
  NO_RECENT_SALES: "border-l-grey",
  NOT_PLANNED: "border-l-grey",
  HANDLED: "border-l-grey",
};

/** The one line about ordering on the closed card. */
function orderShort(card: ItemCard): string {
  if (card.order_at_least > 0) return `Order at least ${qty(card.order_at_least, card.sell_uom)}`;
  return card.status === "TOO_LATE"
    ? "Ordering more won't close the gap"
    : "Nothing to order today";
}

export function OrderRow({
  card,
  asOf,
  showStatus = true,
}: {
  card: ItemCard;
  asOf: string;
  /** False inside a status section (Too late, ...), where the section header already says it. */
  showStatus?: boolean;
}) {
  const [handling, setHandling] = useState(false);
  const uom = card.sell_uom;
  const itemLink = `/items/${encodeURIComponent(card.item_code)}`;
  const status = card.handled_note ? "HANDLED" : card.status;

  // A card in the grid. Opened, it spans the full row (open:col-span-full) and the cards after it
  // fill the gap (grid-flow-dense on the grid).
  return (
    <details
      className={`group/card rounded-lg border border-l-4 border-rope bg-hull open:col-span-full ${ACCENT[status]}`}
    >
      <summary className="block cursor-pointer list-none rounded-lg p-4 hover:bg-ice">
        {showStatus ? (
          <>
            <span className="flex items-start justify-between gap-2">
              <StatusChip status={status} />
              <span className="whitespace-nowrap pt-0.5 text-sm text-fog">{card.item_code}</span>
            </span>
            <span className="mt-2 block font-semibold leading-snug">
              {itemName(card.description)}
            </span>
          </>
        ) : (
          <span className="flex items-start justify-between gap-2">
            <span className="font-semibold leading-snug">{itemName(card.description)}</span>
            <span className="whitespace-nowrap pt-0.5 text-sm text-fog">{card.item_code}</span>
          </span>
        )}
        <span className="block text-sm text-fog">{keyDate(card, asOf)}</span>
        <span className="mt-3 block">
          <RunwayBar card={card} compact />
        </span>
        <span className="mt-3 flex items-center justify-between gap-2 text-sm">
          <span className="font-semibold">{orderShort(card)}</span>
          <span className="whitespace-nowrap text-fog">
            <span className="group-open/card:hidden">Details</span>
            <span className="hidden group-open/card:inline">Close</span>{" "}
            <span
              aria-hidden="true"
              className="inline-block transition-transform group-open/card:rotate-90"
            >
              ›
            </span>
          </span>
        </span>
      </summary>

      <div className="space-y-2 border-t border-rope px-4 pb-4 pt-3">
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
