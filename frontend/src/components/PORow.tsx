/**
 * One purchase order on the Purchase orders page, as a dropdown row (same style as Monday).
 * Closed: PO number, supplier, what's on it, when it arrives, and its status.
 * Open: each line with ordered / received / still to come, the arrival date and who set it, any
 * flags from matching BlueTide's copy (planning/records.py, R1-R6), the receipts (with Undo), and
 * the actions: change date, mark shipped, receive, cancel, reopen.
 * Fed by: GET /purchase-orders. Writes: the PO line endpoints (api/v1/purchase_orders.py).
 */
import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import {
  useCancelLine,
  useLocations,
  useReceiveLine,
  useReopenLine,
  useShipLine,
  useUndoMovement,
} from "../api/queries";
import type { POLine, PurchaseOrder } from "../api/types";
import { formatShortDate } from "../lib/dates";
import { dayWithRelative, money, qty } from "../lib/format";
import { itemName } from "../lib/names";
import { input, label, primaryButton, quietButton, secondaryButton } from "../lib/ui";
import { SetPoDate } from "./SetPoDate";
import { POStatusChip, SourceBadge } from "./StatusChip";

type Mode = null | "ship" | "receive" | "cancel";

function keyDate(po: PurchaseOrder, asOf: string): string {
  if (po.status === "received") return "Received";
  if (po.status === "cancelled") return "Cancelled";
  if (po.status === "late") return "Late, no arrival date";
  return po.expected_date
    ? `Arrives ${dayWithRelative(po.expected_date, asOf)}`
    : "No arrival date";
}

function ShipForm({ line, asOf, onDone }: { line: POLine; asOf: string; onDone: () => void }) {
  const ship = useShipLine();
  const [container, setContainer] = useState(line.container_no ?? "");
  const [eta, setEta] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    ship.mutate(
      {
        po: line.po_no,
        line: line.line_no,
        container_no: container.trim() || null,
        eta: eta || null,
      },
      { onSuccess: onDone },
    );
  };
  return (
    <form
      onSubmit={submit}
      className="grid gap-3 rounded-md bg-ice p-3 sm:grid-cols-[1fr_1fr_auto]"
    >
      <label className={label}>
        Container number (optional)
        <input value={container} onChange={(e) => setContainer(e.target.value)} className={input} />
      </label>
      <label className={label}>
        New arrival date (optional)
        <input
          type="date"
          min={asOf}
          value={eta}
          onChange={(e) => setEta(e.target.value)}
          className={input}
        />
      </label>
      <div className="flex items-end gap-2">
        <button type="submit" disabled={ship.isPending} className={primaryButton}>
          {ship.isPending ? "Saving…" : "Mark shipped"}
        </button>
        <button type="button" onClick={onDone} className={quietButton}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function ReceiveForm({ line, asOf, onDone }: { line: POLine; asOf: string; onDone: () => void }) {
  const receive = useReceiveLine();
  const locations = useLocations();
  const buildings = (locations.data ?? []).filter((l) => l.can_receive);
  const firstBuilding =
    buildings.find((l) => l.is_sellable && !l.is_third_party_storage) ?? buildings[0];
  const [amount, setAmount] = useState(String(Math.round(line.remaining) || ""));
  const [building, setBuilding] = useState("");
  const [lot, setLot] = useState(`${line.po_no}-${line.line_no}`);
  const [expiry, setExpiry] = useState("");
  const [cost, setCost] = useState("");
  const [over, setOver] = useState(false);
  const unit = line.sell_uom === "CS" ? "cases" : "lb";
  const submit = (e: FormEvent) => {
    e.preventDefault();
    receive.mutate(
      {
        po: line.po_no,
        line: line.line_no,
        qty: Number(amount),
        location_code: building || firstBuilding?.code || "",
        lot_no: lot.trim(),
        expiry_date: expiry,
        unit_cost: cost ? Number(cost) : null,
        allow_over_receipt: over,
      },
      { onSuccess: onDone },
    );
  };
  return (
    <form onSubmit={submit} className="space-y-3 rounded-md bg-ice p-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <label className={label}>
          Quantity received ({unit})
          <input
            type="number"
            min={1}
            step="any"
            required
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className={input}
          />
        </label>
        <label className={label}>
          Building
          <select
            value={building || firstBuilding?.code || ""}
            onChange={(e) => setBuilding(e.target.value)}
            className={input}
          >
            {buildings.map((l) => (
              <option key={l.code} value={l.code}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
        <label className={label}>
          Lot number
          <input required value={lot} onChange={(e) => setLot(e.target.value)} className={input} />
        </label>
        <label className={label}>
          Expiry date
          <input
            type="date"
            required
            min={asOf}
            value={expiry}
            onChange={(e) => setExpiry(e.target.value)}
            className={input}
          />
        </label>
        <label className={label}>
          Cost per {line.sell_uom === "CS" ? "case" : "lb"} (optional)
          <input
            type="number"
            min={0}
            step="any"
            placeholder={line.unit_cost !== null ? String(line.unit_cost) : ""}
            value={cost}
            onChange={(e) => setCost(e.target.value)}
            className={input}
          />
        </label>
        <label className="flex items-end gap-2 pb-2 text-sm">
          <input type="checkbox" checked={over} onChange={(e) => setOver(e.target.checked)} />
          More than ordered arrived
        </label>
      </div>
      <div className="flex gap-2">
        <button type="submit" disabled={receive.isPending} className={primaryButton}>
          {receive.isPending ? "Saving…" : "Receive into stock"}
        </button>
        <button type="button" onClick={onDone} className={quietButton}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function CancelForm({ line, onDone }: { line: POLine; onDone: () => void }) {
  const cancel = useCancelLine();
  const [reason, setReason] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    cancel.mutate(
      { po: line.po_no, line: line.line_no, reason: reason.trim() || null },
      { onSuccess: onDone },
    );
  };
  return (
    <form
      onSubmit={submit}
      className="grid gap-3 rounded-md bg-red-tint p-3 sm:grid-cols-[1fr_auto]"
    >
      <label className={label}>
        Why is it cancelled? (optional)
        <input value={reason} onChange={(e) => setReason(e.target.value)} className={input} />
      </label>
      <div className="flex items-end gap-2">
        <button type="submit" disabled={cancel.isPending} className={primaryButton}>
          {cancel.isPending ? "Saving…" : "Cancel this line"}
        </button>
        <button type="button" onClick={onDone} className={quietButton}>
          Keep it
        </button>
      </div>
    </form>
  );
}

function LineBlock({ line, asOf }: { line: POLine; asOf: string }) {
  const [mode, setMode] = useState<Mode>(null);
  const reopen = useReopenLine();
  const undo = useUndoMovement();
  const u = line.sell_uom;
  const open = line.status === "open" || line.status === "shipped" || line.status === "late";
  const setByDana = line.eta_source?.startsWith("Set by") ?? false;

  return (
    <li className="space-y-2 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <Link
            to={`/items/${encodeURIComponent(line.item_code)}`}
            className="font-semibold hover:underline"
          >
            {itemName(line.description)}{" "}
            <span className="whitespace-nowrap text-sm font-normal text-fog">{line.item_code}</span>
          </Link>
          <p className="text-sm">
            Line {line.line_no}: ordered {qty(line.ordered, u)}
            {line.received > 0 && `, received ${qty(line.received, u)}`}
            {open && `, ${qty(line.remaining, u)} still to come`}
            {line.unit_cost !== null && ` at ${money(line.unit_cost)} each`}.
          </p>
          <p className="text-sm text-fog">
            {line.eta
              ? `Arrives ${dayWithRelative(line.eta, asOf)} (${line.eta_source ?? "your date"})`
              : open
                ? "No arrival date: not counted as coming until you set one."
                : ""}
            {line.bluetide_date && ` BlueTide said ${formatShortDate(line.bluetide_date)}.`}
            {line.shipped_on && ` Shipped ${formatShortDate(line.shipped_on)}`}
            {line.container_no && `, container ${line.container_no}`}
            {line.cancel_reason && ` Cancelled: ${line.cancel_reason}`}
          </p>
        </div>
        <POStatusChip status={line.status} />
      </div>

      {line.flags.length > 0 && (
        <p className="rounded-md bg-yellow-tint px-3 py-1.5 text-sm">
          {line.flags.map((f) => (f.endsWith(".") ? f : `${f}.`)).join(" ")}
        </p>
      )}

      {line.receipts.length > 0 && (
        <ul className="space-y-1 text-sm">
          {line.receipts.map((r) => (
            <li
              key={r.movement_id}
              className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md bg-ice px-3 py-1.5"
            >
              <span>
                Received {qty(r.qty, u)} on {formatShortDate(r.received_on)} into {r.location_name},
                lot {r.lot_no}
                {r.expiry_date &&
                  `, expires ${formatShortDate(r.expiry_date)} ${r.expiry_date.slice(0, 4)}`}
                {` (${r.created_by})`}.
                {!r.added_to_stock && r.why_not && (
                  <span className="text-fog"> Not added again: {r.why_not}.</span>
                )}
              </span>
              <button
                type="button"
                disabled={undo.isPending}
                onClick={() => undo.mutate({ id: r.movement_id, reason: null })}
                className={quietButton}
              >
                Undo
              </button>
            </li>
          ))}
        </ul>
      )}

      {mode === "ship" && <ShipForm line={line} asOf={asOf} onDone={() => setMode(null)} />}
      {mode === "receive" && <ReceiveForm line={line} asOf={asOf} onDone={() => setMode(null)} />}
      {mode === "cancel" && <CancelForm line={line} onDone={() => setMode(null)} />}

      {mode === null && (
        <div className="flex flex-wrap items-center gap-2">
          {open && (
            <>
              <button type="button" onClick={() => setMode("receive")} className={secondaryButton}>
                Receive
              </button>
              {line.status !== "shipped" && (
                <button type="button" onClick={() => setMode("ship")} className={secondaryButton}>
                  Mark shipped
                </button>
              )}
              <SetPoDate
                poNo={line.po_no}
                lineNo={line.line_no}
                asOf={asOf}
                current={setByDana ? line.eta : null}
                label={line.eta ? "Change date" : "Set real date"}
              />
              <button type="button" onClick={() => setMode("cancel")} className={quietButton}>
                Cancel line
              </button>
            </>
          )}
          {(line.status === "cancelled" || line.status === "shipped") && (
            <button
              type="button"
              disabled={reopen.isPending}
              onClick={() => reopen.mutate({ po: line.po_no, line: line.line_no })}
              className={quietButton}
            >
              {line.status === "cancelled" ? "Reopen line" : "Undo shipped"}
            </button>
          )}
        </div>
      )}
    </li>
  );
}

export function PORow({
  po,
  asOf,
  defaultOpen = false,
}: {
  po: PurchaseOrder;
  asOf: string;
  defaultOpen?: boolean;
}) {
  const first = po.lines[0];
  const what =
    po.lines.length === 1 && first
      ? `${itemName(first.description)}, ${qty(first.ordered, first.sell_uom)}`
      : `${po.lines.length} items`;
  return (
    <details className="group/po" open={defaultOpen}>
      <summary className="grid cursor-pointer list-none grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 px-4 py-3 hover:bg-ice sm:grid-cols-[auto_minmax(0,12rem)_minmax(0,1fr)_auto]">
        <span
          aria-hidden="true"
          className="text-lg leading-none text-fog transition-transform group-open/po:rotate-90"
        >
          ›
        </span>
        <span className="min-w-0">
          <span className="flex flex-wrap items-center gap-2 font-semibold">
            {po.po_no} <SourceBadge source={po.source} />
          </span>
          <span className="block text-sm text-fog">{po.vendor_name}</span>
        </span>
        <span className="col-span-full col-start-2 row-start-2 min-w-0 text-sm sm:col-span-1 sm:col-start-3 sm:row-start-1">
          <span className="block">{what}</span>
          <span className="block text-fog">{keyDate(po, asOf)}</span>
        </span>
        <span className="col-start-3 row-start-1 justify-self-end sm:col-start-4">
          <POStatusChip status={po.status} />
        </span>
      </summary>
      <div className="px-4 pb-3 pl-11">
        <p className="text-sm text-fog">
          Ordered {formatShortDate(po.order_date)}
          {po.created_by && ` by ${po.created_by}`}.{po.note && ` ${po.note}`}
        </p>
        <ul className="divide-y divide-rope">
          {po.lines.map((line) => (
            <LineBlock key={line.line_no} line={line} asOf={asOf} />
          ))}
        </ul>
      </div>
    </details>
  );
}
