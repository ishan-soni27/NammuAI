/**
 * The top bar on every page: the app name, the day the numbers are for ("Friday, November 27, 2026"),
 * how old BlueTide's stock count is, the page links, the "view as of" switch and who is using the app.
 * "Today" is Boston's calendar date from the API (ADR-034), never the browser clock, so everyone sees
 * the same day as the numbers. "View as of" (Ishan 2026-11-26) picks an earlier day, from the day after
 * the count up to today, for this browser tab only (lib/viewDate.ts).
 * Below the bar, DateBanners says when the view isn't today or the count is getting old.
 * Fed by: GET /api/v1/health → as_of, snapshot_date, data_date; lib/actor.ts for the name.
 */
import { useEffect, type ReactNode } from "react";
import { NavLink, Link } from "react-router";
import { useHealth } from "../api/health";
import { formatLongDate, formatShortDate } from "../lib/dates";
import { countAge, daysBetween } from "../lib/format";
import { useSetViewDate, useViewDate } from "../lib/viewDate";

const LINKS = [
  { to: "/", label: "Monday" },
  { to: "/on-the-way", label: "On the way" },
  { to: "/suppliers", label: "Suppliers" },
  { to: "/harbor", label: "Harbor" },
  { to: "/data", label: "Data" },
  { to: "/activity", label: "Activity" },
] as const;

interface AppHeaderProps {
  actor: string;
  onChangeActor: () => void;
}

/** A view date the server would refuse (before the data date, or after today) goes back to today. */
function useKeepViewInRange(today?: string, earliest?: string | null) {
  const view = useViewDate();
  const setView = useSetViewDate();
  useEffect(() => {
    if (!view || !today) return;
    if (view >= today || (earliest && view < earliest)) setView(null);
  }, [view, today, earliest, setView]);
}

export function AppHeader({ actor, onChangeActor }: AppHeaderProps) {
  const { data } = useHealth();
  const view = useViewDate();
  const setView = useSetViewDate();
  useKeepViewInRange(data?.as_of, data?.data_date);
  const shown = view ?? data?.as_of;
  const earliest = data?.data_date ?? data?.as_of;

  return (
    <header className="border-b border-rope bg-hull">
      <div className="mx-auto flex max-w-7xl flex-wrap items-baseline justify-between gap-x-6 gap-y-1 px-4 pt-3 sm:px-6">
        <Link to="/" className="text-lg font-bold text-ink">
          Kestrel Bay ordering
        </Link>
        <p className="text-fog">
          {shown ? formatLongDate(shown) : " "}
          {shown && data?.snapshot_date && (
            <span className="text-sm">
              {" "}
              · BlueTide count of {formatShortDate(data.snapshot_date)} (
              {countAge(daysBetween(data.snapshot_date, shown))})
            </span>
          )}
        </p>
      </div>
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 pb-2 pt-2 sm:px-6">
        <nav aria-label="Pages" className="-mx-2 flex flex-wrap">
          {LINKS.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === "/"}
              className={({ isActive }) =>
                `rounded-md px-2 py-1 ${isActive ? "font-semibold text-ink underline underline-offset-4" : "text-fog hover:text-ink"}`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-fog">
          {data && earliest && earliest < data.as_of && (
            <label className="inline-flex items-center gap-1.5">
              View as of
              <input
                type="date"
                value={shown ?? ""}
                min={earliest}
                max={data.as_of}
                onChange={(e) => {
                  const value = e.target.value;
                  if (!value || value === data.as_of) setView(null);
                  else if (value >= earliest && value < data.as_of) setView(value);
                }}
                className={`rounded border px-1.5 py-0.5 text-ink ${view ? "border-yellow bg-yellow-tint font-semibold" : "border-rope bg-hull"}`}
              />
            </label>
          )}
          <p>
            Using as: <span className="font-semibold text-ink">{actor}</span> ·{" "}
            <button
              type="button"
              onClick={onChangeActor}
              className="underline underline-offset-2 hover:text-ink"
            >
              change
            </button>
          </p>
        </div>
      </div>
    </header>
  );
}

/**
 * The strips under the header (ADR-034):
 *   - yellow "Viewing as of …" while the switch shows an earlier day, with "Back to today";
 *   - otherwise, once BlueTide's count is older than a week (stale_after_days), a reminder that the
 *     stock since then is estimated and this week's files should be uploaded: yellow, then red after
 *     two weeks (very_stale_after_days).
 */
export function DateBanners() {
  const { data } = useHealth();
  const view = useViewDate();
  const setView = useSetViewDate();
  if (!data) return null;

  if (view && view < data.as_of) {
    return (
      <Strip tone="yellow" label="Viewing an earlier day">
        <span>
          <span className="font-semibold">Viewing as of {formatLongDate(view)}</span>, not today (
          {formatShortDate(data.as_of)}). The numbers, and any change you make, use that day.
        </span>
        <button
          type="button"
          onClick={() => setView(null)}
          className="rounded-md border border-ink px-2.5 py-0.5 font-semibold hover:bg-hull"
        >
          Back to today
        </button>
      </Strip>
    );
  }

  const age = data.days_since_count;
  const stale = data.stale_after_days;
  if (!data.snapshot_date || age === null || age === undefined || !stale || age <= stale)
    return null;
  const veryStale = data.very_stale_after_days ? age > data.very_stale_after_days : false;
  return (
    <Strip tone={veryStale ? "red" : "yellow"} label="BlueTide's count is getting old">
      <span>
        {veryStale && <span aria-hidden="true">⚠ </span>}
        <span className="font-semibold">
          BlueTide's latest stock count is from {formatShortDate(data.snapshot_date)}, {age} days
          ago.
        </span>{" "}
        Stock since then is estimated from expected sales and scheduled orders
        {veryStale ? ", and after two weeks the estimate can be well off" : ""}.
      </span>
      <Link
        to="/data"
        className="rounded-md border border-ink px-2.5 py-0.5 font-semibold hover:bg-hull"
      >
        Upload this week's files
      </Link>
    </Strip>
  );
}

function Strip({
  tone,
  label,
  children,
}: {
  tone: "yellow" | "red";
  label: string;
  children: ReactNode;
}) {
  const colours =
    tone === "red" ? "border-red bg-red-tint text-red" : "border-yellow bg-yellow-tint text-ink";
  return (
    <div role="status" aria-label={label} className={`border-b-2 ${colours}`}>
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-2 text-sm sm:px-6">
        {children}
      </div>
    </div>
  );
}
