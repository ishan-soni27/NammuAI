/**
 * One import in progress (Phase 6 step 3; ADR-029): upload files into slots, check (a dry run that
 * changes nothing), then load with the check's one-time code. Works the same for BlueTide's seven
 * export files and for Dana's own templates (with a "Download the template" link per slot).
 * Fed by: the Import returned by every /imports call. Writes: PUT files, POST check, POST load, DELETE.
 */
import { useState } from "react";
import { API_BASE_URL } from "../api/client";
import { useCheckImport, useDiscardImport, useLoadImport, usePutImportFile } from "../api/queries";
import type { Import, ImportReport } from "../api/types";
import { primaryButton, quietButton, secondaryButton } from "../lib/ui";

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
      {report.problems && report.problems.length > 0 && (
        <div className="max-h-64 overflow-auto rounded-md border border-rope">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-hull text-left text-fog">
              <tr>
                <th className="px-2 py-1 font-semibold">File</th>
                <th className="px-2 py-1 font-semibold">Line</th>
                <th className="px-2 py-1 font-semibold">What to fix</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rope">
              {report.problems.map((p) => (
                <tr key={`${p.slot}-${p.line}-${p.message}`}>
                  <td className="px-2 py-1">{p.label}</td>
                  <td className="px-2 py-1">{p.line}</td>
                  <td className="px-2 py-1">{p.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
          Stock count in these files: {report.snapshot_date}
          {report.current_snapshot_date && ` (the one loaded now: ${report.current_snapshot_date})`}
          .
        </p>
      )}
      {report.notes && (
        <p className="text-sm text-fog">
          The loader would clean up {report.notes.total.toLocaleString("en-US")} rows (the data
          notes list each one after loading).
        </p>
      )}
      {(report.conflicts?.length ?? 0) + (report.orphans?.length ?? 0) > 0 && (
        <div className="rounded-md bg-yellow-tint px-3 py-2 text-sm">
          <p className="font-semibold">What it does to your own records:</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {[...(report.conflicts ?? []), ...(report.orphans ?? [])].map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
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
  const bluetide = current.kind === "bluetide";
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
        {bluetide
          ? "Choose the files BlueTide exported. Any you leave out reuse the last load's copy."
          : "Download a template, fill it in Excel, save it as CSV, and upload it. Use only the ones you need."}
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
                    : bluetide
                      ? `Not chosen: the last load's ${slot.expected_name} will be used`
                      : `Columns: ${slot.columns.join(", ")}`}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                {!bluetide && (
                  <a
                    href={`${API_BASE_URL}/import-templates/${slot.slot}.csv`}
                    className="text-sm font-semibold underline underline-offset-2"
                  >
                    Download the template
                  </a>
                )}
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
        Checking changes nothing. Loading replaces the BlueTide data in one go (or adds your
        records) and never touches the POs, orders, notes and settings you entered.
      </p>
    </div>
  );
}
