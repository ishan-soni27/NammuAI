/**
 * One weekly upload in progress (ADR-029): BlueTide's export files go into slots, then a check (a dry
 * run that changes nothing), then a load with the check's one-time code. Slots left empty reuse the
 * last load's file.
 * Fed by: the Import returned by every /imports call. Writes: PUT files, POST check, POST load, DELETE.
 */
import { useState } from "react";
import { useCheckImport, useDiscardImport, useLoadImport, usePutImportFile } from "../api/queries";
import type { Import, ImportReport } from "../api/types";
import { formatShortDate } from "../lib/dates";
import { primaryButton, quietButton, secondaryButton } from "../lib/ui";

const n = (value: number) => value.toLocaleString("en-US");

function Report({ report }: { report: ImportReport }) {
  return (
    <div className="space-y-3">
      {report.blockers.length > 0 && (
        <div className="rounded-md bg-red-tint px-3 py-2 text-sm text-red">
          <p className="font-semibold">This can't be loaded yet:</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {report.blockers.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        </div>
      )}
      {report.warnings.length > 0 && (
        <div className="rounded-md bg-yellow-tint px-3 py-2 text-sm">
          <p className="font-semibold">Worth a look:</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {report.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}
      {report.changes && report.changes.length > 0 && (
        <div>
          <p className="text-sm font-semibold">What would change</p>
          <table className="mt-1 w-full max-w-lg text-sm">
            <tbody className="divide-y divide-rope">
              {report.changes.map((c) => (
                <tr key={c.what}>
                  <td className="py-1 pr-3">{c.what}</td>
                  {c.count !== undefined ? (
                    <td className="py-1 text-right font-semibold">
                      {c.count.toLocaleString("en-US")}
                    </td>
                  ) : (
                    <td className="py-1 text-right">
                      {c.now?.toLocaleString("en-US")} <span aria-hidden="true">→</span>
                      <span className="sr-only">would become</span>{" "}
                      <span className={c.now !== c.after ? "font-semibold" : ""}>
                        {c.after?.toLocaleString("en-US")}
                      </span>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {report.snapshot_date && (
        <p className="text-sm text-fog">
          Stock count in these files: {formatShortDate(report.snapshot_date)}
          {report.current_snapshot_date &&
            ` (the one loaded now: ${formatShortDate(report.current_snapshot_date)})`}
          .{report.today && ` Loading them makes today ${formatShortDate(report.today)}.`}
        </p>
      )}
      {report.sales && (
        <p className="text-sm text-fog">
          Sales lines: {n(report.sales.new)} new, {n(report.sales.updated)} changed (for example
          open to invoiced), {n(report.sales.unchanged)} the same, and {n(report.sales.kept)} older
          ones kept from earlier uploads. {report.sales.months_of_history} months of sales history
          in all.
        </p>
      )}
      {report.notes && (
        <p className="text-sm text-fog">
          The loader would clean up {report.notes.total.toLocaleString("en-US")} rows (the data
          notes list each one after loading).
        </p>
      )}
    </div>
  );
}

export function ImportPanel({ imp, onDone }: { imp: Import; onDone: () => void }) {
  const put = usePutImportFile();
  const check = useCheckImport();
  const load = useLoadImport();
  const discard = useDiscardImport();
  const [current, setCurrent] = useState(imp);
  const files = new Map(current.files.map((f) => [f.slot, f]));
  const busy = put.isPending || check.isPending || load.isPending;

  if (current.status === "loaded") {
    return (
      <div className="space-y-2 rounded-md bg-green-tint px-4 py-3">
        <p className="font-semibold text-green">Loaded.</p>
        <p className="text-sm">The Monday screen and every page now use the new data.</p>
        <button type="button" onClick={onDone} className={secondaryButton}>
          Done
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-fog">
        Choose the files BlueTide exported. Any you leave out reuse the last load's copy.
      </p>
      <ul className="divide-y divide-rope rounded-md border border-rope">
        {current.slots.map((slot) => {
          const file = files.get(slot.slot);
          return (
            <li
              key={slot.slot}
              className="flex flex-wrap items-center justify-between gap-3 px-3 py-2"
            >
              <div className="min-w-0">
                <p className="font-semibold">{slot.label}</p>
                <p className="text-sm text-fog">
                  {file
                    ? `${file.file_name}: ${file.rows.toLocaleString("en-US")} rows`
                    : `Not chosen: the last load's ${slot.expected_name} will be used`}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <label className={`${secondaryButton} cursor-pointer text-sm`}>
                  {file ? "Replace" : "Choose file"}
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    className="sr-only"
                    disabled={busy}
                    onChange={(e) => {
                      const chosen = e.target.files?.[0];
                      e.target.value = "";
                      if (chosen)
                        put.mutate(
                          { id: current.id, slot: slot.slot, file: chosen },
                          { onSuccess: setCurrent },
                        );
                    }}
                  />
                </label>
              </div>
            </li>
          );
        })}
      </ul>

      {current.report && current.status === "checked" && <Report report={current.report} />}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={busy || current.files.length === 0}
          onClick={() => check.mutate({ id: current.id }, { onSuccess: setCurrent })}
          className={secondaryButton}
        >
          {check.isPending
            ? "Checking…"
            : current.status === "checked"
              ? "Check again"
              : "Check these files"}
        </button>
        {current.status === "checked" && current.confirm_code && (
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              load.mutate(
                { id: current.id, confirm_code: current.confirm_code ?? "" },
                { onSuccess: setCurrent },
              )
            }
            className={primaryButton}
          >
            {load.isPending ? "Loading… (this can take a minute)" : "Load these files"}
          </button>
        )}
        <button
          type="button"
          disabled={busy}
          onClick={() => discard.mutate({ id: current.id }, { onSuccess: onDone })}
          className={quietButton}
        >
          Start over
        </button>
      </div>
      <p className="text-xs text-fog">
        Checking changes nothing. Loading replaces BlueTide's data in one go and never touches your
        dates, notes and settings.
      </p>
    </div>
  );
}
