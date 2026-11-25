/**
 * The Monday screen. Phase 1 (walking skeleton): proves the browser → API → database
 * chain works end to end and shows its status in plain words. Phase 5 replaces the body
 * with "What to order" and "What you're stuck with".
 * Fed by: GET /api/v1/health.
 */
import { API_BASE_URL } from "../api/client";
import { useHealth } from "../api/health";
import type { HealthResponse } from "../api/types";
import { ColdStartNotice } from "../components/ColdStartNotice";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { formatTimestamp } from "../lib/dates";
import { useShowAfter } from "../lib/useShowAfter";

const COLD_START_NOTICE_MS = 3000; // BUILD_PROMPT §9.4: show after 3 s with no response

function databaseSentence(health: HealthResponse): string {
  if (health.db === "not_configured") return "The server isn't connected to a database yet.";
  if (health.db === "down")
    return "The database isn't responding. It may be waking up, so try again in a minute.";
  if (!health.schema_ready) return "The database is connected, but its tables aren't set up yet.";
  return "The database is connected.";
}

function loadSentence(health: HealthResponse): string {
  return health.last_load_at
    ? `BlueTide data last loaded ${formatTimestamp(health.last_load_at)}.`
    : "No BlueTide data has been loaded yet.";
}

export function MondayPage() {
  const health = useHealth();
  const slow = useShowAfter(health.isPending, COLD_START_NOTICE_MS);

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      {health.isPending && (slow ? <ColdStartNotice /> : <LoadingState />)}

      {health.isError && <ErrorState error={health.error} onRetry={() => health.refetch()} />}

      {health.data && (
        <section
          className="rounded-lg border border-rope bg-hull px-5 py-4"
          aria-labelledby="status-heading"
        >
          <h1 id="status-heading" className="text-xl font-bold">
            {health.data.status === "ok" ? "Everything is connected" : "Almost ready"}
          </h1>
          <ul className="mt-3 space-y-1">
            <li>The server is up.</li>
            <li>{databaseSentence(health.data)}</li>
            <li>{loadSentence(health.data)}</li>
          </ul>
          <p className="mt-4 text-sm text-fog">
            The Monday screen (what to order and what you're stuck with) comes in a later step.
            Server version {health.data.version}, at {API_BASE_URL}.
          </p>
        </section>
      )}
    </main>
  );
}
