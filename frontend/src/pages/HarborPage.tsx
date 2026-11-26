/**
 * Harbor storage (P1 #1; ADR-031): what the stock at Harbor Cold Storage costs a month.
 *
 * Dana types how many cases fit on a pallet for each item (remembered for next time). Pallets and
 * dollars a month show as she types. "Add to table" saves a row to her own table, worked out
 * again on the server, and the table downloads for Excel. A what-if form does the same for any
 * amount (for example, before sending stock to Harbor).
 * Fed by: GET /harbor-storage (and /items for the what-if list). Writes: POST /harbor-storage/rows,
 * DELETE /harbor-storage/rows/{id}, PATCH /items/{code}/settings (cases per pallet).
 */
import { useState } from "react";
import { Link } from "react-router";
import {
  useAddHarborRows,
  useDeleteHarborRow,
  useHarbor,
  useItems,
  useSaveCasesPerPallet,
} from "../api/queries";
import type { Harbor, HarborItem, HarborRow } from "../api/types";
import { Disclosure } from "../components/Disclosure";
import { DownloadLink } from "../components/DownloadLink";
import { QueryState } from "../components/QueryState";
import { TagChip } from "../components/StatusChip";
import { formatDateWithYear, formatTimestamp } from "../lib/dates";
import { money, qty } from "../lib/format";
import { itemName } from "../lib/names";
import { input, label, quietButton, secondaryButton } from "../lib/ui";

/**
 * Mirrors planning/storage.pallets_needed: each lot sits on its own pallets and a part pallet is
 * charged as a whole one (A47). A preview only: the server works it out again on "Add to table".
 */
function palletsFor(lotCases: number[], perPallet: number): number {
  return lotCases.reduce(
    (n, c) => n + (c > 0 ? Math.ceil(Number((c / perPallet).toFixed(6))) : 0),
    0,
  );
}

const pallets = (n: number) => `${n.toLocaleString("en-US")} ${n === 1 ? "pallet" : "pallets"}`;
const lots = (n: number) => `${n} ${n === 1 ? "lot" : "lots"}`;
const smallInput = "mt-1 block w-20 rounded-md border border-rope bg-hull px-3 py-2";
// Narrow enough that the box, the cost and "Add to table" share one line on a phone.
const rowInput = "block w-16 rounded-md border border-rope bg-hull px-2 py-2";

/** A whole number from 1 to max, or null. */
function parsePerPallet(text: string, max: number): number | null {
  if (!/^\d+$/.test(text.trim())) return null;
  const n = Number(text);
  return n >= 1 && n <= max ? n : null;
}

function Preview({
  count,
  rate,
  invalid,
  max,
}: {
  count: number | null;
  rate: number;
  invalid: boolean;
  max: number;
}) {
  return (
    <p className="min-w-24 text-sm leading-tight" aria-live="polite">
      {count === null ? (
        <span className={invalid ? "text-red" : "text-fog"}>
          {invalid ? `A whole number from 1 to ${max.toLocaleString("en-US")}` : "No cost yet"}
        </span>
      ) : (
        <>
          <span className="block font-semibold">{money(count * rate)} a month</span>
          <span className="block text-fog">{pallets(count)}</span>
        </>
      )}
    </p>
  );
}

function ItemRow({ item, harbor }: { item: HarborItem; harbor: Harbor }) {
  const [text, setText] = useState(item.cases_per_pallet?.toString() ?? "");
  const add = useAddHarborRows();
  const save = useSaveCasesPerPallet();
  const max = harbor.cases_per_pallet_max;
  const per = parsePerPallet(text, max);
  const dirty = per !== null && per !== item.cases_per_pallet;
  const count =
    per === null
      ? null
      : palletsFor(
          item.lots.map((l) => l.cases),
          per,
        );
  const id = `cpp-${item.item_code}`;

  return (
    <li className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2 px-3 py-3 sm:px-4">
      <div className="min-w-0 flex-1 basis-60">
        <p className="font-semibold">
          <Link to={`/items/${encodeURIComponent(item.item_code)}`} className="hover:underline">
            {itemName(item.description)}
          </Link>{" "}
          <span className="font-normal text-fog">{item.item_code}</span>
        </p>
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-fog">
          <span>
            {qty(item.cases, "CS")} in {lots(item.lots.length)}
          </span>
          {item.stuck_tag && <TagChip tag={item.stuck_tag} />}
        </p>
        {item.unconverted_lots > 0 && (
          <p className="text-sm text-red">
            {lots(item.unconverted_lots)} in pounds can't be put on pallets: add pounds per case on
            the Items page.
          </p>
        )}
      </div>
      <div>
        <label htmlFor={id} className={label}>
          Cases per pallet
        </label>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
          <input
            id={id}
            inputMode="numeric"
            value={text}
            onChange={(e) => setText(e.target.value)}
            aria-invalid={text.trim() !== "" && per === null}
            className={rowInput}
          />
          <Preview
            count={count}
            rate={harbor.rate_per_pallet_month}
            invalid={text.trim() !== "" && per === null}
            max={max}
          />
          {dirty && (
            <button
              type="button"
              disabled={save.isPending}
              onClick={() => save.mutate({ code: item.item_code, cases_per_pallet: per })}
              className={quietButton}
            >
              Save
            </button>
          )}
          <button
            type="button"
            disabled={per === null || add.isPending}
            onClick={() =>
              per !== null &&
              add.mutate({ rows: [{ item_code: item.item_code, cases_per_pallet: per }] })
            }
            className={secondaryButton}
          >
            Add to table
          </button>
        </div>
      </div>
    </li>
  );
}

function Summary({ harbor }: { harbor: Harbor }) {
  const add = useAddHarborRows();
  const { totals } = harbor;
  const missing = totals.items - totals.priced_items;
  const priced = harbor.items.filter((i) => i.cases_per_pallet !== null);
  return (
    <section
      aria-label="Harbor now"
      className="space-y-2 rounded-lg border border-rope bg-hull px-5 py-4"
    >
      <p className="text-lg font-semibold">
        {qty(totals.cases, "CS")} of {totals.items} items at Harbor now.
      </p>
      {totals.priced_items === 0 ? (
        <p className="text-fog">Type cases per pallet for an item below to see what it costs.</p>
      ) : (
        <p>
          With the cases per pallet you've saved
          {missing > 0 ? ` for ${totals.priced_items} of them` : ""}:{" "}
          <span className="font-semibold">
            {pallets(totals.pallets)}, {money(totals.cost_per_month)} a month
          </span>
          .{missing > 0 && ` ${missing} still need cases per pallet, so the full cost is higher.`}
        </p>
      )}
      {priced.length > 0 && (
        <button
          type="button"
          disabled={add.isPending}
          onClick={() =>
            add.mutate({
              rows: priced.map((i) => ({
                item_code: i.item_code,
                cases_per_pallet: i.cases_per_pallet ?? 0,
              })),
            })
          }
          className={secondaryButton}
        >
          Add all {priced.length} to your table
        </button>
      )}
    </section>
  );
}

function WhatIf({ harbor }: { harbor: Harbor }) {
  const items = useItems();
  const add = useAddHarborRows();
  const [code, setCode] = useState("");
  const [casesText, setCasesText] = useState("");
  const [perText, setPerText] = useState("");
  const max = harbor.cases_per_pallet_max;
  const cases = /^\d+(\.\d+)?$/.test(casesText.trim()) ? Number(casesText) : null;
  const per = parsePerPallet(perText, max);
  const count = cases && per ? palletsFor([cases], per) : null;
  const remembered = new Map(harbor.items.map((i) => [i.item_code, i.cases_per_pallet]));
  const options = [...(items.data ?? [])].sort((a, b) =>
    itemName(a.description).localeCompare(itemName(b.description)),
  );

  return (
    <div className="space-y-3">
      <p className="text-sm text-fog">
        Any item and amount, for example before sending stock to Harbor. Worked out as one lot.
      </p>
      <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
        <label className={`${label} min-w-0 flex-1 basis-64`}>
          Item
          <select
            value={code}
            onChange={(e) => {
              setCode(e.target.value);
              const known = remembered.get(e.target.value);
              if (known && perText === "") setPerText(String(known));
            }}
            className={input}
          >
            <option value="">Choose an item</option>
            {options.map((i) => (
              <option key={i.item_code} value={i.item_code}>
                {itemName(i.description)} ({i.item_code})
              </option>
            ))}
          </select>
        </label>
        <label className={label}>
          Cases
          <input
            inputMode="decimal"
            value={casesText}
            onChange={(e) => setCasesText(e.target.value)}
            className={smallInput}
          />
        </label>
        <label className={label}>
          Cases per pallet
          <input
            inputMode="numeric"
            value={perText}
            onChange={(e) => setPerText(e.target.value)}
            aria-invalid={perText.trim() !== "" && per === null}
            className={smallInput}
          />
        </label>
        <Preview
          count={count}
          rate={harbor.rate_per_pallet_month}
          invalid={perText.trim() !== "" && per === null}
          max={max}
        />
        <button
          type="button"
          disabled={!code || !cases || per === null || add.isPending}
          onClick={() =>
            per !== null &&
            cases &&
            add.mutate(
              { rows: [{ item_code: code, cases_per_pallet: per, cases }] },
              { onSuccess: () => setCasesText("") },
            )
          }
          className={`${secondaryButton} mb-0.5`}
        >
          Add to table
        </button>
      </div>
    </div>
  );
}

function SavedTable({ rows }: { rows: HarborRow[] }) {
  const remove = useDeleteHarborRow();
  if (rows.length === 0) {
    return (
      <p className="rounded-lg border border-rope bg-hull px-4 py-3 text-fog">
        Nothing here yet. "Add to table" keeps a row exactly as it was worked out, so you can
        download the table for Excel.
      </p>
    );
  }
  const num = "px-3 py-2 text-right tabular-nums";
  return (
    <div className="relative overflow-x-auto rounded-lg border border-rope bg-hull">
      <table className="w-full min-w-[46rem] text-sm">
        <thead className="text-left text-fog">
          <tr className="border-b border-rope">
            <th className="px-3 py-2 font-semibold">Worked out for</th>
            <th className="px-3 py-2 font-semibold">Item</th>
            <th className="px-3 py-2 font-semibold">What</th>
            <th className={`${num} font-semibold`}>Cases</th>
            <th className={`${num} font-semibold`}>Per pallet</th>
            <th className={`${num} font-semibold`}>Pallets</th>
            <th className={`${num} font-semibold`}>A month</th>
            <th className="px-3 py-2 font-semibold">Added by</th>
            <th className="px-3 py-2">
              <span className="sr-only">Remove</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-rope">
          {rows.map((r) => (
            <tr key={r.id}>
              <td className="px-3 py-2 whitespace-nowrap">{formatDateWithYear(r.as_of_date)}</td>
              <td className="min-w-56 px-3 py-2">
                {itemName(r.description)} <span className="text-fog">{r.item_code}</span>
              </td>
              <td className="px-3 py-2 whitespace-nowrap">
                {r.kind === "at_harbor" ? `At Harbor, ${lots(r.lots)}` : "What-if"}
              </td>
              <td className={num}>{Math.round(r.cases).toLocaleString("en-US")}</td>
              <td className={num}>{r.cases_per_pallet.toLocaleString("en-US")}</td>
              <td className={num}>{r.pallets.toLocaleString("en-US")}</td>
              <td className={`${num} font-semibold`}>{money(r.cost_per_month)}</td>
              <td
                className="px-3 py-2 whitespace-nowrap text-fog"
                title={formatTimestamp(r.created_at)}
              >
                {r.created_by}
              </td>
              <td className="px-3 py-2 text-right">
                <button
                  type="button"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate({ id: r.id })}
                  className={quietButton}
                  aria-label={`Remove ${r.item_code} from your table`}
                >
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HarborView({ harbor }: { harbor: Harbor }) {
  const where = harbor.location_names.join(" and ") || "Harbor Cold Storage";
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Harbor storage</h1>
          <p className="mt-1 max-w-3xl text-fog">
            {where} charges {money(harbor.rate_per_pallet_month)} per pallet per month. Type how
            many cases fit on a pallet for each item to see the pallets and the cost. Each lot sits
            on its own pallets, and a part pallet is charged as a whole one.
          </p>
        </div>
        <DownloadLink
          list="harbor-storage"
          label="Download your table for Excel"
          what="Every row you added to your Harbor table"
        />
      </div>

      <Summary harbor={harbor} />

      <section aria-labelledby="now-heading" className="space-y-2">
        <h2 id="now-heading" className="text-xl font-bold">
          At Harbor now
        </h2>
        {harbor.items.length === 0 ? (
          <p className="rounded-lg border border-rope bg-hull px-4 py-3 text-fog">
            Nothing is at Harbor right now.
          </p>
        ) : (
          <ul className="divide-y divide-rope rounded-lg border border-rope bg-hull">
            {harbor.items.map((item) => (
              <ItemRow key={item.item_code} item={item} harbor={harbor} />
            ))}
          </ul>
        )}
      </section>

      <Disclosure title="Work out another amount">
        <WhatIf harbor={harbor} />
      </Disclosure>

      <section aria-labelledby="table-heading" className="space-y-2">
        <h2 id="table-heading" className="text-xl font-bold">
          Your table
        </h2>
        <SavedTable rows={harbor.saved} />
      </section>
    </div>
  );
}

export function HarborPage() {
  const harbor = useHarbor();
  return (
    <QueryState query={harbor} label="Loading Harbor storage">
      {(data) => <HarborView harbor={data} />}
    </QueryState>
  );
}
