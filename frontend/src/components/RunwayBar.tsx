/**
 * The runway bar: Dana's first question drawn as a picture (BUILD_PROMPT §9.1).
 *   - filled length = how long the stock she can sell lasts
 *   - ▲ marker      = when a new order placed today would land (time to arrive)
 *   - hatched zone  = the cushion after that
 * If the fill ends before the marker, the item runs out before a new order can arrive ("Too late").
 * Fed by: ItemCard.runway + status + new_order_arrival.
 */
import type { ItemCard, Status } from "../api/types";
import { formatShortDate } from "../lib/dates";
import { duration } from "../lib/format";

const FILL: Record<Status, string> = {
  TOO_LATE: "bg-late",
  ORDER_THIS_WEEK: "bg-week",
  ORDER_SOON: "bg-soon",
  OK: "bg-fine",
  NO_RECENT_SALES: "bg-handled",
  NOT_PLANNED: "bg-handled",
};

const HATCH = {
  backgroundImage: "repeating-linear-gradient(135deg, var(--color-fog) 0 2px, transparent 2px 6px)",
  opacity: 0.45,
};

export function RunwayBar({ card }: { card: ItemCard }) {
  const {
    stock_lasts_days: lasts,
    lead_time_days: lead,
    cushion_days: cushion,
    horizon_days: horizon,
  } = card.runway;
  // Scale so the marker and the end of the fill are both on screen, never past the planning horizon.
  const scale = Math.min(horizon, Math.max(lead + cushion, lasts ?? horizon) * 1.15);
  const pct = (days: number) => `${Math.min(100, Math.max(0, (days / scale) * 100))}%`;
  const fillDays = lasts ?? horizon;
  const lastsText = lasts === null ? `more than ${duration(horizon)}` : duration(lasts);
  const landsText = `new order lands ${formatShortDate(card.new_order_arrival)}`;

  return (
    <div className="mt-3">
      <div
        role="img"
        aria-label={`Stock lasts ${lastsText}. A ${landsText}, then ${duration(cushion)} of cushion.`}
        className="relative h-3 rounded-full bg-ice ring-1 ring-rope"
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
      <div className="mt-1 flex justify-between gap-3 text-sm text-fog">
        <span>Stock lasts {lastsText}</span>
        <span className="text-right">
          <span aria-hidden="true">▲ </span>
          {landsText}
        </span>
      </div>
    </div>
  );
}
