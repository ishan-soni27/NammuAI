/**
 * Shipments (Phase 6 step 2): orders going out to customers (and samples), logged by Dana.
 * Open ones count as promised on their ship date; shipping takes the lots soonest to expire first.
 * Filters: Open (default), Shipped, Cancelled, All; search by order, customer or item.
 * Fed by: GET /shipments.
 */
import { useDeferredValue, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useHealth } from "../api/health";
import { useShipments } from "../api/queries";
import { QueryState } from "../components/QueryState";
import { ShipmentRow } from "../components/ShipmentRow";
import { input, primaryButton } from "../lib/ui";

const FILTERS = [
  ["open", "Open"],
  ["shipped", "Shipped"],
  ["cancelled", "Cancelled"],
  ["all", "All"],
] as const;

export function ShipmentsPage() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "open";
  const [search, setSearch] = useState("");
  const q = useDeferredValue(search.trim());
  const list = useShipments(status, q);
  const asOf = useHealth().data?.as_of;
  const highlight = params.get("order");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Shipments</h1>
          <p className="text-fog">
            Orders going out. Open ones count as promised to customers on Monday; shipping takes the
            stock.
          </p>
        </div>
        <Link to="/shipments/new" className={primaryButton}>
          New order
        </Link>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div role="group" aria-label="Show" className="flex flex-wrap gap-1">
          {FILTERS.map(([value, text]) => (
            <button
              key={value}
              type="button"
              aria-pressed={status === value}
              onClick={() => setParams({ status: value })}
              className={`rounded-full border px-3 py-1 text-sm font-semibold ${
                status === value
                  ? "border-ink bg-ink text-hull"
                  : "border-rope bg-hull hover:bg-ice"
              }`}
            >
              {text}
            </button>
          ))}
        </div>
        <label className="min-w-[12rem] flex-1 text-sm font-semibold sm:max-w-xs">
          Search
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Order, customer or item"
            className={input}
          />
        </label>
      </div>
      <QueryState query={list} label="Loading shipments">
        {(rows) =>
          rows.length === 0 ? (
            <p className="rounded-lg border border-rope bg-hull px-4 py-3 text-fog">
              No orders here yet. Use "New order" to log one.
            </p>
          ) : (
            <div className="divide-y divide-rope overflow-hidden rounded-lg border border-rope bg-hull">
              {rows.map((sh) => (
                <ShipmentRow
                  key={sh.order_no}
                  sh={sh}
                  asOf={asOf ?? sh.order_date}
                  defaultOpen={sh.order_no === highlight}
                />
              ))}
            </div>
          )
        }
      </QueryState>
    </div>
  );
}
