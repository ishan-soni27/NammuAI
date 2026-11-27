/**
 * Number and date wording for Dana (BUILD_PROMPT §9.5): always units, whole cases/pounds, dates
 * like "Mon Dec 14" plus "in 4 weeks", relative to the BUSINESS date (as_of), never the clock.
 */
import { differenceInCalendarDays } from "date-fns";
import { formatShortDate, parseBusinessDate } from "./dates";

// Units spelled out (Ishan, 2026-11-26: "what is cs?"). Same words as the API's explain.UNIT_WORDS.
const UNIT_WORDS: Record<string, [string, string]> = { CS: ["case", "cases"], LB: ["lb", "lb"] };

/** "cases" / "case" / "lb"; an unknown code is shown lower-cased, as BlueTide wrote it. */
export function unitWord(uom: string, value = 2): string {
  const [one, many] = UNIT_WORDS[uom.toUpperCase()] ?? [uom.toLowerCase(), uom.toLowerCase()];
  return Math.round(value) === 1 ? one : many;
}

/** "480 cases", "8,479 lb". */
export function qty(value: number | null | undefined, uom: string): string {
  if (value === null || value === undefined) return "–";
  return `${Math.round(value).toLocaleString("en-US")} ${unitWord(uom, value)}`;
}

/** "$81,232". */
export function money(value: number | null | undefined): string {
  if (value === null || value === undefined) return "–";
  return `$${Math.round(value).toLocaleString("en-US")}`;
}

/** "in 5 days", "in 4 weeks", "today", "3 days ago". */
export function relative(isoDate: string, asOf: string): string {
  const days = differenceInCalendarDays(parseBusinessDate(isoDate), parseBusinessDate(asOf));
  if (days === 0) return "today";
  if (days < 0) return `${-days} day${days === -1 ? "" : "s"} ago`;
  if (days < 14) return `in ${days} day${days === 1 ? "" : "s"}`;
  return `in ${Math.round(days / 7)} weeks`;
}

/** Calendar days from one business date to another (both "YYYY-MM-DD"). */
export function daysBetween(fromIso: string, toIso: string): number {
  return differenceInCalendarDays(parseBusinessDate(toIso), parseBusinessDate(fromIso));
}

/** How old BlueTide's count is: "yesterday", "12 days ago". */
export function countAge(days: number): string {
  if (days <= 0) return "today";
  return days === 1 ? "yesterday" : `${days} days ago`;
}

/** "Mon Dec 14 (in 4 weeks)". */
export function dayWithRelative(isoDate: string, asOf: string): string {
  return `${formatShortDate(isoDate)} (${relative(isoDate, asOf)})`;
}

/** A rough length of time: 8 -> "8 days", 30 -> "4 weeks". */
export function duration(days: number): string {
  if (days < 14) return `${days} day${days === 1 ? "" : "s"}`;
  return `${Math.round(days / 7)} weeks`;
}

/** 84 -> "12 weeks", 10 -> "10 days" (exact; for time to arrive and cushion). */
export function weeks(days: number): string {
  return days % 7 === 0 ? `${days / 7} week${days === 7 ? "" : "s"}` : `${days} days`;
}

/** {"CS": 420} -> "420 cs" (several units joined with " + "). */
export function byUnit(values: Record<string, number>): string {
  return Object.entries(values)
    .filter(([, v]) => v)
    .map(([u, v]) => qty(v, u))
    .join(" + ");
}
