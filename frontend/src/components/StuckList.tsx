/**
 * "What you're stuck with" (BUILD_PROMPT §6.9, §9.2): items grouped by their worst problem, in the
 * order Expired › Stopped selling › Inside six-month line › Long at Harbor › Overstock. Each item is a
 * dropdown row (name, quantity, value at cost); opening it lists the lots, Harbor lots (paying storage
 * every month) first and badged.
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
    <details className="group">
      <summary className="grid cursor-pointer list-none grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-x-3 px-4 py-3 hover:bg-ice">
        <span
          aria-hidden="true"
          className="text-lg leading-6 text-fog transition-transform group-open:rotate-90"
        >
          ›
        </span>
        <span className="min-w-0">
          <span className="block font-semibold">
            {itemName(item.description)}{" "}
            <span className="whitespace-nowrap text-sm font-normal text-fog">{item.item_code}</span>
          </span>
          <span className="block text-sm text-fog">
            {qty(item.qty, uom)}
            {item.qty_at_harbor > 0 && `, ${qty(item.qty_at_harbor, uom)} at Harbor`}
          </span>
        </span>
        <span className="whitespace-nowrap font-semibold">{money(item.value_at_cost)}</span>
      </summary>
      <div className="space-y-2 px-4 pb-4 pl-11">
        <ul className="space-y-2">
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
        <Link
          to={`/items/${encodeURIComponent(item.item_code)}`}
          className="inline-block py-1 font-semibold underline underline-offset-2"
        >
          See all the numbers
        </Link>
      </div>
    </details>
  );
}

export function StuckList({ items }: { items: StuckItem[] }) {
  if (items.length === 0) return <p className="px-4 py-3 text-fog">Nothing is stuck right now.</p>;
  return (
    <div>
      {TAG_ORDER.map((tag) => {
        const group = items.filter((i) => i.primary_tag === tag);
        if (group.length === 0) return null;
        const total = group.reduce((sum, i) => sum + i.value_at_cost, 0);
        return (
          <section key={tag} aria-label={TAG_LABEL[tag]}>
            <div className="flex items-center justify-between gap-2 border-y border-rope bg-ice/60 px-4 py-1.5">
              <TagChip tag={tag} />
              <span className="text-sm text-fog">
                {group.length} item{group.length === 1 ? "" : "s"}, {money(total)} at cost
              </span>
            </div>
            <div className="divide-y divide-rope">
              {group.map((item) => (
                <StuckRow key={item.item_code} item={item} />
              ))}
            </div>
          </section>
        );
      })}
      <p className="border-t border-rope px-4 py-2 text-sm text-fog">
        <Term explain="harbor">Harbor</Term> charges for storage every month. Inside the{" "}
        <Term explain="sixMonth">six-month line</Term>, customers won't take it.
      </p>
    </div>
  );
}
