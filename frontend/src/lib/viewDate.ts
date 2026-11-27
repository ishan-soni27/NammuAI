/**
 * "View as of" (Ishan 2026-11-26, ADR-034): look at the numbers as they stood on an earlier day,
 * from the day after BlueTide's latest stock count up to today. Null means today (Boston's date,
 * from the server).
 *
 * Kept for this browser tab only (sessionStorage), so a new visit always opens on today.
 * api/client.ts sends it as X-As-Of on every request and DownloadLink adds ?as_of=, so the server
 * computes everything for that day; edits made while viewing are dated by it too.
 * Storage can be blocked (private mode), so every access is wrapped; then the view lasts until reload.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useSyncExternalStore } from "react";

const STORAGE_KEY = "kestrel-bay.view-as-of";
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const listeners = new Set<() => void>();

function read(): string | null {
  try {
    const value = window.sessionStorage.getItem(STORAGE_KEY);
    return value && ISO_DATE.test(value) ? value : null;
  } catch {
    return null;
  }
}

let current: string | null = read();

/** The day being viewed ("YYYY-MM-DD"), or null for today. */
export function getViewDate(): string | null {
  return current;
}

function store(value: string | null): void {
  current = value;
  try {
    if (value) window.sessionStorage.setItem(STORAGE_KEY, value);
    else window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage blocked: the view lasts until the page reloads.
  }
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The day being viewed, re-rendering when it changes. */
export function useViewDate(): string | null {
  return useSyncExternalStore(subscribe, getViewDate, getViewDate);
}

/** Change the day being viewed (null = back to today) and reload every number for it. */
export function useSetViewDate(): (value: string | null) => void {
  const client = useQueryClient();
  return useCallback(
    (value: string | null) => {
      const next = value && ISO_DATE.test(value) ? value : null;
      if (next === current) return;
      store(next);
      // Every number depends on the day; health doesn't (it always reports today and the count).
      void client.resetQueries({ predicate: (q) => q.queryKey[0] !== "health" });
    },
    [client],
  );
}
