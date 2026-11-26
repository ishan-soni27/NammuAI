/**
 * The top bar on every page: the app name, the business date ("Monday, November 16, 2026"),
 * the page links, and who is using the app ("Using as: Dana · change").
 * The date comes from the API (AS_OF_DATE), never the browser clock, so everyone sees the
 * same "today" as the numbers.
 * Fed by: GET /api/v1/health → as_of; lib/actor.ts for the name.
 */
import { NavLink, Link } from "react-router";
import { useHealth } from "../api/health";
import { formatLongDate } from "../lib/dates";

const LINKS = [
  { to: "/", label: "Monday" },
  { to: "/purchase-orders", label: "Purchase orders" },
  { to: "/items", label: "Items" },
  { to: "/suppliers", label: "Suppliers" },
  { to: "/data-notes", label: "Data notes" },
  { to: "/activity", label: "Activity" },
] as const;

interface AppHeaderProps {
  actor: string;
  onChangeActor: () => void;
}

export function AppHeader({ actor, onChangeActor }: AppHeaderProps) {
  const { data } = useHealth();

  return (
    <header className="border-b border-rope bg-hull">
      <div className="mx-auto flex max-w-7xl flex-wrap items-baseline justify-between gap-x-6 gap-y-1 px-4 pt-3 sm:px-6">
        <Link to="/" className="text-lg font-bold text-ink">
          Kestrel Bay ordering
        </Link>
        <p className="text-fog">{data ? formatLongDate(data.as_of) : " "}</p>
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
        <p className="text-sm text-fog">
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
    </header>
  );
}
