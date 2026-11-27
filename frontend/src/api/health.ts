/**
 * useHealth(): GET /api/v1/health, the first call every page makes.
 *
 * It tells the header which date is "today" (Boston's calendar date from the server, ADR-034; never
 * the browser clock), how old BlueTide's count is, and whether the database is reachable. Retries a
 * few times because a sleeping server can take a while to answer the first call.
 */
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "./client";
import type { HealthResponse } from "./types";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => apiGet<HealthResponse>("/health", signal),
    retry: 3,
    retryDelay: (attempt) => Math.min(2000 * 2 ** attempt, 10_000),
    staleTime: 60_000,
  });
}
