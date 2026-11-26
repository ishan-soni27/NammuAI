/**
 * Status and problem labels as Dana reads them: traffic-light colour + icon + words, never colour
 * alone (BUILD_PROMPT §9.1; Ishan 2026-11-26: red, yellow and green only).
 *   red    = too late
 *   yellow = order this week (solid), order soon (light): both mean "an order is due"
 *   green  = fine
 *   grey   = handled, no recent sales, not planned
 * Fed by: ItemCard.status (and "HANDLED" when Dana marked the item), StuckLot tags.
 */
import type { Status, StuckTag } from "../api/types";

const STATUS: Record<Status | "HANDLED", { label: string; icon: string; className: string }> = {
  TOO_LATE: { label: "Too late", icon: "⚠", className: "bg-red text-hull" },
  ORDER_THIS_WEEK: { label: "Order this week", icon: "●", className: "bg-yellow text-ink" },
  ORDER_SOON: {
    label: "Order soon",
    icon: "◐",
    className: "bg-yellow-tint text-ink ring-1 ring-inset ring-yellow",
  },
  OK: { label: "Fine", icon: "✓", className: "bg-green text-hull" },
  NO_RECENT_SALES: { label: "No recent sales", icon: "–", className: "bg-grey-tint text-grey" },
  NOT_PLANNED: { label: "Not planned", icon: "–", className: "bg-grey-tint text-grey" },
  HANDLED: { label: "Handled", icon: "✓", className: "bg-grey-tint text-grey" },
};

export function StatusChip({ status }: { status: Status | "HANDLED" }) {
  const s = STATUS[status];
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-sm font-semibold ${s.className}`}
    >
      <span aria-hidden="true">{s.icon}</span>
      {s.label}
    </span>
  );
}

const RED_TAG = "bg-red-tint text-red";
const YELLOW_TAG = "bg-yellow-tint text-ink";

const TAG: Record<StuckTag, { label: string; className: string }> = {
  EXPIRED: { label: "Expired", className: RED_TAG },
  INSIDE_SIX_MONTHS: { label: "Inside six-month line", className: RED_TAG },
  STOPPED_SELLING: { label: "Stopped selling", className: YELLOW_TAG },
  LONG_AT_HARBOR: { label: "Long at Harbor", className: YELLOW_TAG },
  OVERSTOCK: { label: "Overstock", className: YELLOW_TAG },
};

// eslint-disable-next-line react-refresh/only-export-components
export const TAG_LABEL: Record<StuckTag, string> = Object.fromEntries(
  Object.entries(TAG).map(([k, v]) => [k, v.label]),
) as Record<StuckTag, string>;

export function TagChip({ tag }: { tag: StuckTag }) {
  const t = TAG[tag];
  return (
    <span
      className={`inline-block whitespace-nowrap rounded px-2 py-0.5 text-xs font-semibold ${t.className}`}
    >
      {t.label}
    </span>
  );
}

export function HarborBadge() {
  return (
    <span className="inline-block whitespace-nowrap rounded border border-yellow bg-yellow-tint px-1.5 py-0.5 text-xs font-semibold text-ink">
      At Harbor (paying storage)
    </span>
  );
}

const PO_STATUS: Record<string, { label: string; icon: string; className: string }> = {
  late: { label: "Late", icon: "⚠", className: "bg-red text-hull" },
  open: { label: "Ordered", icon: "○", className: "bg-grey-tint text-grey" },
  shipped: { label: "Shipped", icon: "➜", className: "bg-grey-tint text-ink" },
  partly_received: {
    label: "Partly received",
    icon: "◐",
    className: "bg-yellow-tint text-ink ring-1 ring-inset ring-yellow",
  },
  received: { label: "Received", icon: "✓", className: "bg-green text-hull" },
  cancelled: { label: "Cancelled", icon: "✕", className: "bg-grey-tint text-grey" },
};

/** A PO's (or a PO line's) status: late is red, received is green, everything else grey. */
export function POStatusChip({ status }: { status: string }) {
  const s = PO_STATUS[status] ?? PO_STATUS.open!;
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-sm font-semibold ${s.className}`}
    >
      <span aria-hidden="true">{s.icon}</span>
      {s.label}
    </span>
  );
}

/** "Yours" (made in the app) or "Yours + BlueTide" next to a record. Nothing for BlueTide-only. */
export function SourceBadge({ source }: { source: "app" | "bluetide" | "both" }) {
  if (source === "bluetide") return null;
  return (
    <span className="inline-block whitespace-nowrap rounded border border-rope px-1.5 py-0.5 text-xs font-semibold text-fog">
      {source === "app" ? "Yours" : "Yours + BlueTide"}
    </span>
  );
}

const SHIPMENT_STATUS: Record<string, { label: string; icon: string; className: string }> = {
  overdue: { label: "Overdue", icon: "⚠", className: "bg-red text-hull" },
  open: { label: "Open", icon: "○", className: "bg-grey-tint text-grey" },
  shipped: { label: "Shipped", icon: "✓", className: "bg-green text-hull" },
  cancelled: { label: "Cancelled", icon: "✕", className: "bg-grey-tint text-grey" },
};

/** An order going out: overdue (open past its ship date) is red, shipped is green, the rest grey. */
export function ShipmentStatusChip({ status }: { status: string }) {
  const s = SHIPMENT_STATUS[status] ?? SHIPMENT_STATUS.open!;
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-sm font-semibold ${s.className}`}
    >
      <span aria-hidden="true">{s.icon}</span>
      {s.label}
    </span>
  );
}
