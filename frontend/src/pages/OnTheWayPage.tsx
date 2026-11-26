/**
 * On the way (ADR-032): BlueTide's open PO lines, read only, exactly as the plan counts them.
 * POs are created, shipped and received in BlueTide and arrive here with each weekly upload. The one
 * thing Dana adds is the real arrival date ("Set real date"), which the plan uses from then on.
 * Late lines (no believable date) come first: they aren't counted until she sets one (Dana Q3).
 * Fed by: GET /purchase-orders (?q= search). Writes: PATCH /purchase-orders/{po}/lines/{n}.
 */
import { useDeferredValue, useState } from "react";
import { Link } from "react-router";
import { useHealth } from "../api/health";
import { useOnTheWay } from "../api/queries";
import type { OnTheWayLine } from "../api/types";
import { DownloadLink } from "../components/DownloadLink";
import { QueryState } from "../components/QueryState";
import { SetPoDate } from "../components/SetPoDate";
import { Term } from "../components/Term";
import { formatShortDate } from "../lib/dates";
import { dayWithRelative, qty } from "../lib/format";
import { itemName } from "../lib/names";
import { input } from "../lib/ui";

function Line({ line, asOf }: { line: OnTheWayLine; asOf: string }) {
  const setByDana = line.eta_source.startsWith("Set by");
  const corrected = line.eta && line.bluetide_date && line.eta !== line.bluetide_date;
  return (
    <li className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2 px-4 py-3">
      <div className="min-w-0 flex-1 basis-64">
        <p className="font-semibold">
          <Link
            to={`/items/${encodeURIComponent(line.item_code)}`}
            className="underline-offset-2 hover:underline"
          >
            {itemName(line.description)}
          </Link>{" "}
          <span className="font-normal text-fog">{line.item_code}</span>
        </p>
        <p className="text-sm text-fog">
          {line.po_no} line {line.line_no} · {line.vendor_name}
        </p>
      </div>
      <div className="min-w-0 basis-72 space-y-1 text-sm sm:text-right">
        <p>
          <span className="font-semibold">{qty(line.qty, line.sell_uom)}</span>{" "}
          {line.is_late ? (
            <span className="inline-block rounded bg-red-tint px-2 py-0.5 text-xs font-semibold text-red">
              <Term explain="late">Late</Term>: not counted
            </span>
          ) : (
            <>arriving about {line.eta ? dayWithRelative(line.eta, asOf) : "?"}</>
          )}
        </p>
        <p className="text-fog">
          {line.is_late
            ? line.bluetide_date
              ? `BlueTide said ${formatShortDate(line.bluetide_date)}, and nothing has arrived.`
              : "No date in BlueTide, and nothing has arrived."
            : setByDana
              ? line.eta_source
              : corrected
                ? `BlueTide says ${formatShortDate(line.bluetide_date ?? "")}; the real lead time says later.`
                : line.eta_source}
        </p>
        <div className="sm:flex sm:justify-end">
          <SetPoDate
            poNo={line.po_no}
            lineNo={line.line_no}
            asOf={asOf}
            current={setByDana ? line.eta : null}
            label={setByDana ? "Change date" : "Set real date"}
          />
        </div>
      </div>
    </li>
  );
}

export function OnTheWayPage() {
  const [search, setSearch] = useState("");
  const q = useDeferredValue(search.trim());
  const lines = useOnTheWay(q);
  const asOf = useHealth().data?.as_of;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">On the way</h1>
          <p className="max-w-3xl text-fog">
            BlueTide's open purchase orders, from your last upload. Late ones aren't counted until
            you set the date the supplier gave you.
          </p>
        </div>
        <DownloadLink list="purchase-orders" what="Every open PO line, our date and BlueTide's" />
      </div>
      <label className="block max-w-xs text-sm font-semibold">
        Search
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="PO, supplier or item"
          className={input}
        />
      </label>
      <QueryState query={lines} label="Loading what's on the way">
        {(list) =>
          list.length === 0 ? (
            <p className="rounded-lg border border-rope bg-hull px-4 py-3 text-fog">
              {q ? "No open PO lines match." : "Nothing is on the way."}
            </p>
          ) : (
            <ul className="divide-y divide-rope rounded-lg border border-rope bg-hull">
              {list.map((line) => (
                <Line
                  key={`${line.po_no}-${line.line_no}`}
                  line={line}
                  asOf={asOf ?? line.eta ?? ""}
                />
              ))}
            </ul>
          )
        }
      </QueryState>
    </div>
  );
}
