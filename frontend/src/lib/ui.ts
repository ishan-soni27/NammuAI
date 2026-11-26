/**
 * Shared class names for forms, so every page's inputs and buttons look and behave the same.
 * (Plain strings: Tailwind sees them here and keeps the styles.)
 */
export const input = "mt-1 w-full rounded-md border border-rope bg-hull px-3 py-2";
export const label = "block text-sm font-semibold";
export const primaryButton =
  "rounded-md bg-ink px-4 py-2 font-semibold text-hull disabled:opacity-50";
export const secondaryButton =
  "rounded-md border border-ink bg-hull px-3 py-1.5 font-semibold hover:bg-ice disabled:opacity-50";
export const quietButton = "px-2 py-1 text-sm text-fog underline underline-offset-2 hover:text-ink";

/** "2026-11-16" + n days, as "YYYY-MM-DD" (business dates are plain dates, no time zone). */
export function addDays(isoDate: string, days: number): string {
  const [y, m, d] = isoDate.split("-").map(Number) as [number, number, number];
  const date = new Date(Date.UTC(y, m - 1, d + days));
  return date.toISOString().slice(0, 10);
}
