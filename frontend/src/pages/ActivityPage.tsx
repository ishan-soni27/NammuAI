/**
 * Activity (BUILD_PROMPT §9.4, §10): who changed what (before and after), every data load, and
 * recent events and errors (server and browser). Nothing here is editable.
 * Fed by: GET /audit-log, GET /load-runs, GET /events.
 */
import { differenceInSeconds, parseISO } from "date-fns";
import type { ReactNode } from "react";
import { useAuditLog, useEvents, useLoadRuns } from "../api/queries";
import type { AuditEntry } from "../api/types";
import { QueryState } from "../components/QueryState";
import { formatTimestamp } from "../lib/dates";

const ACTION: Record<string, string> = {
  "handled.create": "Marked as handled",
  "handled.clear": "Cleared a handled note",
  "po_eta.set": "Set an arrival date",
  "po_eta.clear": "Cleared an arrival date",
  "vendor_settings.update": "Changed supplier terms",
  "item_settings.update": "Changed item settings",
};

const show = (v: unknown) =>
  v === null || v === undefined ? "–" : typeof v === "string" ? v : JSON.stringify(v);

function Changes({ entry }: { entry: AuditEntry }) {
  const before = entry.before ?? {};
  const after = entry.after ?? {};
  const keys = [...new Set([...Object.keys(before), ...Object.keys(after)])].filter(
    (k) => show(before[k]) !== show(after[k]),
  );
  if (keys.length === 0) return <span className="text-fog">No field changed</span>;
  return (
    <ul className="space-y-0.5">
      {keys.map((k) => (
        <li key={k}>
          <span className="text-fog">{k}:</span> {show(before[k])} <span aria-hidden="true">→</span>
          <span className="sr-only">became</span> {show(after[k])}
        </li>
      ))}
    </ul>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-rope bg-hull px-5 py-4">
      <h2 className="text-lg font-bold">{title}</h2>
      <div className="relative mt-3 -mx-1 overflow-x-auto">{children}</div>
    </section>
  );
}

const th = "px-1 py-1 text-left font-semibold text-fog";
const td = "px-1 py-1.5 align-top";

export function ActivityPage() {
  const audit = useAuditLog();
  const runs = useLoadRuns();
  const events = useEvents();
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Activity</h1>
        <p className="mt-1 text-fog">
          Every change anyone made, every data load, and anything that went wrong.
        </p>
      </div>

      <Section title="Changes">
        <QueryState query={audit} label="Loading changes">
          {(list) =>
            list.length === 0 ? (
              <p className="px-1 text-fog">No changes yet.</p>
            ) : (
              <table className="w-full min-w-[40rem] text-sm">
                <thead>
                  <tr>
                    <th className={th}>When</th>
                    <th className={th}>Who</th>
                    <th className={th}>What</th>
                    <th className={th}>Before and after</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rope">
                  {list.map((e) => (
                    <tr key={e.id}>
                      <td className={td}>{formatTimestamp(e.occurred_at)}</td>
                      <td className={td}>{e.actor}</td>
                      <td className={td}>
                        {ACTION[e.action] ?? e.action}
                        <div className="text-fog">
                          {show(e.after?.["item_code"] ?? e.before?.["item_code"] ?? e.entity_id)}
                        </div>
                      </td>
                      <td className={td}>
                        <Changes entry={e} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
          }
        </QueryState>
      </Section>

      <Section title="Data loads">
        <QueryState query={runs} label="Loading data loads">
          {(list) =>
            list.length === 0 ? (
              <p className="px-1 text-fog">No data loaded yet.</p>
            ) : (
              <table className="w-full min-w-[40rem] text-sm">
                <thead>
                  <tr>
                    <th className={th}>Started</th>
                    <th className={th}>Result</th>
                    <th className={th}>Took</th>
                    <th className={th}>Files</th>
                    <th className={th}>Notes</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rope">
                  {list.map((r) => {
                    const issues = r.summary["issues"];
                    return (
                      <tr key={r.id}>
                        <td className={td}>{formatTimestamp(r.started_at)}</td>
                        <td className={td}>
                          {r.status === "succeeded"
                            ? "Loaded"
                            : r.status === "failed"
                              ? "Failed (nothing changed)"
                              : r.status}
                        </td>
                        <td className={td}>
                          {r.finished_at
                            ? `${differenceInSeconds(parseISO(r.finished_at), parseISO(r.started_at))} s`
                            : "–"}
                        </td>
                        <td className={td}>
                          {r.files.length} files,{" "}
                          {r.files.reduce((n, f) => n + f.rows, 0).toLocaleString("en-US")} rows
                        </td>
                        <td className={td}>
                          {typeof issues === "number" ? issues.toLocaleString("en-US") : "–"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )
          }
        </QueryState>
      </Section>

      <Section title="Events and errors">
        <QueryState query={events} label="Loading events">
          {(list) =>
            list.length === 0 ? (
              <p className="px-1 text-fog">Nothing recorded.</p>
            ) : (
              <table className="w-full min-w-[40rem] text-sm">
                <thead>
                  <tr>
                    <th className={th}>When</th>
                    <th className={th}>Level</th>
                    <th className={th}>From</th>
                    <th className={th}>What</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rope">
                  {list.map((e) => (
                    <tr key={e.id} className={e.level === "ERROR" ? "text-late" : ""}>
                      <td className={td}>{formatTimestamp(e.occurred_at)}</td>
                      <td className={td}>
                        {e.level === "ERROR" ? "Error" : e.level === "WARNING" ? "Warning" : "Info"}
                      </td>
                      <td className={td}>
                        {e.source === "web" ? "Browser" : e.source === "api" ? "Server" : e.source}
                      </td>
                      <td className={td}>
                        {e.event}
                        {e.request_id && <div className="text-fog">Reference {e.request_id}</div>}
                        {e.details && (
                          <details>
                            <summary className="cursor-pointer text-soon">Details</summary>
                            <pre className="mt-1 max-w-xl overflow-x-auto whitespace-pre-wrap break-all text-xs text-ink">
                              {JSON.stringify(e.details, null, 2)}
                            </pre>
                          </details>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
          }
        </QueryState>
      </Section>
    </div>
  );
}
