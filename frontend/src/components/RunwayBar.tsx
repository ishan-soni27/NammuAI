/**
 * The runway bar: Dana's first question drawn as a picture (BUILD_PROMPT §9.1).
 *   - coloured fill = how long the stock she can sell lasts (red / yellow / green by status)
 *   - black tick    = when a new order placed today would arrive
 *   - striped part  = the cushion after that
 * If the fill ends before the tick, the item runs out before a new order can arrive ("Too late").
 * `compact` is the slim version in each collapsed row; RunwayLegend explains it once per list.
 * Fed by: ItemCard.runway + status + new_order_arrival.
 */
import type { ItemCard, Status } from "../api/types";
import { formatShortDate } from "../lib/dates";
import { duration } from "../lib/format";

const FILL: Record<Status, string> = {
  OUT_OF_STOCK: "bg-red",
  TOO_LATE: "bg-red",
  OVERDUE: "bg-red",
  ORDER_THIS_WEEK: "bg-yellow",
  ORDER_SOON: "bg-yellow",
  OK: "bg-green",
  NO_RECENT_SALES: "bg-grey",
  NOT_PLANNED: "bg-grey",
};

const HATCH = {
  backgroundImage: "repeating-linear-gradient(135deg, var(--color-fog) 0 2px, transparent 2px 6px)",
  opacity: 0.45,
};

export function RunwayBar({ card, compact = false }: { card: ItemCard; compact?: boolean }) {
  const {
    stock_lasts_days: lasts,
    lead_time_days: lead,
    cushion_days: cushion,
    horizon_days: horizon,
  } = card.runway;
  // Scale so the tick and the end of the fill are both on screen, never past the planning horizon.
  const scale = Math.min(horizon, Math.max(lead + cushion, lasts ?? horizon) * 1.15);
  const pct = (days: number) => `${Math.min(100, Math.max(0, (days / scale) * 100))}%`;
  const fillDays = lasts ?? horizon;
  const lastsText = lasts === null ? `more than ${duration(horizon)}` : duration(lasts);
  const landsText = `an order placed today arrives ${formatShortDate(card.new_order_arrival)}`;

  return (
    <div className={compact ? "" : "mt-3"}>
      <div
        role="img"
        aria-label={`Stock lasts ${lastsText}; ${landsText}, then ${duration(cushion)} of cushion.`}
        className={`relative rounded-full bg-ice ring-1 ring-rope ${compact ? "h-2.5" : "h-3"}`}
      >
        <div
          className={`absolute inset-y-0 left-0 rounded-full ${FILL[card.status]}`}
          style={{ width: pct(fillDays) }}
        />
        <div
          className="absolute inset-y-0"
          style={{
            left: pct(lead),
            width: `calc(${pct(lead + cushion)} - ${pct(lead)})`,
            ...HATCH,
          }}
        />
        <div className="absolute -inset-y-1 w-0.5 bg-ink" style={{ left: pct(lead) }} />
      </div>
      {!compact && (
        <div className="mt-1 flex justify-between gap-3 text-sm text-fog">
          <span>Stock lasts {lastsText}</span>
          <span className="text-right">
            <span aria-hidden="true">▲ </span>
            {landsText.charAt(0).toUpperCase() + landsText.slice(1)}
          </span>
        </div>
      )}
    </div>
  );
}

/** What the bar means, shown once above the list. */
export function RunwayLegend() {
  return (
    <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-fog">
      <span className="inline-flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-6 rounded-full bg-fog/50" aria-hidden="true" />
        How long your stock lasts
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="inline-block h-3.5 w-0.5 bg-ink" aria-hidden="true" />
        When an order placed today arrives
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-6 rounded-sm" style={HATCH} aria-hidden="true" />
        Cushion
      </span>
    </p>
  );
}
