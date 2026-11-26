/**
 * Lead times (BUILD_PROMPT §9.4): per supplier, how long an order takes to arrive and how much cushion
 * to keep. Dana edits in weeks; the API stores days (1 to 365, checked by the API). Each row saves on
 * its own, says so in a toast, and lands in the Activity log with her name.
 * Fed by: GET /vendors; PATCH /vendors/{code}.
 */
import { useState, type FormEvent } from "react";
import { useUpdateVendor, useVendors } from "../api/queries";
import type { Vendor } from "../api/types";
import { QueryState } from "../components/QueryState";
import { Term } from "../components/Term";
import { formatTimestamp } from "../lib/dates";
import { weeks } from "../lib/format";

const toWeeks = (days: number) => String(Math.round((days / 7) * 10) / 10);
const toDays = (weeksText: string) => Math.round(Number(weeksText) * 7);

function VendorRow({ vendor }: { vendor: Vendor }) {
  const save = useUpdateVendor();
  const [lead, setLead] = useState(toWeeks(vendor.lead_time_days));
  const [cushion, setCushion] = useState(toWeeks(vendor.cushion_days));
  const [note, setNote] = useState(vendor.note ?? "");
  const changed =
    toDays(lead) !== vendor.lead_time_days ||
    toDays(cushion) !== vendor.cushion_days ||
    (note.trim() || null) !== (vendor.note ?? null);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate({
      code: vendor.vendor_code,
      lead_time_days: toDays(lead),
      cushion_days: toDays(cushion),
      note: note.trim() || null,
    });
  };
  const id = `vendor-${vendor.vendor_code}`;

  return (
    <form
      onSubmit={submit}
      className="rounded-lg border border-rope bg-hull px-5 py-4"
      aria-labelledby={id}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-4">
        <h2 id={id} className="text-lg font-semibold">
          {vendor.name}{" "}
          <span className="whitespace-nowrap text-sm font-normal text-fog">
            {vendor.vendor_code}
          </span>
        </h2>
        <span className="text-fog">{vendor.country ?? "Country not in BlueTide"}</span>
      </div>
      <div className="mt-3 grid gap-4 sm:grid-cols-[1fr_1fr_1fr_2fr]">
        <div>
          <p className="text-sm font-semibold">BlueTide says</p>
          <p className="mt-2">
            {vendor.lead_time_days_bluetide !== null
              ? weeks(vendor.lead_time_days_bluetide)
              : vendor.lead_time_bluetide_text
                ? `"${vendor.lead_time_bluetide_text}" (unreadable)`
                : "Blank"}
          </p>
        </div>
        <label className="block">
          <span className="text-sm font-semibold">
            You say, weeks <Term explain="arrive">to arrive</Term>
          </span>
          <input
            type="number"
            inputMode="decimal"
            min={1 / 7}
            max={365 / 7}
            step="any"
            required
            value={lead}
            onChange={(e) => setLead(e.target.value)}
            className="mt-1 w-full rounded-md border border-rope px-3 py-2"
          />
        </label>
        <label className="block">
          <span className="text-sm font-semibold">
            <Term explain="cushion">Cushion</Term>, weeks
          </span>
          <input
            type="number"
            inputMode="decimal"
            min={1 / 7}
            max={365 / 7}
            step="any"
            required
            value={cushion}
            onChange={(e) => setCushion(e.target.value)}
            className="mt-1 w-full rounded-md border border-rope px-3 py-2"
          />
        </label>
        <label className="block">
          <span className="text-sm font-semibold">Note</span>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={500}
            className="mt-1 w-full rounded-md border border-rope px-3 py-2"
          />
        </label>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <button
          type="submit"
          disabled={!changed || save.isPending}
          className="rounded-md bg-ink px-4 py-2 font-semibold text-hull disabled:opacity-40"
        >
          {save.isPending ? "Saving…" : `Save ${vendor.name}`}
        </button>
        <span className="text-sm text-fog">
          {vendor.updated_at
            ? `Last changed by ${vendor.updated_by ?? "someone"} on ${formatTimestamp(vendor.updated_at)}.`
            : "Not changed yet."}{" "}
          Stored as {vendor.lead_time_days} days to arrive and {vendor.cushion_days} days of
          cushion.
        </span>
      </div>
    </form>
  );
}

export function LeadTimesPage() {
  const vendors = useVendors();
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Lead times</h1>
        <p className="mt-1 text-fog">
          How long each supplier takes from placing the order to having it in our building, and how
          much extra stock to keep for when ships slip. When BlueTide is wrong or blank, what you
          say here is what the plan uses.
        </p>
      </div>
      <QueryState query={vendors} label="Loading suppliers">
        {(list) => (
          <div className="space-y-3">
            {list.map((v) => (
              <VendorRow key={`${v.vendor_code}-${v.updated_at ?? ""}`} vendor={v} />
            ))}
          </div>
        )}
      </QueryState>
    </div>
  );
}
