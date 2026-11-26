/**
 * Report unexpected browser errors to the API (POST /client-events → event_log, source "web"),
 * so Ishan can see them on the Activity page (BUILD_PROMPT §10). Never throws, never floods.
 */
import { apiSend } from "../api/client";

let sent = 0;
const MAX_PER_PAGE_LOAD = 20; // a broken page must not flood the log

export function reportClientEvent(
  event: string,
  details: Record<string, unknown>,
  level = "ERROR",
): void {
  if (sent >= MAX_PER_PAGE_LOAD) return;
  sent += 1;
  void apiSend("POST", "/client-events", {
    level,
    event,
    details: { ...details, page: window.location.pathname },
  }).catch(() => undefined);
}

export function installGlobalErrorReporting(): void {
  window.addEventListener("error", (e) =>
    reportClientEvent("window_error", { message: String(e.message) }),
  );
  window.addEventListener("unhandledrejection", (e) =>
    reportClientEvent("unhandled_rejection", { message: String(e.reason) }),
  );
}
