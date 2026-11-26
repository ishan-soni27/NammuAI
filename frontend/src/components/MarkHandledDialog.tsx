/**
 * "I've handled this one" (Dana, call 00:09:45; BUILD_PROMPT §6.10). Quantity and arrival date are
 * optional. With both, the order counts as on the way, so the plan updates. With neither, the item
 * just moves to "Handled" with her note. Nothing is hidden: the item still shows under Handled.
 * Fed by: POST /items/{code}/handled.
 */
import { useState, type FormEvent } from "react";
import { useMarkHandled } from "../api/queries";
import type { ItemCard } from "../api/types";
import { itemName } from "../lib/names";
import { Dialog } from "./Dialog";

interface Props {
  card: ItemCard;
  asOf: string;
  open: boolean;
  onClose: () => void;
}

export function MarkHandledDialog({ card, asOf, open, onClose }: Props) {
  const mark = useMarkHandled();
  const [qty, setQty] = useState("");
  const [eta, setEta] = useState("");
  const [note, setNote] = useState("");
  const unit = card.sell_uom.toLowerCase();

  const submit = (e: FormEvent) => {
    e.preventDefault();
    mark.mutate(
      {
        code: card.item_code,
        qty: qty ? Number(qty) : null,
        eta: eta || null,
        note: note.trim() || null,
      },
      {
        onSuccess: () => {
          setQty("");
          setEta("");
          setNote("");
          onClose();
        },
      },
    );
  };

  return (
    <Dialog open={open} title={`Mark ${itemName(card.description)} as handled`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <p className="text-fog">
          Say what you did. If you give a quantity and an arrival date, we count it as on the way
          and the plan updates. You can clear this later.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-semibold">Quantity ordered ({unit}, optional)</span>
            <input
              type="number"
              inputMode="numeric"
              min={1}
              step="any"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              placeholder={card.order_at_least > 0 ? String(Math.ceil(card.order_at_least)) : ""}
              className="mt-1 w-full rounded-md border border-rope px-3 py-2"
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold">Arrives (optional)</span>
            <input
              type="date"
              min={asOf}
              value={eta}
              onChange={(e) => setEta(e.target.value)}
              className="mt-1 w-full rounded-md border border-rope px-3 py-2"
            />
          </label>
        </div>
        <label className="block">
          <span className="text-sm font-semibold">Note (optional)</span>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={500}
            rows={2}
            placeholder="Ordered from Bien Xanh, PO not in BlueTide yet"
            className="mt-1 w-full rounded-md border border-rope px-3 py-2"
          />
        </label>
        <div className="flex flex-wrap gap-3">
          <button
            type="submit"
            disabled={mark.isPending}
            className="rounded-md bg-ink px-4 py-2 font-semibold text-hull disabled:opacity-60"
          >
            {mark.isPending ? "Saving…" : "Mark as handled"}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-rope px-4 py-2 font-semibold"
          >
            Cancel
          </button>
        </div>
      </form>
    </Dialog>
  );
}
