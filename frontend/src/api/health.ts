/**
 * useHealth(): GET /api/v1/health, the first call every page makes.
 *
 * It tells the header which date is "today" (AS_OF_DATE from the server, never the
 * browser clock) and whether the database is reachable. Retries a few times because a
 * sleeping Render instance can take up to about a minute to answer (§8.1).
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
