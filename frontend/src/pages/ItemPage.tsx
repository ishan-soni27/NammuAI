/**
 * Item page (BUILD_PROMPT §9.3): why the Monday screen says what it says, down to the source rows.
 *   1. header: name, code, supplier, status, "Mark as handled"
 *   2. "Why" as numbers: one row per number the engine used, each linking to its source table
 *      (ADR-033), with the one instruction for items only a late PO would cover
 *   3. the projection chart (the runway, enlarged) and its week-by-week table
 *   4. tables: lots (counted or not, and why), promised to customers, on the way (with "Set real
 *      date"), late POs, sales by month
 *   5. item settings: still selling?, a different cushion for this item
 * Fed by: GET /items/{code}.
 */
import { format } from "date-fns";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useParams } from "react-router";
import { useItem, useUpdateItemSettings } from "../api/queries";
import type { Incoming, ItemDetail } from "../api/types";
import { HandledNoteView } from "../components/HandledNoteView";
import { MarkHandledDialog } from "../components/MarkHandledDialog";
import { ProjectionChart, ProjectionTable } from "../components/ProjectionChart";
import { QueryState } from "../components/QueryState";
import { SetPoDate } from "../components/SetPoDate";
import { StatusChip, TagChip } from "../components/StatusChip";
import { Term } from "../components/Term";
import { formatShortDate, formatTimestamp, parseBusinessDate } from "../lib/dates";
import { duration, money, qty, unitWord, weeks } from "../lib/format";
import { itemName } from "../lib/names";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** The numbers-only "why" (ADR-033): label, number, date and a short note; each label links to the
 * table below that holds its source rows. Rows come computed from the engine, so they always agree. */
function Breakdown({ detail }: { detail: ItemDetail }) {
  const instruction = detail.card.instruction;
  return (
    <div className="space-y-3">
      {instruction && (
        <p className="rounded-md bg-yellow-tint px-3 py-2 text-sm font-semibold">{instruction}</p>
      )}
      <table className="w-full text-sm">
        <tbody className="divide-y divide-rope">
          {detail.breakdown.map((row, i) => (
            <tr key={`${row.key}-${i}`} className="align-top">
              <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                {row.link ? (
                  <a href={row.link} className="underline-offset-2 hover:underline">
                    {row.label}
                  </a>
                ) : (
                  row.label
                )}
                {row.detail && <span className="block text-xs text-fog">{row.detail}</span>}
              </th>
              <td className="whitespace-nowrap py-1.5 pr-3 text-right font-semibold tabular-nums">
                {row.qty !== null
                  ? `${row.qty.toLocaleString("en-US", { maximumFractionDigits: 1 })} ${row.unit ?? ""}`
                  : ""}
              </td>
              <td className="whitespace-nowrap py-1.5 text-right tabular-nums">
                {row.date ? formatShortDate(row.date) : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Card({ title, children, id }: { title: ReactNode; children: ReactNode; id?: string }) {
  return (
    <section id={id} className="min-w-0 rounded-lg border border-rope bg-hull px-5 py-4">
      <h2 className="text-lg font-bold">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Table({ head, children }: { head: ReactNode[]; children: ReactNode }) {
  return (
    <div className="relative -mx-1 overflow-x-auto">
      <table className={`w-full text-sm ${head.length > 3 ? "min-w-[32rem]" : ""}`}>
        <thead className="text-left text-fog">
          <tr>
            {head.map((h, i) => (
              <th key={i} className="px-1 py-1 font-semibold">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-rope">{children}</tbody>
      </table>
    </div>
  );
}

const td = "px-1 py-1.5 align-top";

function arrivalCell(line: Incoming) {
  const corrected = line.bluetide_date && line.eta && line.bluetide_date !== line.eta;
  return (
    <>
      {line.eta ? formatShortDate(line.eta) : "No date"}
      {corrected && line.bluetide_date && (
        <span className="ml-2 text-fog">
          BlueTide said <del>{formatShortDate(line.bluetide_date)}</del>
        </span>
      )}
      <div className="text-fog">{line.eta_source}</div>
    </>
  );
}

function SettingsForm({ detail }: { detail: ItemDetail }) {
  const save = useUpdateItemSettings();
  const s = detail.settings;
  const [lifecycle, setLifecycle] = useState(s?.lifecycle_override ?? "");
  const [cushion, setCushion] = useState(s?.safety_days_override?.toString() ?? "");
  const [note, setNote] = useState(s?.note ?? "");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate({
      code: detail.card.item_code,
      lifecycle_override: lifecycle || null,
      safety_days_override: cushion ? Number(cushion) : null,
      note: note.trim() || null,
    });
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <p>
        BlueTide and the sales history say:{" "}
        <span className="font-semibold">{detail.lifecycle_reason}</span>
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="text-sm font-semibold">Still selling?</span>
          <select
            value={lifecycle}
            onChange={(e) => setLifecycle(e.target.value)}
            className="mt-1 w-full rounded-md border border-rope bg-hull px-3 py-2"
          >
            <option value="">Decide from sales (automatic)</option>
            <option value="active">Yes, still selling: plan it</option>
            <option value="dormant">Not right now</option>
            <option value="discontinued">No, stopped for good</option>
          </select>
        </label>
        <label className="block">
          <span className="text-sm font-semibold">
            <Term explain="cushion">Cushion</Term> for this item, in days (blank uses the supplier's{" "}
            {weeks(detail.vendor.cushion_days)})
          </span>
          <input
            type="number"
            inputMode="numeric"
            min={1}
            max={365}
            value={cushion}
            onChange={(e) => setCushion(e.target.value)}
            className="mt-1 w-full rounded-md border border-rope px-3 py-2"
          />
        </label>
      </div>
      <label className="block">
        <span className="text-sm font-semibold">Note (optional)</span>
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={500}
          className="mt-1 w-full rounded-md border border-rope px-3 py-2"
        />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={save.isPending}
          className="rounded-md bg-ink px-4 py-2 font-semibold text-hull disabled:opacity-60"
        >
          {save.isPending ? "Saving…" : "Save item settings"}
        </button>
        {s?.updated_at && (
          <span className="text-sm text-fog">
            Last changed by {s.updated_by ?? "someone"} on {formatTimestamp(s.updated_at)}
          </span>
        )}
      </div>
    </form>
  );
}

function Item({ detail }: { detail: ItemDetail }) {
  const [handling, setHandling] = useState(false);
  const { card, vendor } = detail;
  const uom = card.sell_uom;
  const asOf = detail.as_of;
  const months = Object.entries(detail.demand.monthly_history);

  return (
    <div className="space-y-5">
      <Link to="/" className="text-sm font-semibold text-ink underline underline-offset-2">
        Back to Monday
      </Link>

      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">
            {itemName(card.description)}{" "}
            <span className="text-base font-normal text-fog">{card.item_code}</span>
          </h1>
          <p className="mt-1 text-fog">
            {vendor.vendor_name}
            {vendor.country ? `, ${vendor.country}` : ""}. {weeks(vendor.lead_time_days)}{" "}
            <Term explain="arrive">to arrive</Term> (set by {vendor.lead_time_source}
            {vendor.lead_time_days_bluetide !== null &&
            vendor.lead_time_days_bluetide !== vendor.lead_time_days
              ? `; BlueTide says ${weeks(vendor.lead_time_days_bluetide)}`
              : ""}
            ), plus {weeks(vendor.cushion_days)} <Term explain="cushion">cushion</Term>.
          </p>
          {detail.aliases.length > 0 && (
            <p className="mt-1 text-sm text-fog">
              Also written in BlueTide as: {detail.aliases.join(", ")}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <StatusChip status={card.handled_note ? "HANDLED" : card.status} />
          <button
            type="button"
            onClick={() => setHandling(true)}
            className="rounded-md border border-ink px-3 py-1.5 font-semibold hover:bg-ice"
          >
            Mark as handled
          </button>
        </div>
      </header>
      {handling && (
        <MarkHandledDialog card={card} asOf={asOf} open onClose={() => setHandling(false)} />
      )}

      {detail.handled_notes.length > 0 && (
        <div className="space-y-2">
          {detail.handled_notes.map((n) => (
            <HandledNoteView key={n.id} note={n} uom={uom} />
          ))}
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[2fr_3fr]">
        <Card title="Why">
          <Breakdown detail={detail} />
        </Card>
        <Card
          id="chart"
          title={`Stock over the next ${duration(card.runway.horizon_days)}, in ${unitWord(uom)}`}
        >
          <ProjectionChart detail={detail} />
          <ProjectionTable detail={detail} />
        </Card>
      </div>

      <Card title="What you have" id="have">
        <p className="mb-2 text-fog">
          {card.count_date ? (
            <>
              BlueTide's count of {formatShortDate(card.count_date)}: {qty(card.sellable, uom)} you
              can sell. About {qty(card.sellable_now, uom)} today (estimated: see Why).
            </>
          ) : (
            <>You can sell {qty(card.sellable, uom)}.</>
          )}
          {card.on_hold > 0 && <> {qty(card.on_hold, uom)} on hold.</>}
          {detail.damaged > 0 && <> {qty(detail.damaged, uom)} damaged.</>}
          {detail.expired > 0 && <> {qty(detail.expired, uom)} expired.</>} Only counted lots go
          into the plan.
        </p>
        {detail.lots.length === 0 ? (
          <p className="text-fog">No stock in any building.</p>
        ) : (
          <Table head={["Lot", "Where", "Quantity", "Expires", "Value at cost", "Counted?"]}>
            {detail.lots.map((lot) => (
              <tr
                key={`${lot.lot_no}-${lot.location_code}`}
                className={lot.counted ? "" : "text-fog"}
              >
                <td className={td}>{lot.lot_no}</td>
                <td className={td}>{lot.location_name}</td>
                <td className={td}>
                  {qty(lot.qty, uom)}
                  {lot.uom_source.toUpperCase() !== uom.toUpperCase() && (
                    <div className="text-fog">
                      {qty(lot.qty_source, lot.uom_source)} in BlueTide
                    </div>
                  )}
                </td>
                <td className={td}>
                  {lot.expiry_date
                    ? format(parseBusinessDate(lot.expiry_date), "MMM d, yyyy")
                    : "–"}
                </td>
                <td className={td}>{money(lot.value_at_cost)}</td>
                <td className={td}>
                  {lot.counted ? "Yes" : `No: ${lot.reason}`}
                  {lot.stuck_tags.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {lot.stuck_tags.map((t) => (
                        <TagChip key={t} tag={t} />
                      ))}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card id="promised" title={<Term explain="promised">Promised to customers</Term>}>
          {detail.promised.length === 0 ? (
            <p className="text-fog">No open customer orders.</p>
          ) : (
            <Table head={["Order", "Customer", "Ships", "Quantity"]}>
              {detail.promised.map((p) => (
                <tr key={`${p.order_no}-${p.ship_date}`}>
                  <td className={td}>{p.order_no}</td>
                  <td className={td}>{p.customer_name}</td>
                  <td className={td}>{p.ship_date ? formatShortDate(p.ship_date) : "No date"}</td>
                  <td className={td}>{qty(p.qty, uom)}</td>
                </tr>
              ))}
            </Table>
          )}
        </Card>

        <Card id="on-the-way" title="On the way">
          {detail.incoming.length === 0 && detail.late.length === 0 ? (
            <p className="text-fog">Nothing on order.</p>
          ) : (
            <div className="space-y-4">
              {detail.incoming.length > 0 && (
                <Table head={["Order", "Quantity", "Arrives", ""]}>
                  {detail.incoming.map((line) => (
                    <tr key={line.reference}>
                      <td className={td}>{line.reference}</td>
                      <td className={td}>{qty(line.qty, uom)}</td>
                      <td className={td}>{arrivalCell(line)}</td>
                      <td className={td}>
                        {line.po_no && line.line_no !== null && (
                          <SetPoDate
                            poNo={line.po_no}
                            lineNo={line.line_no}
                            asOf={asOf}
                            label="Change date"
                            current={line.eta_source.startsWith("Set by") ? line.eta : null}
                          />
                        )}
                      </td>
                    </tr>
                  ))}
                </Table>
              )}
              {detail.late.length > 0 && (
                <div id="late">
                  <h3 className="font-semibold text-red">
                    <Term explain="late">Late</Term>, not counted
                  </h3>
                  <ul className="mt-1 divide-y divide-rope">
                    {detail.late.map((line) => (
                      <li key={line.reference} className="py-2">
                        <p>
                          {line.reference}, {qty(line.qty, uom)}.
                          {line.bluetide_date &&
                            ` BlueTide said ${formatShortDate(line.bluetide_date)}.`}
                        </p>
                        {line.flags.length > 0 && (
                          <p className="text-sm text-fog">{line.flags.join(". ")}.</p>
                        )}
                        {line.po_no && line.line_no !== null && (
                          <div className="mt-1">
                            <SetPoDate poNo={line.po_no} lineNo={line.line_no} asOf={asOf} />
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>

      <Card id="demand" title="Sales by month">
        <p className="mb-2 text-fog">
          Selling about {qty(detail.demand.selling_per_week, uom)} a week over the last{" "}
          {Math.round(detail.demand.measured_over_days / 7)} weeks. The season row shows how each
          month usually sells compared with an average month for this kind of item.
        </p>
        {months.length === 0 ? (
          <p className="text-fog">No sales history.</p>
        ) : (
          <Table head={["Month", "Sold", "Season"]}>
            {months.map(([month, sold]) => {
              const m = Number(month.slice(5, 7));
              const season = detail.demand.season_by_month[String(m)];
              return (
                <tr key={month}>
                  <td className={td}>
                    {MONTHS[m - 1]} {month.slice(0, 4)}
                    {month === asOf.slice(0, 7) && <span className="text-fog"> (so far)</span>}
                  </td>
                  <td className={td}>{qty(sold, uom)}</td>
                  <td className={td}>{season !== undefined ? `${season.toFixed(1)}×` : "–"}</td>
                </tr>
              );
            })}
          </Table>
        )}
      </Card>

      <Card title="Item settings">
        <SettingsForm key={detail.settings?.updated_at ?? "none"} detail={detail} />
      </Card>
    </div>
  );
}

export function ItemPage() {
  const { code = "" } = useParams();
  const item = useItem(code);
  return (
    <QueryState query={item} label="Loading this item">
      {(detail) => <Item detail={detail} />}
    </QueryState>
  );
}
