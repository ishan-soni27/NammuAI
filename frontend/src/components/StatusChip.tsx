/**
 * The order status as Dana reads it: icon + words + tint, never colour alone (BUILD_PROMPT §9.1).
 * Fed by: ItemCard.status (and "handled" when Dana marked the item).
 */
import type { Status, StuckTag } from "../api/types";

const STATUS: Record<Status | "HANDLED", { label: string; icon: string; className: string }> = {
  TOO_LATE: { label: "Too late", icon: "⚠", className: "bg-late-tint text-late" },
  ORDER_THIS_WEEK: { label: "Order this week", icon: "●", className: "bg-week-tint text-week" },
  ORDER_SOON: { label: "Order soon", icon: "◐", className: "bg-soon-tint text-soon" },
  OK: { label: "Fine", icon: "✓", className: "bg-fine-tint text-fine" },
  NO_RECENT_SALES: {
    label: "No recent sales",
    icon: "–",
    className: "bg-handled-tint text-handled",
  },
  NOT_PLANNED: { label: "Not planned", icon: "–", className: "bg-handled-tint text-handled" },
  HANDLED: { label: "Handled", icon: "✓", className: "bg-handled-tint text-handled" },
};

export function StatusChip({ status }: { status: Status | "HANDLED" }) {
  const s = STATUS[status];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-sm font-semibold ${s.className}`}
    >
      <span aria-hidden="true">{s.icon}</span>
      {s.label}
    </span>
  );
}

const TAG: Record<StuckTag, { label: string; className: string }> = {
  EXPIRED: { label: "Expired", className: "bg-expired-tint text-expired" },
  STOPPED_SELLING: { label: "Stopped selling", className: "bg-stopped-tint text-stopped" },
  INSIDE_SIX_MONTHS: {
    label: "Inside six-month line",
    className: "bg-sixmonth-tint text-sixmonth",
  },
  LONG_AT_HARBOR: { label: "Long at Harbor", className: "bg-harbor-tint text-harbor" },
  OVERSTOCK: { label: "Overstock", className: "bg-overstock-tint text-overstock" },
};

// eslint-disable-next-line react-refresh/only-export-components
export const TAG_LABEL: Record<StuckTag, string> = Object.fromEntries(
  Object.entries(TAG).map(([k, v]) => [k, v.label]),
) as Record<StuckTag, string>;

export function TagChip({ tag }: { tag: StuckTag }) {
  const t = TAG[tag];
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${t.className}`}>
      {t.label}
    </span>
  );
}

export function HarborBadge() {
  return (
    <span className="inline-block rounded border border-harbor px-1.5 py-0.5 text-xs font-semibold text-harbor">
      At Harbor (paying storage)
    </span>
  );
}
