/**
 * One row of "What to order": the item, its status, when it runs out, the runway bar, how much to
 * order and from whom, and "Mark as handled". Every number links to the item page, where the "why"
 * steps and source rows are (BUILD_PROMPT §9.2).
 * Fed by: ItemCard from GET /dashboard.
 */
import { useState } from "react";
import { Link } from "react-router";
import type { ItemCard } from "../api/types";
import { dayWithRelative, duration, qty, weeks } from "../lib/format";
import { itemName } from "../lib/names";
import { HandledNoteView } from "./HandledNoteView";
import { MarkHandledDialog } from "./MarkHandledDialog";
import { RunwayBar } from "./RunwayBar";
import { StatusChip } from "./StatusChip";
import { Term } from "./Term";

function whenSentence(card: ItemCard, asOf: string): string {
  const runsOut = card.run_out_date
    ? `Runs out about ${dayWithRelative(card.run_out_date, asOf)}.`
    : "";
  if (card.status === "TOO_LATE") {
    return `${runsOut} A new order placed today lands about ${dayWithRelative(card.new_order_arrival, asOf)}.`;
  }
  if (card.order_by_date && (card.status === "ORDER_THIS_WEEK" || card.status === "ORDER_SOON")) {
    return `${runsOut} Order by ${dayWithRelative(card.order_by_date, asOf)} so it lands in time.`.trim();
  }
  return runsOut || `Lasts more than ${duration(card.runway.horizon_days)}.`;
}

export function OrderCard({ card, asOf }: { card: ItemCard; asOf: string }) {
  const [handling, setHandling] = useState(false);
  const uom = card.sell_uom;

  return (
    <article className="rounded-lg border border-rope bg-hull px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-lg font-semibold">
          <Link to={`/items/${encodeURIComponent(card.item_code)}`} className="hover:underline">
            {itemName(card.description)}
          </Link>{" "}
          <span className="whitespace-nowrap text-sm font-normal text-fog">{card.item_code}</span>
        </h3>
        <StatusChip status={card.handled_note ? "HANDLED" : card.status} />
      </div>

      <p className="mt-1">{whenSentence(card, asOf)}</p>
      <RunwayBar card={card} />

      <p className="mt-3">
        {card.order_at_least > 0 ? (
          <span className="font-semibold">Order at least {qty(card.order_at_least, uom)}.</span>
        ) : (
          <span className="font-semibold">Nothing needs ordering today.</span>
        )}{" "}
        {card.vendor_name}
        {card.country ? `, ${card.country}` : ""}, {weeks(card.lead_time_days)}{" "}
        <Term explain="arrive">to arrive</Term> plus {weeks(card.cushion_days)}{" "}
        <Term explain="cushion">cushion</Term>.
      </p>

      {card.status === "TOO_LATE" && card.short_qty > 0 && (
        <p className="mt-1 text-late">
          Even ordering today, you'll be short about {qty(card.short_qty, uom)} until it lands
          {card.back_in_stock_date
            ? ` about ${dayWithRelative(card.back_in_stock_date, asOf)}`
            : ""}
          .
        </p>
      )}

      {card.covered_only_by_late_po && (
        <p className="mt-2 rounded-md bg-week-tint px-3 py-2 text-ink">
          <span className="font-semibold">Only covered by a late PO.</span>{" "}
          {qty(card.late_qty, uom)} on a <Term explain="late">late PO</Term> would cover it if it
          really shows up. It isn't counted until you set a real arrival date.
        </p>
      )}

      {card.on_hold > 0 && (
        <p className="mt-1 text-sm text-fog">
          {qty(card.on_hold, uom)} <Term explain="onHold">on hold</Term> isn't counted.
        </p>
      )}

      {card.handled_note ? (
        <div className="mt-3">
          <HandledNoteView note={card.handled_note} uom={uom} />
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => setHandling(true)}
            className="rounded-md border border-ink px-3 py-1.5 font-semibold hover:bg-ice"
          >
            Mark as handled
          </button>
          <Link
            to={`/items/${encodeURIComponent(card.item_code)}`}
            className="px-1 py-1.5 font-semibold text-soon underline underline-offset-2"
          >
            See why
          </Link>
        </div>
      )}
      {handling && (
        <MarkHandledDialog card={card} asOf={asOf} open onClose={() => setHandling(false)} />
      )}
    </article>
  );
}
