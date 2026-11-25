/**
 * The top bar on every page: the app name and the business date ("Monday, November 16,
 * 2026"). The date comes from the API (AS_OF_DATE), never the browser clock, so
 * everyone sees the same "today" as the numbers.
 * Fed by: GET /api/v1/health → as_of.
 * Phase 5 adds the links to Lead times, Data notes and Activity.
 */
import { Link } from "react-router";
import { useHealth } from "../api/health";
import { formatLongDate } from "../lib/dates";

export function AppHeader() {
  const { data } = useHealth();

  return (
    <header className="border-b border-rope bg-hull">
      <div className="mx-auto flex max-w-7xl flex-wrap items-baseline justify-between gap-x-6 gap-y-1 px-4 py-3 sm:px-6">
        <Link to="/" className="text-lg font-bold text-ink">
          Kestrel Bay ordering
        </Link>
        <p className="text-fog">{data ? formatLongDate(data.as_of) : " "}</p>
      </div>
    </header>
  );
}
