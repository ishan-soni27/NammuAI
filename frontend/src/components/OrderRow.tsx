/**
 * One item in "What to order" (and in Handled / Fine), as a card in a grid (Ishan, 2026-11-26: "I
 * want the Items in What to Order to be in grid layout"). Closed, it shows the status, the name, one
 * key date, the runway bar and how much to order. Clicking it opens it across the full row with short
 * computed labels (runs out, order by, order at least, when a new order lands, the shortfall, stock
 * on hold, late POs), the one instruction for items only a late PO would cover (ADR-033), Dana's
 * handled note and the buttons. When BlueTide's count is older than the day shown (ADR-034), it
 * shows both: what the count said, and the estimate for today (Ishan 2026-11-26). No paragraphs: the item page has the full numbers-only "why".
 * Native <details>, so it opens with the keyboard and screen readers for free.
 * Fed by: ItemCard from GET /dashboard.
 */
import { useState, type ReactNode } from "react";
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

/** "Overdue by 6 days". */
function overdueBy(card: ItemCard): string {
  const n = card.days_overdue ?? 0;
  return `Overdue by ${n} day${n === 1 ? "" : "s"}`;
}

/** "Out of stock since about Tue Nov 24" (estimated) or, with nothing counted, "Nothing left to sell". */
function outOfStock(card: ItemCard, asOf: string): string {
  return card.run_out_date && card.run_out_date < asOf
    ? `Out of stock since about ${formatShortDate(card.run_out_date)}`
    : "Nothing left to sell today";
}

/** The one date that matters most, for the closed row. */
function keyDate(card: ItemCard, asOf: string): string {
  if (card.status === "NO_RECENT_SALES") return "No recent sales";
  if (card.status === "OUT_OF_STOCK") return outOfStock(card, asOf);
  if (card.status === "OVERDUE" && card.order_by_date) {
    return `${overdueBy(card)} (order by was ${formatShortDate(card.order_by_date)})`;
  }
  if ((card.status === "ORDER_THIS_WEEK" || card.status === "ORDER_SOON") && card.order_by_date) {
    return `Order by ${formatShortDate(card.order_by_date)}`;
  }
  if (card.run_out_date) return `Runs out ${formatShortDate(card.run_out_date)}`;
  return `Lasts more than ${duration(card.runway.horizon_days)}`;
}

const SHORT_STATUSES: ItemCard["status"][] = ["OUT_OF_STOCK", "TOO_LATE"];

/** The opened card's facts: short computed labels, each a number or a date (ADR-033). */
function Facts({ card, asOf }: { card: ItemCard; asOf: string }) {
  const uom = card.sell_uom;
  const facts: [ReactNode, ReactNode][] = [];
  // Both counts when the count is older than the day shown (Ishan's choice 1, ADR-034).
  if (card.count_date) {
    facts.push([`At the count (${formatShortDate(card.count_date)})`, qty(card.sellable, uom)]);
    facts.push(["Can sell now (estimated)", qty(card.sellable_now, uom)]);
  }
  if (card.status === "OUT_OF_STOCK") {
    facts.push([
      "Out of stock",
      <span key="out" className="text-red">
        {card.run_out_date && card.run_out_date < asOf
          ? `since about ${dayWithRelative(card.run_out_date, asOf)}`
          : "nothing left to sell today"}
      </span>,
    ]);
  } else {
    facts.push([
      "Runs out",
      card.run_out_date
        ? dayWithRelative(card.run_out_date, asOf)
        : `not within ${duration(card.runway.horizon_days)}`,
    ]);
  }
  if (card.status === "OVERDUE" && card.order_by_date) {
    facts.push([
      "Order by",
      <span key="overdue" className="text-red">
        {formatShortDate(card.order_by_date)}: {overdueBy(card).toLowerCase()}
      </span>,
    ]);
  }
  if ((card.status === "ORDER_THIS_WEEK" || card.status === "ORDER_SOON") && card.order_by_date) {
    facts.push(["Order by", dayWithRelative(card.order_by_date, asOf)]);
  }
  facts.push(["Order at least", qty(card.order_at_least, uom)]);
  facts.push([
    <Term key="arrive" explain="arrive">
      New order lands
    </Term>,
    `${dayWithRelative(card.new_order_arrival, asOf)} · ${card.vendor_name}, ${weeks(card.lead_time_days)} + ${weeks(card.cushion_days)} cushion`,
  ]);
  if (SHORT_STATUSES.includes(card.status) && card.short_qty > 0) {
    facts.push([
      "Short",
      <span key="short" className="text-red">
        {qty(card.short_qty, uom)}
        {card.back_in_stock_date && ` until ${formatShortDate(card.back_in_stock_date)}`}
      </span>,
    ]);
  }
  if (card.on_hold > 0) {
    facts.push([
      <Term key="hold" explain="onHold">
        On hold
      </Term>,
      `${qty(card.on_hold, uom)}, not counted`,
    ]);
  }
  if (card.late_qty > 0) {
    facts.push([
      <Term key="late" explain="late">
        Late POs
      </Term>,
      `${qty(card.late_qty, uom)}, not counted`,
    ]);
  }
  return (
    <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
      {facts.map(([label, value], i) => (
        <div key={i} className="contents">
          <dt className="text-fog">{label}</dt>
          <dd className="font-semibold">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

// The card's left edge in its traffic-light colour (always with the chip's words too).
const ACCENT: Record<ItemCard["status"] | "HANDLED", string> = {
  OUT_OF_STOCK: "border-l-red",
  TOO_LATE: "border-l-red",
  OVERDUE: "border-l-red",
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
  return SHORT_STATUSES.includes(card.status)
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
        <Facts card={card} asOf={asOf} />
        {card.instruction && (
          <p className="rounded-md bg-yellow-tint px-3 py-2 text-sm font-semibold">
            {card.instruction}
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
