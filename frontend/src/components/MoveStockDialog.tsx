/**
 * Move part or all of a lot to another building (Phase 6 step 2): e.g. out of Harbor (paying
 * storage every month) into New Bedford, or releasing a QA hold. It's a paired out and in, and can
 * be undone on the item page's "Stock changes in the app" list (both halves are reversed).
 * Writes: POST /stock-moves.
 */
import { useState, type FormEvent } from "react";
import { useLocations, useMoveStock } from "../api/queries";
import { unitWord } from "../lib/format";
import { input, label, primaryButton, quietButton } from "../lib/ui";
import { Dialog } from "./Dialog";

interface Props {
  itemCode: string;
  itemLabel: string;
  fromLocation: string;
  fromName: string;
  lotNo: string;
  maxQty: number;
  uom: string;
  defaultTo?: string;
  onClose: () => void;
}

export function MoveStockDialog(p: Props) {
  const move = useMoveStock();
  const locations = useLocations();
  const choices = (locations.data ?? []).filter((l) => l.code !== p.fromLocation);
  const firstSellable =
    choices.find((l) => l.is_sellable && !l.is_third_party_storage) ?? choices[0];
  const [qty, setQty] = useState(String(Math.round(p.maxQty)));
  const [to, setTo] = useState(p.defaultTo ?? "");
  const [note, setNote] = useState("");
  const target = to || firstSellable?.code || "";
  const submit = (e: FormEvent) => {
    e.preventDefault();
    move.mutate(
      {
        item_code: p.itemCode,
        from_location: p.fromLocation,
        lot_no: p.lotNo,
        to_location: target,
        qty: Number(qty),
        note: note.trim() || null,
      },
      { onSuccess: p.onClose },
    );
  };
  return (
    <Dialog open title={`Move ${p.itemLabel}`} onClose={p.onClose}>
      <form onSubmit={submit} className="space-y-4">
        <p className="text-fog">
          Lot {p.lotNo} at {p.fromName}: {Math.round(p.maxQty).toLocaleString("en-US")}{" "}
          {unitWord(p.uom)}.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className={label}>
            How many ({unitWord(p.uom)})
            <input
              type="number"
              min={1}
              max={p.maxQty}
              step="any"
              required
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              className={input}
            />
          </label>
          <label className={label}>
            Move to
            <select value={target} onChange={(e) => setTo(e.target.value)} className={input}>
              {choices.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className={label}>
          Note (optional)
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={500}
            className={input}
          />
        </label>
        <div className="flex gap-3">
          <button type="submit" disabled={move.isPending || !target} className={primaryButton}>
            {move.isPending ? "Moving…" : "Move stock"}
          </button>
          <button type="button" onClick={p.onClose} className={quietButton}>
            Cancel
          </button>
        </div>
      </form>
    </Dialog>
  );
}
