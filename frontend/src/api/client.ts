/**
 * The one place the frontend talks to the API.
 *
 * - Base URL is the same site's /api/v1 (override with VITE_API_BASE_URL if ever needed).
 * - Every request sends X-Actor (for the audit trail) and X-Request-ID (so a browser
 *   error and the matching server log line share one reference id), and X-As-Of while the
 *   header's "view as of" shows an earlier day (lib/viewDate.ts; ADR-034).
 * - Failures become an `ApiError` with a plain-English message and that reference id,
 *   which <ErrorState> shows to Dana.
 *
 * How to add an endpoint: add a typed hook in api/queries.ts that calls
 * apiGet<ResponseType>("/path") or apiSend<ResponseType>("PATCH", "/path", body).
 */
import { getActor } from "../lib/actor";
import { getViewDate } from "../lib/viewDate";
import type { ApiErrorBody } from "./types";

// The API lives on the same site under /api (one Vercel project, two services; see the
// root vercel.json and ADR-002). Locally, the Vite dev server forwards /api to the FastAPI
// server on port 8000 (vite.config.ts), so the same relative path works everywhere and no
// CORS is involved. VITE_API_BASE_URL is only an optional override, e.g. to point a local
// frontend at the live API. `||` (not `??`) so a blank value also falls back.
const SAME_SITE_API = "/api/v1";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL?.trim() || SAME_SITE_API).replace(
  /\/+$/,
  "",
);

export class ApiError extends Error {
  readonly code: string;
  readonly status: number | null;
  readonly requestId: string | null;

  constructor(message: string, code: string, status: number | null, requestId: string | null) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}

function newRequestId(): string {
  // "web-" prefix makes browser-originated ids easy to spot in server logs.
  const random = globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);
  return `web-${random.replace(/-/g, "").slice(0, 24)}`;
}

function isErrorBody(value: unknown): value is ApiErrorBody {
  return typeof value === "object" && value !== null && "error" in value;
}

type Method = "GET" | "POST" | "PATCH" | "DELETE";

/** Send a request and return the JSON body. Throws ApiError on network failure or a non-2xx reply. */
async function request<T>(
  method: Method | "PUT",
  path: string,
  body?: unknown,
  signal?: AbortSignal,
  raw?: Blob,
): Promise<T> {
  const requestId = newRequestId();
  const headers: Record<string, string> = {
    Accept: "application/json",
    "X-Actor": getActor(),
    "X-Request-ID": requestId,
  };
  const viewDate = getViewDate();
  if (viewDate) headers["X-As-Of"] = viewDate;
  if (raw !== undefined) headers["Content-Type"] = "text/csv";
  else if (body !== undefined) headers["Content-Type"] = "application/json";
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: raw !== undefined ? raw : body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    // Server asleep, offline, or blocked: the browser gives no detail, so we explain.
    throw new ApiError(
      "We couldn't reach the server. It may be waking up, or your connection may be down.",
      "network_error",
      null,
      requestId,
    );
  }

  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const serverRequestId = response.headers.get("X-Request-ID") ?? requestId;
    if (isErrorBody(data)) {
      const { code, message, request_id } = data.error;
      throw new ApiError(message, code, response.status, request_id ?? serverRequestId);
    }
    throw new ApiError(
      `The server answered with an error (${response.status}).`,
      "http_error",
      response.status,
      serverRequestId,
    );
  }
  if (data === null) {
    // A 2xx that isn't JSON almost always means the request reached the website instead of
    // the API (routing or VITE_API_BASE_URL problem). Fail loudly instead of a blank page.
    console.error(`Expected JSON from ${API_BASE_URL}${path}; is the API service routed at /api?`);
    throw new ApiError(
      "The server sent back something we couldn't read.",
      "unexpected_response",
      response.status,
      response.headers.get("X-Request-ID") ?? requestId,
    );
  }
  return data as T;
}

/** GET a JSON resource. */
export function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>("GET", path, undefined, signal);
}

/** POST / PATCH / DELETE with an optional JSON body (Dana's edits). */
export function apiSend<T>(
  method: Exclude<Method, "GET">,
  path: string,
  body?: unknown,
): Promise<T> {
  return request<T>(method, path, body);
}

/** PUT a file's bytes as the request body (imports: the CSV exactly as on disk, so its SHA-256 matches). */
export function apiUpload<T>(path: string, file: Blob): Promise<T> {
  return request<T>("PUT", path, undefined, undefined, file);
}
