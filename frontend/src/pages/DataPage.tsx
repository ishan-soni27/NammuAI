/**
 * Data (ADR-029, ADR-032): Dana's weekly upload of BlueTide's exports, past uploads, and what the
 * loader cleaned up. BlueTide owns every fact; this is the only way stock, sales and POs get in.
 * "Load new BlueTide files": any file left out reuses the last load's copy. Each upload is checked
 * first (a dry run that changes nothing), then loaded with one click.
 * Fed by: GET /imports, /data-issues. Writes: /imports.
 */
import { useState } from "react";
import { useImports, useStartImport } from "../api/queries";
import type { Import } from "../api/types";
import { Disclosure } from "../components/Disclosure";
import { ImportPanel } from "../components/ImportPanel";
import { QueryState } from "../components/QueryState";
import { formatTimestamp } from "../lib/dates";
import { secondaryButton } from "../lib/ui";
import { DataNotesPage } from "./DataNotesPage";
import { DownloadLink } from "../components/DownloadLink";

const STATUS: Record<Import["status"], string> = {
  open: "Not checked yet",
  checked: "Checked, not loaded",
  loaded: "Loaded",
  failed: "Failed (nothing changed)",
  discarded: "Discarded",
};

export function DataPage() {
  const start = useStartImport();
  const history = useImports();
  const [active, setActive] = useState<Import | null>(null);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Data</h1>
          <p className="mt-1 text-fog">
            Bring in this week's BlueTide files. Nothing changes until you've seen the check and
            pressed Load.
          </p>
        </div>
        <DownloadLink
          list="data-notes"
          label="Download data notes for Excel"
          what="Every change the loader made to BlueTide's files, with file and line"
        />
      </div>

      <section
        aria-labelledby="import-heading"
        className="space-y-3 rounded-lg border border-rope bg-hull px-5 py-4"
      >
        <h2 id="import-heading" className="text-lg font-bold">
          Bring in new data
        </h2>
        {active ? (
          <ImportPanel key={active.id} imp={active} onDone={() => setActive(null)} />
        ) : (
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              disabled={start.isPending}
              onClick={() => start.mutate(undefined, { onSuccess: setActive })}
              className={secondaryButton}
            >
              Load new BlueTide files
            </button>
          </div>
        )}
      </section>

      <section aria-labelledby="history-heading" className="space-y-2">
        <h2 id="history-heading" className="text-xl font-bold">
          Past imports
        </h2>
        <QueryState query={history} label="Loading past imports">
          {(list) =>
            list.length === 0 ? (
              <p className="text-fog">No imports from the website yet.</p>
            ) : (
              <ul className="divide-y divide-rope rounded-lg border border-rope bg-hull">
                {list.slice(0, 10).map((imp) => (
                  <li
                    key={imp.id}
                    className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 text-sm"
                  >
                    <span>
                      <span className="font-semibold">BlueTide files</span>{" "}
                      <span className="text-fog">
                        {formatTimestamp(imp.created_at)} by {imp.created_by}
                        {imp.files.length > 0 &&
                          `, ${imp.files.length} file${imp.files.length === 1 ? "" : "s"}`}
                      </span>
                    </span>
                    <span className="flex items-center gap-3">
                      <span className={imp.status === "failed" ? "text-red" : "text-fog"}>
                        {STATUS[imp.status]}
                      </span>
                      {(imp.status === "open" || imp.status === "checked") && !active && (
                        <button
                          type="button"
                          onClick={() => setActive(imp)}
                          className="font-semibold underline"
                        >
                          Continue
                        </button>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            )
          }
        </QueryState>
      </section>

      <Disclosure title="What we cleaned up and why (every change the loader made to BlueTide's files)">
        <DataNotesPage embedded />
      </Disclosure>
    </div>
  );
}
