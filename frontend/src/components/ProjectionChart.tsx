/**
 * The runway, enlarged (BUILD_PROMPT §9.1, §9.3): stock Dana can sell, day by day for 26 weeks.
 *   - solid line + light wash: the plan with confirmed supply only
 *   - dashed line: "if the late PO arrives today" (only when there is a late PO; ADR-021)
 *   - red band: out of stock
 *   - vertical lines: when a new order placed today lands, and the run-out point
 *   - dots: dated arrivals that are counted
 *   - grey bands: busy seasons (Christmas, Lent) from business_rules.season_markers
 * The engine's day-by-day balance goes below zero once demand can't be met (that's how it measures
 * the shortage). Stock on a shelf can't be negative, so the chart stops at zero and shades those days
 * "Out of stock"; the shortage itself is in the "Why" steps.
 * Hover shows the numbers for that day; the same numbers are in the week-by-week table below the
 * chart, so nothing depends on hovering.
 * Fed by: ItemDetail.projection, if_late_arrive_projection, incoming, season_markers, card.
 */
import { format } from "date-fns";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ItemDetail, Point } from "../api/types";
import { formatShortDate, parseBusinessDate } from "../lib/dates";
import { qty } from "../lib/format";

// Chart colours come from the design tokens (styles/index.css), so the chart matches the page.
const INK = "var(--color-ink)";
const FOG = "var(--color-fog)";
const ROPE = "var(--color-rope)";
const RED = "var(--color-red)";
const RED_TINT = "var(--color-red-tint)";
const SURFACE = "var(--color-hull)";

const OUT = 0.5; // under half a case (or pound) left counts as out of stock

interface Row {
  day: string;
  stock: number;
  ifLate?: number;
}

const shelf = (v: number) => Math.max(0, v);

/** Runs of consecutive days with nothing left to sell, as [first day, last day]. */
function outOfStockRuns(points: Point[]): [string, string][] {
  const runs: [string, string][] = [];
  let start: string | null = null;
  let prev: string | null = null;
  for (const p of points) {
    if (p.stock < OUT) {
      start ??= p.day;
    } else if (start && prev) {
      runs.push([start, prev]);
      start = null;
    }
    prev = p.day;
  }
  if (start && prev) runs.push([start, prev]);
  return runs;
}

function stockText(value: number | undefined, uom: string): string {
  if (value === undefined) return "–";
  return value < OUT ? "Out of stock" : qty(value, uom);
}

function ChartTooltip({
  active,
  label,
  payload,
  uom,
}: {
  active?: boolean;
  label?: string;
  payload?: { dataKey?: string | number; value?: number }[];
  uom: string;
}) {
  if (!active || !label || !payload?.length) return null;
  const stock = payload.find((p) => p.dataKey === "stock")?.value;
  const ifLate = payload.find((p) => p.dataKey === "ifLate")?.value;
  return (
    <div className="rounded-md border border-rope bg-hull px-3 py-2 text-sm shadow-md">
      <p className="text-fog">{formatShortDate(label)}</p>
      {stock !== undefined && (
        <p>
          <span className="font-semibold">{stockText(stock, uom)}</span>{" "}
          {stock >= OUT && <span className="text-fog">you can sell</span>}
        </p>
      )}
      {ifLate !== undefined && (
        <p>
          <span className="font-semibold">{stockText(ifLate, uom)}</span>{" "}
          <span className="text-fog">if the late PO arrives</span>
        </p>
      )}
    </div>
  );
}

export function ProjectionChart({ detail }: { detail: ItemDetail }) {
  const { card, projection, if_late_arrive_projection: ifLate } = detail;
  const uom = card.sell_uom;
  const lateByDay = new Map((ifLate ?? []).map((p) => [p.day, shelf(p.stock)]));
  const rows: Row[] = projection.map((p) => ({
    day: p.day,
    stock: shelf(p.stock),
    ...(ifLate ? { ifLate: lateByDay.get(p.day) } : {}),
  }));
  const first = rows[0]?.day;
  const last = rows[rows.length - 1]?.day;
  if (!first || !last) return <p className="text-fog">No projection for this item.</p>;

  const inRange = (day: string | null) => (day && day >= first && day <= last ? day : null);
  const landing = inRange(card.new_order_arrival);
  const runOut = inRange(card.run_out_date);
  // Put the run-out label on whichever side of its line has room.
  const runOutEarly = runOut !== null && rows.findIndex((r) => r.day === runOut) < rows.length / 2;
  const stockByDay = new Map(rows.map((r) => [r.day, r.stock]));
  const arrivals = detail.incoming.filter((i) => inRange(i.eta));
  const outRuns = outOfStockRuns(projection);
  const seasons = detail.season_markers
    .map((s) => ({
      label: s.label,
      x1: s.start < first ? first : s.start,
      x2: s.end > last ? last : s.end,
    }))
    .filter((s) => s.x1 <= s.x2 && s.x1 <= last && s.x2 >= first);
  const monthTicks = rows.filter((r) => r.day.endsWith("-01")).map((r) => r.day);

  return (
    <figure>
      <figcaption className="sr-only">
        Stock you can sell over the next {rows.length} days. The table below the chart has the same
        numbers.
      </figcaption>
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-fog" aria-hidden="true">
        <span className="inline-flex items-center gap-2">
          <svg width="20" height="4">
            <line x1="0" y1="2" x2="20" y2="2" stroke={INK} strokeWidth="2" />
          </svg>
          Stock you can sell
        </span>
        {ifLate && (
          <span className="inline-flex items-center gap-2">
            <svg width="20" height="4">
              <line
                x1="0"
                y1="2"
                x2="20"
                y2="2"
                stroke={FOG}
                strokeWidth="2"
                strokeDasharray="4 3"
              />
            </svg>
            If the late PO arrives today
          </span>
        )}
        {outRuns.length > 0 && (
          <span className="inline-flex items-center gap-2">
            <span className="inline-block h-3 w-4 rounded-sm bg-red-tint ring-1 ring-red/40" />
            Out of stock
          </span>
        )}
        <span className="inline-flex items-center gap-2">
          <span className="inline-block h-3 w-4 rounded-sm bg-rope/60" />
          Busy season
        </span>
      </div>
      <div className="mt-2 h-72 w-full sm:h-80" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 24, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid vertical={false} stroke={ROPE} strokeWidth={1} />
            {outRuns.map(([x1, x2]) => (
              <ReferenceArea
                key={x1}
                x1={x1}
                x2={x2}
                fill={RED_TINT}
                fillOpacity={0.9}
                stroke="none"
                ifOverflow="hidden"
              />
            ))}
            {seasons.map((s) =>
              s.x1 === s.x2 ? (
                <ReferenceLine
                  key={s.label}
                  x={s.x1}
                  stroke={ROPE}
                  strokeWidth={6}
                  label={{ value: s.label, position: "insideTopLeft", fill: FOG, fontSize: 12 }}
                />
              ) : (
                <ReferenceArea
                  key={s.label}
                  x1={s.x1}
                  x2={s.x2}
                  fill={ROPE}
                  fillOpacity={0.6}
                  stroke="none"
                  ifOverflow="hidden"
                  label={{ value: s.label, position: "insideTop", fill: FOG, fontSize: 12 }}
                />
              ),
            )}
            <XAxis
              dataKey="day"
              ticks={monthTicks}
              tickFormatter={(d: string) => format(parseBusinessDate(d), "MMM")}
              tick={{ fill: FOG, fontSize: 12 }}
              axisLine={{ stroke: ROPE }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: FOG, fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              width={48}
              domain={[0, "auto"]}
              tickFormatter={(v: number) => Math.round(v).toLocaleString("en-US")}
            />
            <Tooltip
              content={<ChartTooltip uom={uom} />}
              cursor={{ stroke: FOG, strokeWidth: 1 }}
              isAnimationActive={false}
            />
            <Area
              type="linear"
              dataKey="stock"
              stroke="none"
              fill={INK}
              fillOpacity={0.08}
              isAnimationActive={false}
              activeDot={false}
            />
            {ifLate && (
              <Line
                type="linear"
                dataKey="ifLate"
                stroke={FOG}
                strokeWidth={2}
                strokeDasharray="6 4"
                dot={false}
                activeDot={{ r: 4, stroke: SURFACE, strokeWidth: 2 }}
                isAnimationActive={false}
              />
            )}
            <Line
              type="linear"
              dataKey="stock"
              stroke={INK}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
              dot={false}
              activeDot={{ r: 5, stroke: SURFACE, strokeWidth: 2 }}
              isAnimationActive={false}
            />
            {landing && (
              <ReferenceLine
                x={landing}
                stroke={INK}
                strokeWidth={1}
                label={{
                  value: `New order lands ${formatShortDate(landing)}`,
                  position: "top",
                  fill: INK,
                  fontSize: 12,
                }}
              />
            )}
            {runOut && (
              <ReferenceLine
                x={runOut}
                stroke={RED}
                strokeWidth={1}
                label={{
                  value: `Runs out ${formatShortDate(runOut)}`,
                  position: runOutEarly ? "insideTopLeft" : "insideTopRight",
                  offset: 22, // below the season labels
                  fill: INK,
                  fontSize: 12,
                }}
              />
            )}
            {arrivals.map((a) => (
              <ReferenceDot
                key={a.reference}
                x={a.eta ?? undefined}
                y={a.eta ? (stockByDay.get(a.eta) ?? 0) : 0}
                r={5}
                fill={INK}
                stroke={SURFACE}
                strokeWidth={2}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}

/** The same projection as a week-by-week table (the chart's accessible twin). */
export function ProjectionTable({ detail }: { detail: ItemDetail }) {
  const uom = detail.card.sell_uom;
  const lateByDay = new Map((detail.if_late_arrive_projection ?? []).map((p) => [p.day, p.stock]));
  const weekly = detail.projection.filter((_, i) => i % 7 === 0);
  return (
    <details className="mt-3">
      <summary className="cursor-pointer text-sm font-semibold text-ink">
        See the numbers week by week
      </summary>
      <div className="mt-2 max-h-80 overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-hull text-left text-fog">
            <tr>
              <th className="py-1 pr-4 font-semibold">Week of</th>
              <th className="py-1 pr-4 text-right font-semibold">You can sell</th>
              {detail.if_late_arrive_projection && (
                <th className="py-1 text-right font-semibold">If the late PO arrives</th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-rope">
            {weekly.map((p) => (
              <tr key={p.day}>
                <td className="py-1 pr-4">{formatShortDate(p.day)}</td>
                <td className="py-1 pr-4 text-right">{stockText(p.stock, uom)}</td>
                {detail.if_late_arrive_projection && (
                  <td className="py-1 text-right">{stockText(lateByDay.get(p.day), uom)}</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
