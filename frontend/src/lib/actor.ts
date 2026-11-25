/**
 * Who is using the app, sent as the X-Actor header so the audit log records a name
 * (there is no login in v1, ADR-011). Defaults to "Dana".
 *
 * Phase 5 adds the one-time "Who's using this?" prompt that calls setActor().
 * localStorage can be unavailable (private mode, blocked storage), so every access is
 * wrapped and falls back to the default.
 */
const STORAGE_KEY = "kestrel-bay.actor";
export const DEFAULT_ACTOR = "Dana";

export function getActor(): string {
  try {
    return window.localStorage.getItem(STORAGE_KEY)?.trim() || DEFAULT_ACTOR;
  } catch {
    return DEFAULT_ACTOR;
  }
}

export function setActor(name: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, name.trim());
  } catch {
    // Storage blocked: the audit log will say "Dana". Acceptable for v1.
  }
}
