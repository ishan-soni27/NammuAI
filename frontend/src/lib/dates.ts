/**
 * Date helpers. Business dates arrive from the API as "YYYY-MM-DD".
 *
 * Trap: `new Date("2026-11-16")` is midnight UTC, which displays as Sunday Nov 15 in
 * Boston. date-fns `parseISO` treats a date-only string as LOCAL midnight, so the day
 * never shifts. Always parse business dates with `parseBusinessDate`.
 */
import { format, parseISO } from "date-fns";

export function parseBusinessDate(isoDate: string): Date {
  return parseISO(isoDate);
}

/** "Monday, November 16, 2026" (page header). */
export function formatLongDate(isoDate: string): string {
  return format(parseBusinessDate(isoDate), "EEEE, MMMM d, yyyy");
}

/** "Mon Dec 14" (list rows, BUILD_PROMPT §9.5). */
export function formatShortDate(isoDate: string): string {
  return format(parseBusinessDate(isoDate), "EEE MMM d");
}

/** A UTC timestamp shown in the viewer's local time, e.g. "Nov 25, 2026, 7:05 AM". */
export function formatTimestamp(isoTimestamp: string): string {
  return format(parseISO(isoTimestamp), "MMM d, yyyy, h:mm a");
}
