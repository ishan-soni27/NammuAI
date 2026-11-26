/**
 * Data notes: "What we cleaned up and why" (BUILD_PROMPT §9.4). Every change the loader made to the
 * BlueTide exports is listed by problem, in plain English, with counts. Opening a problem shows the
 * affected rows 50 at a time, each with its file, line number and the original CSV values, so any
 * number on the Monday screen can be traced back to the export it came from.
 * Fed by: GET /data-issues/summary; GET /data-issues?trap_id=…
 */
import { useState } from "react";
import { useDataIssueSummary, useDataIssues } from "../api/queries";
import type { IssueTrap } from "../api/types";
import { QueryState } from "../components/QueryState";

const PAGE = 50;
const ACTION: Record<string, string> = {
  excluded: "Left out",
  corrected: "Corrected",
  flagged: "Flagged for you",
};

function TrapRows({ trapId }: { trapId: string }) {
  const [offset, setOffset] = useState(0);
  const page = useDataIssues(trapId, offset, true);
  return (
    <QueryState query={page} label="Loading rows">
      {(data) => (
        <div>
          <div className="-mx-1 overflow-x-auto">
            <table className="w-full min-w-[40rem] text-sm">
              <thead className="text-left text-fog">
                <tr>
                  <th className="px-1 py-1 font-semibold">File and line</th>
                  <th className="px-1 py-1 font-semibold">Item</th>
                  <th className="px-1 py-1 font-semibold">What we did</th>
                  <th className="px-1 py-1 font-semibold">Original row</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rope">
                {data.items.map((row) => (
                  <tr key={row.id}>
                    <td className="px-1 py-1.5 align-top">
                      {row.source_file}
                      {row.source_line_number !== null && (
                        <div className="text-fog">line {row.source_line_number}</div>
                      )}
                    </td>
                    <td className="px-1 py-1.5 align-top">{row.item_code ?? "–"}</td>
                    <td className="px-1 py-1.5 align-top">
                      {row.message}
                      {row.field && (row.original_value !== null || row.new_value !== null) && (
                        <div className="text-fog">
                          {row.field}:{" "}
                          {row.original_value === null ? "–" : `"${row.original_value}"`} became{" "}
                          {row.new_value === null ? "–" : `"${row.new_value}"`}
                        </div>
                      )}
                    </td>
                    <td className="px-1 py-1.5 align-top">
                      {row.raw ? (
                        <details>
                          <summary className="cursor-pointer text-soon">Show</summary>
                          <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 text-xs">
                            {Object.entries(row.raw).map(([k, v]) => (
                              <div key={k} className="contents">
                                <dt className="text-fog">{k}</dt>
                                <dd className="break-all">
                                  {v === "" ? <span className="text-fog">(blank)</span> : v}
                                </dd>
                              </div>
                            ))}
                          </dl>
                        </details>
                      ) : (
                        <span className="text-fog">–</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.total > PAGE && (
            <div className="mt-2 flex items-center gap-3 text-sm">
              <button
                type="button"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE))}
                className="rounded-md border border-rope px-3 py-1 font-semibold disabled:opacity-40"
              >
                Previous 50
              </button>
              <span className="text-fog">
                Rows {offset + 1} to {Math.min(offset + PAGE, data.total)} of{" "}
                {data.total.toLocaleString("en-US")}
              </span>
              <button
                type="button"
                disabled={offset + PAGE >= data.total}
                onClick={() => setOffset(offset + PAGE)}
                className="rounded-md border border-rope px-3 py-1 font-semibold disabled:opacity-40"
              >
                Next 50
              </button>
            </div>
          )}
        </div>
      )}
    </QueryState>
  );
}

function Trap({ trap }: { trap: IssueTrap }) {
  const [open, setOpen] = useState(false);
  return (
    <details
      className="rounded-lg border border-rope bg-hull"
      onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}
    >
      <summary className="flex cursor-pointer list-none flex-wrap items-baseline justify-between gap-x-4 px-4 py-3">
        <span className="font-semibold">
          {trap.title}{" "}
          {trap.trap_id && (
            <span className="whitespace-nowrap text-sm font-normal text-fog">{trap.trap_id}</span>
          )}
        </span>
        <span className="text-fog">
          {trap.count.toLocaleString("en-US")} row{trap.count === 1 ? "" : "s"}
        </span>
      </summary>
      <div className="border-t border-rope px-4 py-3">
        <ul className="space-y-1">
          {trap.rules.map((r) => (
            <li key={r.rule_code}>
              <span className="font-semibold">{ACTION[r.action] ?? r.action}</span>{" "}
              <span className="text-fog">({r.count.toLocaleString("en-US")})</span>: {r.example}
            </li>
          ))}
        </ul>
        <div className="mt-3">
          {open && trap.trap_id ? <TrapRows trapId={trap.trap_id} /> : null}
          {!trap.trap_id && (
            <p className="text-sm text-fog">These rows aren't grouped under a known problem.</p>
          )}
        </div>
      </div>
    </details>
  );
}

export function DataNotesPage() {
  const summary = useDataIssueSummary();
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">What we cleaned up and why</h1>
        <p className="mt-1 text-fog">
          BlueTide's exports have known problems. We never change the files; we fix things as we
          read them and write every change down here. Open a problem to see the rows, with the file,
          line and original values.
        </p>
      </div>
      <QueryState query={summary} label="Loading data notes">
        {(data) => (
          <div className="space-y-2">
            <p>
              {data.total.toLocaleString("en-US")} notes from the latest load, in{" "}
              {data.by_trap.length} groups.
            </p>
            {data.by_trap.map((t) => (
              <Trap key={t.trap_id ?? "none"} trap={t} />
            ))}
          </div>
        )}
      </QueryState>
    </div>
  );
}
