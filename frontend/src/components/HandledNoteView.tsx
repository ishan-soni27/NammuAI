/**
 * Dana's "I've handled this" note, shown on the card and the item page: who, when, what she said,
 * whether it counts as on the way, and a hint when BlueTide has since caught up ("BlueTide now shows
 * PO-260412"). Once its arrival date has passed it stops counting (A25, Ishan 2026-11-27): only an
 * upload can show the stock arrived, and then BlueTide's count already holds it. Notes are cleared, never deleted, so the history stays in the Activity log.
 * Fed by: HandledNote; DELETE /handled/{id}.
 */
import { useClearHandled } from "../api/queries";
import type { HandledNote } from "../api/types";
import { formatShortDate, formatTimestamp } from "../lib/dates";
import { qty } from "../lib/format";

export function HandledNoteView({ note, uom }: { note: HandledNote; uom: string }) {
  const clear = useClearHandled();
  const what = [
    note.qty !== null ? `ordered ${qty(note.qty, uom)}` : null,
    note.eta ? `arriving ${formatShortDate(note.eta)}` : null,
  ]
    .filter(Boolean)
    .join(", ");

  const passed = Boolean(note.date_passed);
  return (
    <div
      className={`rounded-md px-3 py-2 text-ink ${passed ? "bg-yellow-tint ring-1 ring-inset ring-yellow" : "bg-grey-tint"}`}
    >
      <p>
        <span className="font-semibold">
          {note.created_by} marked this handled on {formatTimestamp(note.created_at)}
        </span>
        {what && <>: {what}</>}.
      </p>
      {note.note && <p className="mt-1">“{note.note}”</p>}
      {passed ? (
        <p className="mt-1 text-sm font-semibold">
          Its date has passed, so it's no longer counted as on the way. Upload this week's BlueTide
          files to see if it arrived, or clear this note and mark the item again with a new date.
        </p>
      ) : (
        <p className="mt-1 text-sm text-fog">
          {note.counts_as_incoming
            ? "Counted as on the way in the plan."
            : "Not counted as on the way (it needs both a quantity and an arrival date)."}
        </p>
      )}
      {note.bluetide_now_shows.length > 0 && (
        <p className="mt-1 text-sm text-ink">
          BlueTide now shows {note.bluetide_now_shows.join(", ")} for this item. If that's this
          order, you can clear this note so it isn't counted twice.
        </p>
      )}
      <button
        type="button"
        disabled={clear.isPending}
        onClick={() => clear.mutate({ id: note.id, reason: null })}
        className="mt-2 rounded-md border border-rope bg-hull px-3 py-1 text-sm font-semibold disabled:opacity-60"
      >
        {clear.isPending ? "Clearing…" : "Clear this note"}
      </button>
    </div>
  );
}
