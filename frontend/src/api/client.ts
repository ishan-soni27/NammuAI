/**
 * The one place the frontend talks to the API.
 *
 * - Base URL comes from VITE_API_BASE_URL (set on Vercel). Default is the local API.
 * - Every request sends X-Actor (for the audit trail) and X-Request-ID (so a browser
 *   error and the matching server log line share one reference id).
 * - Failures become an `ApiError` with a plain-English message and that reference id,
 *   which <ErrorState> shows to Dana.
 *
 * How to add an endpoint: write a small typed function next to the feature
 * (see api/health.ts) that calls apiGet<ResponseType>("/path").
 */
import { getActor } from "../lib/actor";
import type { ApiErrorBody } from "./types";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1"
).replace(/\/+$/, "");

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

/** GET a JSON resource. Throws ApiError on network failure or a non-2xx response. */
export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const requestId = newRequestId();
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Accept: "application/json", "X-Actor": getActor(), "X-Request-ID": requestId },
      signal,
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    // Server asleep, offline, or blocked by CORS: the browser gives no detail, so we explain.
    throw new ApiError(
      "We couldn't reach the server. It may be waking up, or your connection may be down.",
      "network_error",
      null,
      requestId,
    );
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const serverRequestId = response.headers.get("X-Request-ID") ?? requestId;
    if (isErrorBody(body)) {
      const { code, message, request_id } = body.error;
      throw new ApiError(message, code, response.status, request_id ?? serverRequestId);
    }
    throw new ApiError(
      `The server answered with an error (${response.status}).`,
      "http_error",
      response.status,
      serverRequestId,
    );
  }
  return body as T;
}
