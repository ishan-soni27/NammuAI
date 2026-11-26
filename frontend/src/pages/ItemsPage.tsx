/**
 * Items (Phase 6 step 1): every item, BlueTide's and Dana's, and a form to add her own, so the app
 * doesn't need BlueTide to know what she buys (Ishan, 2026-11-26). Each item is a dropdown row;
 * opening it lets her change its details (her copy wins over BlueTide's from then on).
 * Fed by: GET /item-details, GET /items (status), GET /vendors. Writes: POST /items, PATCH /items/{code}/details.
 */
import { useDeferredValue, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router";
import {
  useCreateItem,
  useItemDetails,
  useItems,
  useUpdateItemDetails,
  useVendors,
} from "../api/queries";
import type { ItemCard, ItemDetails, Vendor } from "../api/types";
import { QueryState } from "../components/QueryState";
import { SourceBadge, StatusChip } from "../components/StatusChip";
import { itemName } from "../lib/names";
import { input, label, primaryButton, quietButton, secondaryButton } from "../lib/ui";

interface Draft {
  item_code: string;
  description: string;
  category: string;
  sell_uom: "CS" | "LB";
  lb_per_case: string;
  vendor_code: string;
  status: "active" | "discontinued";
}

const blank: Draft = {
  item_code: "",
  description: "",
  category: "",
  sell_uom: "CS",
  lb_per_case: "",
  vendor_code: "",
  status: "active",
};

function ItemFields({
  draft,
  set,
  vendors,
  categories,
  isNew,
}: {
  draft: Draft;
  set: (patch: Partial<Draft>) => void;
  vendors: Vendor[];
  categories: string[];
  isNew: boolean;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {isNew && (
        <label className={label}>
          Item code
          <input
            required
            value={draft.item_code}
            onChange={(e) => set({ item_code: e.target.value })}
            placeholder="e.g. COD-LOIN6"
            className={input}
          />
        </label>
      )}
      <label className={`${label} ${isNew ? "sm:col-span-2" : "sm:col-span-3"}`}>
        Name
        <input
          required
          value={draft.description}
          onChange={(e) => set({ description: e.target.value })}
          className={input}
        />
      </label>
      <label className={label}>
        Category
        <input
          required
          list="item-categories"
          value={draft.category}
          onChange={(e) => set({ category: e.target.value })}
          className={input}
        />
        <datalist id="item-categories">
          {categories.map((c) => (
            <option key={c} value={c} />
          ))}
        </datalist>
      </label>
      <label className={label}>
        Sold by
        <select
          value={draft.sell_uom}
          onChange={(e) => set({ sell_uom: e.target.value as "CS" | "LB" })}
          className={input}
        >
          <option value="CS">The case</option>
          <option value="LB">The pound</option>
        </select>
      </label>
      <label className={label}>
        Pounds per case{draft.sell_uom === "LB" ? " (optional)" : ""}
        <input
          type="number"
          min={0}
          step="any"
          required={draft.sell_uom === "CS"}
          value={draft.lb_per_case}
          onChange={(e) => set({ lb_per_case: e.target.value })}
          className={input}
        />
      </label>
      <label className={label}>
        Supplier
        <select
          required
          value={draft.vendor_code}
          onChange={(e) => set({ vendor_code: e.target.value })}
          className={input}
        >
          <option value="">Choose a supplier</option>
          {vendors.map((v) => (
            <option key={v.vendor_code} value={v.vendor_code}>
              {v.name}
            </option>
          ))}
        </select>
      </label>
      <label className={label}>
        Still selling?
        <select
          value={draft.status}
          onChange={(e) => set({ status: e.target.value as "active" | "discontinued" })}
          className={input}
        >
          <option value="active">Yes</option>
          <option value="discontinued">No, stopped for good</option>
        </select>
      </label>
    </div>
  );
}

const toBody = (d: Draft) => ({
  description: d.description.trim(),
  category: d.category.trim(),
  sell_uom: d.sell_uom,
  lb_per_case: d.lb_per_case ? Number(d.lb_per_case) : null,
  vendor_code: d.vendor_code,
  status: d.status,
  note: null,
});

function AddItem({
  vendors,
  categories,
  onDone,
}: {
  vendors: Vendor[];
  categories: string[];
  onDone: () => void;
}) {
  const create = useCreateItem();
  const [draft, setDraft] = useState<Draft>(blank);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate({ item_code: draft.item_code.trim(), ...toBody(draft) }, { onSuccess: onDone });
  };
  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border border-rope bg-hull px-5 py-4">
      <h2 className="text-lg font-bold">Add an item</h2>
      <ItemFields
        draft={draft}
        set={(p) => setDraft({ ...draft, ...p })}
        vendors={vendors}
        categories={categories}
        isNew
      />
      <div className="flex gap-2">
        <button type="submit" disabled={create.isPending} className={primaryButton}>
          {create.isPending ? "Saving…" : "Add item"}
        </button>
        <button type="button" onClick={onDone} className={quietButton}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function ItemRow({
  item,
  card,
  vendors,
  categories,
}: {
  item: ItemDetails;
  card: ItemCard | undefined;
  vendors: Vendor[];
  categories: string[];
}) {
  const save = useUpdateItemDetails();
  const [draft, setDraft] = useState<Draft>({
    item_code: item.item_code,
    description: item.description,
    category: item.category,
    sell_uom: item.sell_uom,
    lb_per_case: item.lb_per_case !== null ? String(item.lb_per_case) : "",
    vendor_code: item.vendor_code,
    status: item.status,
  });
  const vendorName =
    vendors.find((v) => v.vendor_code === item.vendor_code)?.name ?? item.vendor_code;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate({ item_code: item.item_code, ...toBody(draft) });
  };
  return (
    <details className="group/item">
      <summary className="grid cursor-pointer list-none grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 px-4 py-3 hover:bg-ice">
        <span
          aria-hidden="true"
          className="text-lg leading-none text-fog transition-transform group-open/item:rotate-90"
        >
          ›
        </span>
        <span className="min-w-0">
          <span className="flex flex-wrap items-center gap-2 font-semibold">
            {itemName(item.description)}
            <span className="whitespace-nowrap text-sm font-normal text-fog">{item.item_code}</span>
            <SourceBadge source={item.source} />
          </span>
          <span className="block text-sm text-fog">
            {item.category}, sold by the {item.sell_uom === "CS" ? "case" : "pound"}, from{" "}
            {vendorName}
          </span>
        </span>
        {card ? <StatusChip status={card.handled_note ? "HANDLED" : card.status} /> : <span />}
      </summary>
      <form onSubmit={submit} className="space-y-3 px-4 pb-4 pl-11">
        <ItemFields
          draft={draft}
          set={(p) => setDraft({ ...draft, ...p })}
          vendors={vendors}
          categories={categories}
          isNew={false}
        />
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" disabled={save.isPending} className={primaryButton}>
            {save.isPending ? "Saving…" : "Save details"}
          </button>
          <Link
            to={`/items/${encodeURIComponent(item.item_code)}`}
            className="font-semibold underline underline-offset-2"
          >
            See all the numbers
          </Link>
          <Link
            to={`/purchase-orders/new?item=${encodeURIComponent(item.item_code)}`}
            className="font-semibold underline underline-offset-2"
          >
            Create a PO
          </Link>
          {item.source !== "app" && (
            <span className="text-sm text-fog">
              Your changes replace BlueTide's details for this item.
            </span>
          )}
        </div>
      </form>
    </details>
  );
}

export function ItemsPage() {
  const details = useItemDetails();
  const cards = useItems();
  const vendors = useVendors();
  const [adding, setAdding] = useState(false);
  const [search, setSearch] = useState("");
  const q = useDeferredValue(search.trim().toLowerCase());
  const cardsByCode = useMemo(
    () => new Map((cards.data ?? []).map((c) => [c.item_code, c])),
    [cards.data],
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Items</h1>
          <p className="text-fog">
            Everything you buy and sell. Add your own; they're planned like BlueTide's.
          </p>
        </div>
        {!adding && (
          <button type="button" onClick={() => setAdding(true)} className={secondaryButton}>
            Add an item
          </button>
        )}
      </div>
      <QueryState query={details} label="Loading items">
        {(list) => (
          <QueryState query={vendors} label="Loading suppliers">
            {(vendorList) => {
              const categories = [...new Set(list.map((i) => i.category))].sort();
              const shown = list.filter(
                (i) =>
                  !q ||
                  i.item_code.toLowerCase().includes(q) ||
                  i.description.toLowerCase().includes(q),
              );
              return (
                <div className="space-y-4">
                  {adding && (
                    <AddItem
                      vendors={vendorList}
                      categories={categories}
                      onDone={() => setAdding(false)}
                    />
                  )}
                  <label className="block max-w-xs text-sm font-semibold">
                    Search
                    <input
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Name or code"
                      className={input}
                    />
                  </label>
                  <div className="divide-y divide-rope overflow-hidden rounded-lg border border-rope bg-hull">
                    {shown.map((item) => (
                      <ItemRow
                        key={`${item.item_code}-${item.updated_at ?? ""}`}
                        item={item}
                        card={cardsByCode.get(item.item_code)}
                        vendors={vendorList}
                        categories={categories}
                      />
                    ))}
                  </div>
                </div>
              );
            }}
          </QueryState>
        )}
      </QueryState>
    </div>
  );
}
