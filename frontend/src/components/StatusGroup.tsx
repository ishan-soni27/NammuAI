/**
 * One status in "What to order" as its own dropdown (Ishan, 2026-11-26): Out of stock, Too late,
 * Overdue, Order this week, Order soon. The header says what the status means and how many items it
 * holds; opening it shows the grid of item cards. All but Order soon start open (they need action this
 * week); Order soon starts closed. Uses its own named group ("section") so the cards inside open and close
 * on their own (a shared "group" class made every card look open; see Term.tsx).
 * Fed by: Dashboard.order_items, grouped by status in MondayPage.
 */
import type { ReactNode } from "react";
import type { Status } from "../api/types";
import { StatusChip } from "./StatusChip";

const MEANING: Partial<Record<Status, string>> = {
  OUT_OF_STOCK:
    "By our estimate these have nothing left to sell today. Order now, and upload this week's BlueTide files to check.",
  OVERDUE:
    "The order-by date has passed. An order placed today still lands before these run out, with less cushion: order today.",
  TOO_LATE:
    "These run out before a new order can arrive. Order now and find a way to cover the gap.",
  ORDER_THIS_WEEK: "Place these orders this week so they arrive in time.",
  ORDER_SOON: "Not urgent yet: order by the date on each card.",
};

const EDGE: Partial<Record<Status, string>> = {
  OUT_OF_STOCK: "border-l-red",
  TOO_LATE: "border-l-red",
  OVERDUE: "border-l-red",
  ORDER_THIS_WEEK: "border-l-yellow",
  ORDER_SOON: "border-l-yellow",
};

interface Props {
  status: Status;
  count: number;
  defaultOpen: boolean;
  children: ReactNode;
}

export function StatusGroup({ status, count, defaultOpen, children }: Props) {
  return (
    <details
      open={defaultOpen}
      className={`group/section rounded-lg border border-l-4 border-rope bg-hull ${EDGE[status] ?? ""}`}
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-lg px-4 py-3 hover:bg-ice">
        <span className="min-w-0">
          <span className="flex flex-wrap items-center gap-2">
            <StatusChip status={status} />
            <span className="font-semibold">
              {count} item{count === 1 ? "" : "s"}
            </span>
          </span>
          <span className="mt-1 block text-sm text-fog">{MEANING[status]}</span>
        </span>
        <span
          aria-hidden="true"
          className="text-lg leading-none text-fog transition-transform group-open/section:rotate-90"
        >
          ›
        </span>
      </summary>
      <div className="border-t border-rope p-3">{children}</div>
    </details>
  );
}
