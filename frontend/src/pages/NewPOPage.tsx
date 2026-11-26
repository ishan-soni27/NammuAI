/**
 * New PO (Phase 6 step 1). Pick a supplier, then its items; quantities in cases or lb. The arrival
 * date defaults to order date + that supplier's time to arrive, and can be changed. Opened from a
 * Monday row or the item page with ?item=CODE&qty=N, the form is filled in already.
 * On save it counts as on the way at once; the item's "handled" note is cleared (ticked by default)
 * so the same order isn't counted twice.
 * Writes: POST /purchase-orders.
 */
import { useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { useHealth } from "../api/health";
import { useCreatePO, useItemDetails, useVendors } from "../api/queries";
import type { ItemDetails, Vendor } from "../api/types";
import { QueryState } from "../components/QueryState";
import { Term } from "../components/Term";
import { dayWithRelative, weeks } from "../lib/format";
import { itemName } from "../lib/names";
import { addDays, input, label, primaryButton, quietButton, secondaryButton } from "../lib/ui";

interface LineDraft {
  item: string;
  qty: string;
  cost: string;
}

function Form({ vendors, items, asOf }: { vendors: Vendor[]; items: ItemDetails[]; asOf: string }) {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const create = useCreatePO();
  const preset = items.find((i) => i.item_code === params.get("item"));
  const [vendor, setVendor] = useState(preset?.vendor_code ?? "");
  const [poNo, setPoNo] = useState("");
  const [orderDate, setOrderDate] = useState(asOf);
  const [expected, setExpected] = useState("");
  const [note, setNote] = useState("");
  const [allItems, setAllItems] = useState(false);
  const [clearNotes, setClearNotes] = useState(true);
  const [lines, setLines] = useState<LineDraft[]>([
    { item: preset?.item_code ?? "", qty: params.get("qty") ?? "", cost: "" },
  ]);

  const supplier = vendors.find((v) => v.vendor_code === vendor);
  const choices = useMemo(
    () =>
      items
        .filter((i) => i.status === "active" && (allItems || !vendor || i.vendor_code === vendor))
        .sort((a, b) => a.description.localeCompare(b.description)),
    [items, allItems, vendor],
  );
  const autoDate = supplier ? addDays(orderDate, supplier.lead_time_days) : null;
  const unitOf = (code: string) =>
    items.find((i) => i.item_code === code)?.sell_uom === "LB" ? "lb" : "cases";
  const setLine = (n: number, patch: Partial<LineDraft>) =>
    setLines((all) => all.map((l, i) => (i === n ? { ...l, ...patch } : l)));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate(
      {
        vendor_code: vendor,
        po_no: poNo.trim() || null,
        order_date: orderDate || null,
        expected_date: expected || null,
        note: note.trim() || null,
        lines: lines
          .filter((l) => l.item && l.qty)
          .map((l) => ({
            item_code: l.item,
            qty: Number(l.qty),
            unit_cost: l.cost ? Number(l.cost) : null,
          })),
        clear_handled_notes: clearNotes,
      },
      {
        onSuccess: (po) =>
          navigate(`/purchase-orders?status=all&po=${encodeURIComponent(po.po_no)}`),
      },
    );
  };

  return (
    <form onSubmit={submit} className="space-y-5 rounded-lg border border-rope bg-hull px-5 py-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className={label}>
          Supplier
          <select
            required
            value={vendor}
            onChange={(e) => setVendor(e.target.value)}
            className={input}
          >
            <option value="">Choose a supplier</option>
            {vendors.map((v) => (
              <option key={v.vendor_code} value={v.vendor_code}>
                {v.name} ({weeks(v.lead_time_days)} to arrive)
              </option>
            ))}
          </select>
          <span className="mt-1 block font-normal text-fog">
            Not in the list?{" "}
            <Link to="/suppliers" className="underline">
              Add a supplier
            </Link>
            .
          </span>
        </label>
        <label className={label}>
          PO number (optional)
          <input
            value={poNo}
            onChange={(e) => setPoNo(e.target.value)}
            placeholder="Leave blank for the next KB- number"
            className={input}
          />
        </label>
        <label className={label}>
          Order date
          <input
            type="date"
            max={asOf}
            required
            value={orderDate}
            onChange={(e) => setOrderDate(e.target.value)}
            className={input}
          />
        </label>
        <label className={label}>
          Expected arrival
          <input
            type="date"
            min={asOf}
            value={expected}
            onChange={(e) => setExpected(e.target.value)}
            className={input}
          />
          <span className="mt-1 block font-normal text-fog">
            {autoDate
              ? `Blank uses ${dayWithRelative(autoDate, asOf)}: the order date plus ${weeks(supplier!.lead_time_days)} `
              : "Blank uses the order date plus the supplier's time "}
            <Term explain="arrive">to arrive</Term>.
          </span>
        </label>
      </div>

      <fieldset className="space-y-3">
        <legend className="font-semibold">What you're ordering</legend>
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
              Cost each (optional)
              <input
                type="number"
                min={0}
                step="any"
                value={l.cost}
                onChange={(e) => setLine(n, { cost: e.target.value })}
                placeholder="Last cost"
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
        <div className="flex flex-wrap items-center gap-4">
          <button
            type="button"
            onClick={() => setLines((all) => [...all, { item: "", qty: "", cost: "" }])}
            className={secondaryButton}
          >
            Add another item
          </button>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={allItems}
              onChange={(e) => setAllItems(e.target.checked)}
            />
            Show items from every supplier
          </label>
        </div>
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
      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          checked={clearNotes}
          onChange={(e) => setClearNotes(e.target.checked)}
          className="mt-1"
        />
        If you marked any of these items as handled, clear that note, so the same order isn't
        counted twice.
      </label>
      <div className="flex flex-wrap gap-3">
        <button type="submit" disabled={create.isPending} className={primaryButton}>
          {create.isPending ? "Saving…" : "Save PO"}
        </button>
        <Link to="/purchase-orders" className={secondaryButton}>
          Cancel
        </Link>
      </div>
    </form>
  );
}

export function NewPOPage() {
  const vendors = useVendors();
  const items = useItemDetails();
  const asOf = useHealth().data?.as_of;
  return (
    <div className="space-y-4">
      <div>
        <Link to="/purchase-orders" className="text-sm font-semibold underline underline-offset-2">
          Back to purchase orders
        </Link>
        <h1 className="mt-1 text-2xl font-bold">New PO</h1>
        <p className="text-fog">It counts as on the way as soon as you save it.</p>
      </div>
      <QueryState query={vendors} label="Loading suppliers">
        {(vendorList) => (
          <QueryState query={items} label="Loading items">
            {(itemList) =>
              asOf ? (
                <Form vendors={vendorList} items={itemList} asOf={asOf} />
              ) : (
                <p className="text-fog">Loading…</p>
              )
            }
          </QueryState>
        )}
      </QueryState>
    </div>
  );
}
