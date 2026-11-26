/**
 * The loading / error / cold-start states every page shares (BUILD_PROMPT §9.4):
 *   - quick answer:        a quiet "Loading…"
 *   - no answer after 3 s: "Waking up the server" (free hosting sleeps when idle)
 *   - failure:             a plain message, the reference id, and "Try again"
 * Fed by: any TanStack Query result.
 */
import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useShowAfter } from "../lib/useShowAfter";
import { ColdStartNotice } from "./ColdStartNotice";
import { ErrorState } from "./ErrorState";
import { LoadingState } from "./LoadingState";

const COLD_START_NOTICE_MS = 3000;

interface QueryStateProps<T> {
  query: UseQueryResult<T>;
  label?: string;
  children: (data: T) => ReactNode;
}

export function QueryState<T>({ query, label, children }: QueryStateProps<T>) {
  const slow = useShowAfter(query.isPending, COLD_START_NOTICE_MS);
  if (query.isPending) return slow ? <ColdStartNotice /> : <LoadingState label={label} />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  return <>{children(query.data)}</>;
}
