/**
 * What Dana sees when something fails: a plain message, a reference id she can pass on
 * (it matches the server's log line), and a retry button.
 * Fed by: ApiError (src/api/client.ts) from any query.
 */
import { ApiError } from "../api/client";

interface ErrorStateProps {
  error: unknown;
  onRetry?: () => void;
}

export function ErrorState({ error, onRetry }: ErrorStateProps) {
  const message =
    error instanceof ApiError ? error.message : "Something went wrong while loading this page.";
  const reference = error instanceof ApiError ? error.requestId : null;

  return (
    <div role="alert" className="rounded-lg border border-red bg-red-tint px-5 py-4 text-ink">
      <p className="font-semibold text-red">That didn't load.</p>
      <p className="mt-1">{message}</p>
      {reference && <p className="mt-2 text-sm text-fog">Reference: {reference}</p>}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-md border border-rope bg-hull px-3 py-1.5 font-semibold hover:bg-ice"
        >
          Try again
        </button>
      )}
    </div>
  );
}
