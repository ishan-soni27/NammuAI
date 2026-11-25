/** What Dana sees while a page's data loads: one quiet line, announced to screen readers. */
export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <p role="status" aria-live="polite" className="text-fog">
      {label}…
    </p>
  );
}
