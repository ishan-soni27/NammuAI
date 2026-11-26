/**
 * New order going out (Phase 6 step 2): customer (or add one), the building it ships from, what's on
 * it, and when it ships. It counts as promised to the customer at once, on its ship date.
 * Transfers between our own buildings aren't orders: use Move stock on the item page or stuck list.
 * Writes: POST /shipments (and POST /customers for a new customer).
 */
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { useHealth } from "../api/health";
import {
  useCreateCustomer,
  useCreateShipment,
  useCustomers,
  useItemDetails,
  useLocations,
} from "../api/queries";
import type { Customer, ItemDetails, Location } from "../api/types";
import { QueryState } from "../components/QueryState";
import { itemName } from "../lib/names";
import { input, label, primaryButton, quietButton, secondaryButton } from "../lib/ui";

interface LineDraft {
  item: string;
  qty: string;
  price: string;
}

function AddCustomer({ types, onAdded }: { types: string[]; onAdded: (code: string) => void }) {
  const create = useCreateCustomer();
  const [name, setName] = useState("");
  // Restaurants are most of Kestrel Bay's customers; never default to the cruise line's type.
  const [type, setType] = useState(
    types.includes("RESTAURANT") ? "RESTAURANT" : (types[0] ?? "RESTAURANT"),
  );
  return (
    <div className="grid gap-3 rounded-md bg-ice p-3 sm:grid-cols-[2fr_1fr_auto]">
      <label className={label}>
        New customer's name
        <input value={name} onChange={(e) => setName(e.target.value)} className={input} />
      </label>
      <label className={label}>
        Type
        <select value={type} onChange={(e) => setType(e.target.value)} className={input}>
          {types.map((t) => (
            <option key={t} value={t}>
              {t.charAt(0) + t.slice(1).toLowerCase()}
            </option>
          ))}
        </select>
      </label>
      <div className="flex items-end">
        <button
          type="button"
          disabled={!name.trim() || create.isPending}
          onClick={() =>
            create.mutate(
              { name: name.trim(), customer_code: null, customer_type: type },
              { onSuccess: (c) => onAdded(c.customer_code) },
            )
          }
          className={secondaryButton}
        >
          Add customer
        </button>
      </div>
    </div>
  );
}

function Form({
  customers,
  items,
  locations,
  asOf,
}: {
  customers: Customer[];
  items: ItemDetails[];
  locations: Location[];
  asOf: string;
}) {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const create = useCreateShipment();
  const buildings = locations.filter((l) => l.is_sellable);
  const types = [...new Set(customers.map((c) => c.customer_type))]
    .filter((t) => t !== "INTERNAL")
    .sort();
  const [customer, setCustomer] = useState("");
  const [adding, setAdding] = useState(false);
  const [kind, setKind] = useState<"customer" | "sample">("customer");
  const [building, setBuilding] = useState(
    buildings.find((b) => !b.is_third_party_storage)?.code ?? "",
  );
  const [orderDate, setOrderDate] = useState(asOf);
  const [shipDate, setShipDate] = useState(asOf);
  const [orderNo, setOrderNo] = useState("");
  const [note, setNote] = useState("");
  const [lines, setLines] = useState<LineDraft[]>([
    { item: params.get("item") ?? "", qty: "", price: "" },
  ]);
  const setLine = (n: number, patch: Partial<LineDraft>) =>
    setLines((all) => all.map((l, i) => (i === n ? { ...l, ...patch } : l)));
  const unitOf = (code: string) =>
    items.find((i) => i.item_code === code)?.sell_uom === "LB" ? "lb" : "cases";
  const choices = items
    .filter((i) => i.status === "active")
    .sort((a, b) => a.description.localeCompare(b.description));
  const customerChoices = customers.filter((c) => c.customer_type !== "INTERNAL");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate(
      {
        customer_code: customer,
        order_no: orderNo.trim() || null,
        kind,
        order_date: orderDate || null,
        ship_date: shipDate || null,
        location_code: building,
        note: note.trim() || null,
        lines: lines
          .filter((l) => l.item && l.qty)
          .map((l) => ({
            item_code: l.item,
            qty: Number(l.qty),
            unit_price: l.price ? Number(l.price) : null,
          })),
      },
      {
        onSuccess: (sh) =>
          navigate(`/shipments?status=all&order=${encodeURIComponent(sh.order_no)}`),
      },
    );
  };

  return (
    <form onSubmit={submit} className="space-y-5 rounded-lg border border-rope bg-hull px-5 py-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className={label}>
            Customer
            <select
              required
              value={customer}
              onChange={(e) => setCustomer(e.target.value)}
              className={input}
            >
              <option value="">Choose a customer</option>
              {customerChoices.map((c) => (
                <option key={c.customer_code} value={c.customer_code}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          {!adding ? (
            <button
              type="button"
              onClick={() => setAdding(true)}
              className={`${quietButton} mt-1 px-0`}
            >
              New customer?
            </button>
          ) : (
            <div className="mt-2">
              <AddCustomer
                types={types.length ? types : ["RESTAURANT", "GROCERY"]}
                onAdded={(code) => {
                  setCustomer(code);
                  setAdding(false);
                }}
              />
            </div>
          )}
        </div>
        <label className={label}>
          Ships from
          <select value={building} onChange={(e) => setBuilding(e.target.value)} className={input}>
            {buildings.map((b) => (
              <option key={b.code} value={b.code}>
                {b.name}
              </option>
            ))}
          </select>
        </label>
        <label className={label}>
          Order date
          <input
            type="date"
            max={asOf}
            value={orderDate}
            onChange={(e) => setOrderDate(e.target.value)}
            className={input}
          />
        </label>
        <label className={label}>
          Ship date
          <input
            type="date"
            min={orderDate}
            value={shipDate}
            onChange={(e) => setShipDate(e.target.value)}
            className={input}
          />
        </label>
        <label className={label}>
          What kind
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as "customer" | "sample")}
            className={input}
          >
            <option value="customer">A customer order</option>
            <option value="sample">A free sample (not counted as demand)</option>
          </select>
        </label>
        <label className={label}>
          Order number (optional)
          <input
            value={orderNo}
            onChange={(e) => setOrderNo(e.target.value)}
            placeholder="Leave blank for the next SH- number"
            className={input}
          />
        </label>
      </div>
      <fieldset className="space-y-3">
        <legend className="font-semibold">What's going out</legend>
        {lines.map((l, n) => (
          <div key={n} className="grid gap-3 rounded-md bg-ice p-3 sm:grid-cols-[2fr_1fr_1fr_auto]">
            <label className={label}>
              Item
              <select
                required
                value={l.item}
                onChange={(e) => setLine(n, { item: e.target.value })}
                className={input}
              >
                <option value="">Choose an item</option>
                {choices.map((i) => (
                  <option key={i.item_code} value={i.item_code}>
                    {itemName(i.description)} ({i.item_code})
                  </option>
                ))}
              </select>
            </label>
            <label className={label}>
              Quantity ({l.item ? unitOf(l.item) : "cases or lb"})
              <input
                type="number"
                min={1}
                step="any"
                required
                value={l.qty}
                onChange={(e) => setLine(n, { qty: e.target.value })}
                className={input}
              />
            </label>
            <label className={label}>
              Price each (optional)
              <input
                type="number"
                min={0}
                step="any"
                value={l.price}
                onChange={(e) => setLine(n, { price: e.target.value })}
                className={input}
              />
            </label>
            <div className="flex items-end">
              {lines.length > 1 && (
                <button
                  type="button"
                  onClick={() => setLines((all) => all.filter((_, i) => i !== n))}
                  className={quietButton}
                >
                  Remove
                </button>
              )}
            </div>
          </div>
        ))}
        <button
          type="button"
          onClick={() => setLines((all) => [...all, { item: "", qty: "", price: "" }])}
          className={secondaryButton}
        >
          Add another item
        </button>
      </fieldset>
      <label className={label}>
        Note (optional)
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={500}
          className={input}
        />
      </label>
      <div className="flex flex-wrap gap-3">
        <button type="submit" disabled={create.isPending} className={primaryButton}>
          {create.isPending ? "Saving…" : "Save order"}
        </button>
        <Link to="/shipments" className={secondaryButton}>
          Cancel
        </Link>
      </div>
    </form>
  );
}

export function NewShipmentPage() {
  const customers = useCustomers();
  const items = useItemDetails();
  const locations = useLocations();
  const asOf = useHealth().data?.as_of;
  return (
    <div className="space-y-4">
      <div>
        <Link to="/shipments" className="text-sm font-semibold underline underline-offset-2">
          Back to shipments
        </Link>
        <h1 className="mt-1 text-2xl font-bold">New order</h1>
        <p className="text-fog">It counts as promised to the customer as soon as you save it.</p>
      </div>
      <QueryState query={customers} label="Loading customers">
        {(c) => (
          <QueryState query={items} label="Loading items">
            {(i) => (
              <QueryState query={locations} label="Loading buildings">
                {(l) =>
                  asOf ? (
                    <Form customers={c} items={i} locations={l} asOf={asOf} />
                  ) : (
                    <p>Loading…</p>
                  )
                }
              </QueryState>
            )}
          </QueryState>
        )}
      </QueryState>
    </div>
  );
}
