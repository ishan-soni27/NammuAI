/**
 * Purchase orders (Phase 6 step 1): every PO, BlueTide's and Dana's, in one list.
 * Filters: Open (default), Late, Received, Cancelled, All; search by PO, supplier or item.
 * Each PO is a dropdown row (components/PORow.tsx) with the actions on each line.
 * Fed by: GET /purchase-orders.
 */
import { useDeferredValue, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useHealth } from "../api/health";
import { usePurchaseOrders } from "../api/queries";
import { PORow } from "../components/PORow";
import { QueryState } from "../components/QueryState";
import { input, primaryButton } from "../lib/ui";
import { DownloadLink } from "../components/DownloadLink";

const FILTERS = [
  ["open", "Open"],
  ["late", "Late"],
  ["received", "Received"],
  ["cancelled", "Cancelled"],
  ["all", "All"],
] as const;

export function PurchaseOrdersPage() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "open";
  const [search, setSearch] = useState(params.get("q") ?? "");
  const q = useDeferredValue(search.trim());
  const pos = usePurchaseOrders(status, q);
  const asOf = useHealth().data?.as_of;
  const highlight = params.get("po");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Purchase orders</h1>
          <p className="text-fog">
            Yours and BlueTide's in one list. What's still to come counts as on the way on Monday.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <DownloadLink list="purchase-orders" what="Every PO line, yours and BlueTide's" />
          <Link to="/purchase-orders/new" className={primaryButton}>
            New PO
          </Link>
        </div>
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
            placeholder="PO, supplier or item"
            className={input}
          />
        </label>
      </div>

      <QueryState query={pos} label="Loading purchase orders">
        {(list) =>
          list.length === 0 ? (
            <p className="rounded-lg border border-rope bg-hull px-4 py-3 text-fog">
              No purchase orders here.
            </p>
          ) : (
            <div className="divide-y divide-rope overflow-hidden rounded-lg border border-rope bg-hull">
              {list.map((po) => (
                <PORow
                  key={po.po_no}
                  po={po}
                  asOf={asOf ?? po.order_date}
                  defaultOpen={po.po_no === highlight}
                />
              ))}
            </div>
          )
        }
      </QueryState>
    </div>
  );
}
