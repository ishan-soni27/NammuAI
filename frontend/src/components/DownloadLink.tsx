/**
 * "Download for Excel" (Phase 6 step 4; ADR-030): a plain link to GET /exports/{list}.csv.
 * The server names the file (kestrel-bay-<list>-<date>.csv) and writes it so Excel opens it
 * cleanly: dates as 2026-11-16, numbers without units (the unit is its own column), her words.
 */
import { API_BASE_URL } from "../api/client";

export type ExportList =
  "order-list" | "stuck-list" | "purchase-orders" | "shipments" | "data-notes";

export function DownloadLink({
  list,
  what,
  label = "Download for Excel",
}: {
  list: ExportList;
  /** What's in the file, for the hover hint and screen readers ("Every item and what to do"). */
  what: string;
  label?: string;
}) {
  return (
    <a
      href={`${API_BASE_URL}/exports/${list}.csv`}
      download
      title={`${what}, as a file Excel opens`}
      aria-label={`${label}: ${what}`}
      className="inline-flex items-center gap-1 text-sm font-semibold whitespace-nowrap underline underline-offset-2"
    >
      <svg
        aria-hidden="true"
        viewBox="0 0 16 16"
        className="h-4 w-4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
      >
        <path d="M8 2v8m0 0 3-3m-3 3L5 7M3 12.5h10" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {label}
    </a>
  );
}
