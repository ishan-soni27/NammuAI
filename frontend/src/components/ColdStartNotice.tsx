/**
 * What Dana sees: a calm note that the free server is waking up, instead of a blank page.
 * Fed by: any pending query (shown by the parent after 3 s with no response).
 */
export function ColdStartNotice() {
  return (
    <div role="status" className="rounded-lg border border-rope bg-hull px-5 py-4 text-ink">
      <p className="font-semibold">Waking up the server.</p>
      <p className="mt-1 text-fog">
        Free hosting pauses when nobody is using it. This usually takes a few seconds.
      </p>
    </div>
  );
}
