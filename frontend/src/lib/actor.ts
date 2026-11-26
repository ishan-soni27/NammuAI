/**
 * Who is using the app, sent as the X-Actor header so the audit log records a name
 * (there is no login in v1, ADR-011). Defaults to "Dana".
 *
 * The one-time "Who's using this?" prompt (components/ActorPrompt.tsx) calls setActor().
 * localStorage can be unavailable (private mode, blocked storage), so every access is
 * wrapped and falls back to the default.
 */
const STORAGE_KEY = "kestrel-bay.actor";
export const DEFAULT_ACTOR = "Dana";

/** True once someone has answered "Who's using this?" on this device. */
export function hasChosenActor(): boolean {
  try {
    return Boolean(window.localStorage.getItem(STORAGE_KEY)?.trim());
  } catch {
    return true; // storage blocked: don't nag on every page load
  }
}

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
