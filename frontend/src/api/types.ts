/**
 * TypeScript mirrors of the API's response shapes (backend/app/api/v1/schemas.py).
 *
 * Keep these in sync by hand: when a field is added to a Pydantic model, add it here too.
 * The TypeScript build then flags every component that needs to handle it.
 */

/** GET /api/v1/health */
export interface HealthResponse {
  /** "ok" when the database is reachable and migrated, otherwise "degraded". */
  status: "ok" | "degraded";
  db: "ok" | "down" | "not_configured";
  schema_ready: boolean;
  /** Business "today" as YYYY-MM-DD. Always use this, never the browser clock. */
  as_of: string;
  /** ISO timestamp (UTC) of the last successful data load, or null. */
  last_load_at: string | null;
  version: string;
}

/** The error envelope every failed API call returns. */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    request_id: string | null;
    details?: { field: string; problem: string }[];
  };
}
