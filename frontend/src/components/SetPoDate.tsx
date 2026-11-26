/**
 * "Set real date" for a PO line (BUILD_PROMPT §6.6, Dana's reply 2026-11-26): a late PO isn't counted
 * as coming until Dana types the date the vendor gave her. Clearing it goes back to the computed date
 * (or back to late). The API rejects dates before today (the business date).
 * Fed by: PATCH /purchase-orders/{po}/lines/{n}.
 */
import { useState, type FormEvent } from "react";
import { useSetPoDate } from "../api/queries";

interface Props {
  poNo: string;
  lineNo: number;
  asOf: string;
  /** A date Dana already set, if any: shows "Clear" to undo it. */
  current?: string | null;
  label?: string;
}

export function SetPoDate({ poNo, lineNo, asOf, current = null, label = "Set real date" }: Props) {
  const save = useSetPoDate();
  const [open, setOpen] = useState(false);
  const [eta, setEta] = useState(current ?? "");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!eta) return;
    save.mutate({ poNo, lineNo, eta, note: null }, { onSuccess: () => setOpen(false) });
  };

  if (!open) {
    return (
      <span className="inline-flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="rounded-md border border-rope bg-hull px-3 py-1 text-sm font-semibold hover:bg-ice"
        >
          {label}
        </button>
        {current && (
          <button
            type="button"
            disabled={save.isPending}
            onClick={() => save.mutate({ poNo, lineNo, eta: null, note: null })}
            className="rounded-md px-2 py-1 text-sm text-fog underline underline-offset-2 hover:text-ink"
          >
            Clear date
          </button>
        )}
      </span>
    );
  }

  return (
    <form onSubmit={submit} className="inline-flex flex-wrap items-center gap-2">
      <label className="sr-only" htmlFor={`eta-${poNo}-${lineNo}`}>
        Real arrival date for {poNo} line {lineNo}
      </label>
      <input
        id={`eta-${poNo}-${lineNo}`}
        type="date"
        min={asOf}
        required
        value={eta}
        onChange={(e) => setEta(e.target.value)}
        className="rounded-md border border-rope px-2 py-1"
      />
      <button
        type="submit"
        disabled={save.isPending}
        className="rounded-md bg-ink px-3 py-1 text-sm font-semibold text-hull disabled:opacity-60"
      >
        {save.isPending ? "Saving…" : "Save arrival date"}
      </button>
      <button
        type="button"
        onClick={() => setOpen(false)}
        className="px-2 py-1 text-sm text-fog underline"
      >
        Cancel
      </button>
    </form>
  );
}
