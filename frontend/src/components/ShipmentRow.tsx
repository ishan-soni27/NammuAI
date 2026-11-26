/**
 * One order going out, as a dropdown row (Phase 6 step 2).
 * Closed: order number, customer, what's on it, when it ships, and its status (overdue is red).
 * Open: the lines, any flags from matching BlueTide's copy (R7, R8), the lots taken if shipped, and
 * the actions. "Ship" first shows the lots that will be taken, soonest to expire first; Dana can
 * change how much comes from each lot before confirming.
 * Fed by: GET /shipments, GET /shipments/{order}/picks, GET /stock-lots. Writes: ship / cancel / undo-ship.
 */
import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import {
  useCancelOrder,
  usePickPlan,
  useShipOrder,
  useStockLots,
  useUndoShip,
} from "../api/queries";
import type { Pick, PickPlan, Shipment, ShipmentLine } from "../api/types";
import { formatDateWithYear, formatShortDate } from "../lib/dates";
import { dayWithRelative, money, qty } from "../lib/format";
import { itemName } from "../lib/names";
import { input, label, primaryButton, quietButton, secondaryButton } from "../lib/ui";
import { ShipmentStatusChip } from "./StatusChip";

type Takes = Record<number, Record<string, string>>; // line -> lot -> qty typed

function LinePicks({
  line,
  building,
  takes,
  setTake,
}: {
  line: ShipmentLine;
  building: string;
  takes: Record<string, string>;
  setTake: (lot: string, value: string) => void;
}) {
  const lots = useStockLots(line.item_code);
  const here = (lots.data ?? []).filter((l) => l.location_code === building && l.counted);
  const total = Object.values(takes).reduce((sum, v) => sum + (Number(v) || 0), 0);
  const u = line.sell_uom;
  return (
    <div className="rounded-md bg-ice p-3">
      <p className="font-semibold">
        {itemName(line.description)}{" "}
        <span className="text-sm font-normal text-fog">{line.item_code}</span>
      </p>
      <p className={`text-sm ${Math.abs(total - line.qty) >= 0.5 ? "text-red" : "text-fog"}`}>
        Taking {qty(total, u)} of {qty(line.qty, u)}.
      </p>
      {here.length === 0 ? (
        <p className="text-sm text-red">No sellable stock of this item in this building.</p>
      ) : (
        <table className="mt-1 w-full text-sm">
          <thead className="text-left text-fog">
            <tr>
              <th className="py-1 pr-2 font-semibold">Lot</th>
              <th className="py-1 pr-2 font-semibold">Expires</th>
              <th className="py-1 pr-2 text-right font-semibold">Has</th>
              <th className="py-1 text-right font-semibold">Take</th>
            </tr>
          </thead>
          <tbody>
            {here.map((l) => (
              <tr key={l.lot_no}>
                <td className="py-1 pr-2">{l.lot_no}</td>
                <td className="py-1 pr-2">
                  {l.expiry_date ? formatDateWithYear(l.expiry_date) : "–"}
                </td>
                <td className="py-1 pr-2 text-right">{qty(l.qty, u)}</td>
                <td className="py-1 text-right">
                  <label className="sr-only" htmlFor={`take-${line.line_no}-${l.lot_no}`}>
                    Take from lot {l.lot_no}
                  </label>
                  <input
                    id={`take-${line.line_no}-${l.lot_no}`}
                    type="number"
                    min={0}
                    max={l.qty}
                    step="any"
                    value={takes[l.lot_no] ?? ""}
                    onChange={(e) => setTake(l.lot_no, e.target.value)}
                    className="w-24 rounded-md border border-rope bg-hull px-2 py-1 text-right"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function ShipPanel({ sh, onDone }: { sh: Shipment; onDone: () => void }) {
  const plan = usePickPlan(sh.order_no, true);
  if (plan.isPending) return <p className="text-sm text-fog">Working out which lots to take…</p>;
  if (!plan.data)
    return <p className="text-sm text-red">We couldn't work out the lots. Try again.</p>;
  return <ShipForm sh={sh} plan={plan.data} onDone={onDone} />;
}

function ShipForm({ sh, plan, onDone }: { sh: Shipment; plan: PickPlan; onDone: () => void }) {
  const ship = useShipOrder();
  const [takes, setTakes] = useState<Takes>(() => {
    const start: Takes = {};
    for (const p of plan.picks)
      start[p.line_no] = { ...(start[p.line_no] ?? {}), [p.lot_no]: String(p.qty) };
    return start;
  });
  const short = Object.entries(plan.short);
  const ok = sh.lines.every(
    (l) =>
      Math.abs(
        Object.values(takes[l.line_no] ?? {}).reduce((s, v) => s + (Number(v) || 0), 0) - l.qty,
      ) < 0.5,
  );
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const picks = Object.entries(takes).flatMap(([line, lots]) =>
      Object.entries(lots)
        .filter(([, v]) => Number(v) > 0)
        .map(([lot_no, v]) => ({ line_no: Number(line), lot_no, qty: Number(v) })),
    );
    ship.mutate({ orderNo: sh.order_no, picks }, { onSuccess: onDone });
  };
  return (
    <form onSubmit={submit} className="space-y-3">
      <p className="text-sm">
        Soonest to expire first, from {sh.location_name}. Change the amounts if you're taking other
        lots.
      </p>
      {short.length > 0 && (
        <p className="rounded-md bg-red-tint px-3 py-2 text-sm text-red">
          {sh.location_name} doesn't have enough:{" "}
          {short
            .map(([n, missing]) => {
              const line = sh.lines.find((l) => l.line_no === Number(n));
              return `${qty(missing, line?.sell_uom ?? "CS")} short of ${line?.item_code ?? ""}`;
            })
            .join("; ")}
          . Ship less, or move stock here first.
        </p>
      )}
      {sh.lines.map((l) => (
        <LinePicks
          key={l.line_no}
          line={l}
          building={sh.location_code}
          takes={takes[l.line_no] ?? {}}
          setTake={(lot, value) =>
            setTakes((t) => ({ ...t, [l.line_no]: { ...(t[l.line_no] ?? {}), [lot]: value } }))
          }
        />
      ))}
      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={!ok || ship.isPending} className={primaryButton}>
          {ship.isPending ? "Shipping…" : "Ship these"}
        </button>
        <button type="button" onClick={onDone} className={quietButton}>
          Not yet
        </button>
      </div>
    </form>
  );
}

function CancelForm({ sh, onDone }: { sh: Shipment; onDone: () => void }) {
  const cancel = useCancelOrder();
  const [reason, setReason] = useState("");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        cancel.mutate(
          { orderNo: sh.order_no, reason: reason.trim() || null },
          { onSuccess: onDone },
        );
      }}
      className="grid gap-3 rounded-md bg-red-tint p-3 sm:grid-cols-[1fr_auto]"
    >
      <label className={label}>
        Why is it cancelled? (optional)
        <input value={reason} onChange={(e) => setReason(e.target.value)} className={input} />
      </label>
      <div className="flex items-end gap-2">
        <button type="submit" disabled={cancel.isPending} className={primaryButton}>
          {cancel.isPending ? "Saving…" : "Cancel order"}
        </button>
        <button type="button" onClick={onDone} className={quietButton}>
          Keep it
        </button>
      </div>
    </form>
  );
}

function picksText(picks: Pick[], uom: string): string {
  return picks
    .map(
      (p) =>
        `${qty(p.qty, uom)} from lot ${p.lot_no}${p.expiry_date ? ` (expires ${formatDateWithYear(p.expiry_date)})` : ""}`,
    )
    .join(", ");
}

export function ShipmentRow({
  sh,
  asOf,
  defaultOpen = false,
}: {
  sh: Shipment;
  asOf: string;
  defaultOpen?: boolean;
}) {
  const [mode, setMode] = useState<null | "ship" | "cancel">(null);
  const undo = useUndoShip();
  const overdue = sh.status === "open" && sh.ship_date < asOf;
  const first = sh.lines[0];
  const what =
    sh.lines.length === 1 && first
      ? `${itemName(first.description)}, ${qty(first.qty, first.sell_uom)}`
      : `${sh.lines.length} items`;
  const when =
    sh.status === "shipped" && sh.shipped_on
      ? `Shipped ${formatShortDate(sh.shipped_on)}`
      : sh.status === "cancelled"
        ? "Cancelled"
        : `Ships ${dayWithRelative(sh.ship_date, asOf)}`;
  return (
    <details className="group/shipment" open={defaultOpen}>
      <summary className="grid cursor-pointer list-none grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 px-4 py-3 hover:bg-ice sm:grid-cols-[auto_minmax(0,14rem)_minmax(0,1fr)_auto]">
        <span
          aria-hidden="true"
          className="text-lg leading-none text-fog transition-transform group-open/shipment:rotate-90"
        >
          ›
        </span>
        <span className="min-w-0">
          <span className="block font-semibold">
            {sh.order_no}
            {sh.kind === "sample" && (
              <span className="ml-2 text-sm font-normal text-fog">sample</span>
            )}
          </span>
          <span className="block text-sm text-fog">{sh.customer_name}</span>
        </span>
        <span className="col-span-full col-start-2 row-start-2 min-w-0 text-sm sm:col-span-1 sm:col-start-3 sm:row-start-1">
          <span className="block">{what}</span>
          <span className="block text-fog">
            {when}, from {sh.location_name}
          </span>
        </span>
        <span className="col-start-3 row-start-1 justify-self-end sm:col-start-4">
          <ShipmentStatusChip status={overdue ? "overdue" : sh.status} />
        </span>
      </summary>
      <div className="space-y-3 px-4 pb-4 pl-11">
        <p className="text-sm text-fog">
          Ordered {formatShortDate(sh.order_date)} by {sh.created_by}.{sh.note && ` ${sh.note}`}
          {sh.cancel_reason && ` Cancelled: ${sh.cancel_reason}`}
        </p>
        <ul className="divide-y divide-rope">
          {sh.lines.map((l) => (
            <li key={l.line_no} className="py-2">
              <Link
                to={`/items/${encodeURIComponent(l.item_code)}`}
                className="font-semibold hover:underline"
              >
                {itemName(l.description)}{" "}
                <span className="text-sm font-normal text-fog">{l.item_code}</span>
              </Link>
              <p className="text-sm">
                {qty(l.qty, l.sell_uom)}
                {l.unit_price !== null && ` at ${money(l.unit_price)} each`}.{" "}
                {l.promised && "Counted as promised to the customer."}
                {l.taken_from_stock && `Taken from stock: ${picksText(l.picks, l.sell_uom)}.`}
                {l.taken_from_stock &&
                  !l.counts_as_demand &&
                  " Not counted as demand (a sample or not a real sale)."}
              </p>
              {l.flags.length > 0 && (
                <p className="mt-1 rounded-md bg-yellow-tint px-3 py-1.5 text-sm">
                  {l.flags.join(". ")}.
                </p>
              )}
            </li>
          ))}
        </ul>
        {mode === "ship" && <ShipPanel sh={sh} onDone={() => setMode(null)} />}
        {mode === "cancel" && <CancelForm sh={sh} onDone={() => setMode(null)} />}
        {mode === null && (
          <div className="flex flex-wrap gap-2">
            {sh.status === "open" && (
              <>
                <button type="button" onClick={() => setMode("ship")} className={secondaryButton}>
                  Ship
                </button>
                <button type="button" onClick={() => setMode("cancel")} className={quietButton}>
                  Cancel order
                </button>
              </>
            )}
            {sh.status === "shipped" && (
              <button
                type="button"
                disabled={undo.isPending}
                onClick={() => undo.mutate({ orderNo: sh.order_no })}
                className={quietButton}
              >
                Undo shipped
              </button>
            )}
          </div>
        )}
      </div>
    </details>
  );
}
