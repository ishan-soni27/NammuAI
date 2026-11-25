/**
 * useShowAfter(active, ms): true once `active` has stayed true for `ms` milliseconds.
 *
 * Used for the cold-start notice: show "Waking up the server" only if a request has been
 * pending for 3 s, so a fast answer never flashes a warning (BUILD_PROMPT §9.4).
 */
import { useEffect, useState } from "react";

export function useShowAfter(active: boolean, ms: number): boolean {
  const [elapsed, setElapsed] = useState(false);

  useEffect(() => {
    if (!active) return;
    const timer = window.setTimeout(() => setElapsed(true), ms);
    return () => {
      window.clearTimeout(timer);
      setElapsed(false);
    };
  }, [active, ms]);

  return active && elapsed;
}
