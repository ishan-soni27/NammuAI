/**
 * "What you're stuck with" (BUILD_PROMPT §6.9, §9.2): items grouped by their worst tag, in the order
 * Expired › Stopped selling › Inside six-month line › Long at Harbor › Overstock. Lots at Harbor
 * (paying storage every month) are listed first and badged. Quantities and value at cost on every row.
 * Fed by: Dashboard.stuck_items.
 */
import { Link } from "react-router";
import type { StuckItem, StuckTag } from "../api/types";
import { formatShortDate } from "../lib/dates";
import { money, qty } from "../lib/format";
import { itemName } from "../lib/names";
import { HarborBadge, TAG_LABEL, TagChip } from "./StatusChip";
import { Term } from "./Term";

const TAG_ORDER: StuckTag[] = [
  "EXPIRED",
  "STOPPED_SELLING",
  "INSIDE_SIX_MONTHS",
  "LONG_AT_HARBOR",
  "OVERSTOCK",
];

function StuckRow({ item }: { item: StuckItem }) {
  const lots = [...item.lots].sort((a, b) => Number(b.at_harbor) - Number(a.at_harbor));
  const uom = item.sell_uom;
  return (
    <li className="py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <Link
          to={`/items/${encodeURIComponent(item.item_code)}`}
          className="font-semibold hover:underline"
        >
          {itemName(item.description)}{" "}
          <span className="whitespace-nowrap text-sm font-normal text-fog">{item.item_code}</span>
        </Link>
        <span className="font-semibold">{money(item.value_at_cost)} at cost</span>
      </div>
      <p className="mt-0.5">
        {qty(item.qty, uom)}
        {item.qty_at_harbor > 0 && (
          <>
            , {qty(item.qty_at_harbor, uom)} of it at <Term explain="harbor">Harbor</Term>
          </>
        )}
      </p>
      <details className="mt-1">
        <summary className="cursor-pointer text-sm text-fog">
          {lots.length === 1 ? "1 lot" : `${lots.length} lots`}
        </summary>
        <ul className="mt-2 space-y-2">
          {lots.map((lot) => (
            <li
              key={`${lot.lot_no}-${lot.location_code}`}
              className="rounded-md bg-ice px-3 py-2 text-sm"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">Lot {lot.lot_no}</span>
                <span>{lot.location_name}</span>
                {lot.at_harbor && <HarborBadge />}
              </div>
              <p className="mt-1">
                {qty(lot.qty, uom)}
                {lot.value_at_cost !== null && `, ${money(lot.value_at_cost)} at cost`}
                {lot.expiry_date &&
                  `, expires ${formatShortDate(lot.expiry_date)} ${lot.expiry_date.slice(0, 4)}`}
              </p>
              <div className="mt-1 flex flex-wrap gap-1">
                {lot.tags.map((t) => (
                  <TagChip key={t} tag={t} />
                ))}
              </div>
            </li>
          ))}
        </ul>
      </details>
    </li>
  );
}

export function StuckList({ items }: { items: StuckItem[] }) {
  if (items.length === 0) return <p className="text-fog">Nothing is stuck right now.</p>;
  return (
    <div className="space-y-5">
      {TAG_ORDER.map((tag) => {
        const group = items.filter((i) => i.primary_tag === tag);
        if (group.length === 0) return null;
        const total = group.reduce((sum, i) => sum + i.value_at_cost, 0);
        return (
          <section key={tag} aria-label={TAG_LABEL[tag]}>
            <div className="flex items-center justify-between gap-2 border-b border-rope pb-1">
              <TagChip tag={tag} />
              <span className="text-sm text-fog">{money(total)} at cost</span>
            </div>
            <ul className="divide-y divide-rope">
              {group.map((item) => (
                <StuckRow key={item.item_code} item={item} />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
