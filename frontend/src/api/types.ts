/**
 * TypeScript mirrors of the API's shapes (backend/app/api/v1/schemas.py), field for field.
 *
 * Keep these in sync by hand: when a field is added to a Pydantic model, add it here too.
 * The strict TypeScript build then flags every component that needs to handle it.
 * Dates are "YYYY-MM-DD" strings (business dates); timestamps are ISO strings (UTC).
 */

export type Status =
  | "OUT_OF_STOCK"
  | "TOO_LATE"
  | "OVERDUE"
  | "ORDER_THIS_WEEK"
  | "ORDER_SOON"
  | "OK"
  | "NO_RECENT_SALES"
  | "NOT_PLANNED";

export type StuckTag =
  "EXPIRED" | "STOPPED_SELLING" | "INSIDE_SIX_MONTHS" | "LONG_AT_HARBOR" | "OVERSTOCK";

/** GET /health */
export interface HealthResponse {
  status: "ok" | "degraded";
  db: "ok" | "down" | "not_configured";
  schema_ready: boolean;
  /** Today in Boston (ADR-034), from the server, never the browser clock. Ignores the "view as of" date. */
  as_of: string;
  /** The date of BlueTide's stock count in the latest load (null before the first load). */
  snapshot_date?: string | null;
  /** The day after that count: where the numbers start, and the earliest day you can view. */
  data_date?: string | null;
  /** Days from the count to today. */
  days_since_count?: number | null;
  /** The count is "old" after this many days (yellow banner) and "very old" after the second (red). */
  stale_after_days?: number | null;
  very_stale_after_days?: number | null;
  last_load_at: string | null;
  version: string;
}

export interface HandledNote {
  id: number;
  item_code: string;
  qty: number | null;
  eta: string | null;
  note: string | null;
  created_at: string;
  created_by: string;
  counts_as_incoming: boolean;
  /** Its arrival date is before today: not counted, and the item is back in its status group (A25). */
  date_passed?: boolean;
  bluetide_now_shows: string[];
}

export interface Runway {
  stock_lasts_days: number | null;
  lead_time_days: number;
  cushion_days: number;
  horizon_days: number;
}

export interface ItemCard {
  item_code: string;
  description: string;
  category: string;
  sell_uom: string;
  vendor_code: string;
  vendor_name: string;
  country: string | null;
  lifecycle_status: string;
  status: Status;
  run_out_date: string | null;
  order_by_date: string | null;
  new_order_arrival: string;
  back_in_stock_date: string | null;
  lead_time_days: number;
  cushion_days: number;
  order_at_least: number;
  short_qty: number;
  /** What BlueTide's count said you can sell. */
  sellable: number;
  /** The estimate for today: the count minus expected sales and scheduled orders since (ADR-034). */
  sellable_now: number;
  /** The count's date, when it's older than the day shown (null when the count is from last night). */
  count_date: string | null;
  /** Overdue: days since the order-by date. */
  days_overdue: number | null;
  on_hold: number;
  promised_to_customers: number;
  on_the_way: number;
  late_qty: number;
  weeks_of_cover: number | null;
  covered_only_by_late_po: boolean;
  /** Only for items a late PO alone would cover: what to do, in one sentence (ADR-033). */
  instruction?: string | null;
  if_late_arrive_status: Status | null;
  if_late_arrive_order_at_least: number | null;
  handled_note: HandledNote | null;
  runway: Runway;
}

export interface LateLine {
  item_code: string;
  description: string;
  sell_uom: string;
  po_no: string | null;
  line_no: number | null;
  reference: string;
  qty: number;
  bluetide_date: string | null;
  flags: string[];
}

export interface OnHold {
  item_code: string;
  description: string;
  sell_uom: string;
  qty: number;
}

export interface StuckLot {
  lot_no: string;
  location_code: string;
  location_name: string;
  qty: number;
  expiry_date: string | null;
  value_at_cost: number | null;
  tags: StuckTag[];
  primary_tag: StuckTag;
  at_harbor: boolean;
}

export interface StuckItem {
  item_code: string;
  description: string;
  sell_uom: string;
  primary_tag: StuckTag;
  qty: number;
  qty_at_harbor: number;
  value_at_cost: number;
  lots: StuckLot[];
}

export type ByUnit = Record<string, number>;

export interface TrustStrip {
  on_hold: ByUnit;
  damaged: ByUnit;
  expired: ByUnit;
  old_zz_stock: ByUnit;
  late_po_qty: ByUnit;
}

export interface Summary {
  out_of_stock: number;
  too_late: number;
  overdue: number;
  order_this_week: number;
  order_soon: number;
  handled: number;
  fine: number;
  covered_only_by_late_po: number;
  inside_six_months_value: number;
  inside_six_months_value_at_harbor: number;
  stuck_value: number;
  sentences: string[];
}

/** GET /dashboard */
export interface Dashboard {
  /** The day these numbers are for: today in Boston, or the "view as of" date. */
  as_of: string;
  data_snapshot_date: string | null;
  /** The day after the count: the numbers between it and as_of are estimated. */
  data_date: string | null;
  days_since_count: number | null;
  last_load_at: string | null;
  summary: Summary;
  order_items: ItemCard[];
  handled_items: ItemCard[];
  fine_items: ItemCard[];
  late_inventory: { late_pos: LateLine[]; on_hold: OnHold[] };
  stuck_items: StuckItem[];
  trust_strip: TrustStrip;
}

export interface VendorTerms {
  vendor_code: string;
  vendor_name: string;
  country: string | null;
  lead_time_days: number;
  lead_time_source: string;
  lead_time_days_bluetide: number | null;
  cushion_days: number;
  order_cycle_days: number;
}

export interface Lot {
  lot_no: string;
  location_code: string;
  location_name: string;
  qty: number | null;
  qty_source: number;
  uom_source: string;
  pack_date: string | null;
  expiry_date: string | null;
  received_date: string | null;
  unit_cost: number | null;
  value_at_cost: number | null;
  counted: boolean;
  reason: string;
  stuck_tags: StuckTag[];
}

export interface Promised {
  order_no: string;
  customer_name: string;
  ship_date: string | null;
  qty: number;
}

export interface Incoming {
  source: string;
  reference: string;
  po_no: string | null;
  line_no: number | null;
  qty: number;
  eta: string | null;
  eta_source: string;
  bluetide_date: string | null;
  is_late: boolean;
  flags: string[];
}

export interface Demand {
  selling_per_week: number;
  measured_over_days: number;
  season_now: number;
  normal_per_week: number;
  season_by_month: Record<string, number>;
  monthly_history: Record<string, number>;
}

export interface Point {
  day: string;
  stock: number;
}

export interface ItemSettings {
  item_code: string;
  lifecycle_override: string | null;
  safety_days_override: number | null;
  cases_per_pallet?: number | null;
  note: string | null;
  updated_at: string | null;
  updated_by: string | null;
}

export interface BreakdownRow {
  key: string;
  label: string;
  qty: number | null;
  unit: string | null;
  date: string | null;
  detail: string | null;
  /** The item-page table that holds the source rows: "#have", "#promised", "#on-the-way", ... */
  link: string | null;
}

export interface SeasonMarker {
  label: string;
  start: string;
  end: string;
}

/** GET /items/{code} */
export interface ItemDetail {
  as_of: string;
  card: ItemCard;
  lifecycle_reason: string;
  vendor: VendorTerms;
  sellable_by_location: Record<string, number>;
  damaged: number;
  expired: number;
  lots: Lot[];
  promised: Promised[];
  incoming: Incoming[];
  late: Incoming[];
  demand: Demand;
  projection: Point[];
  if_late_arrive_projection: Point[] | null;
  /** The numbers-only "why" (ADR-033): one row per number the engine used. */
  breakdown: BreakdownRow[];
  settings: ItemSettings | null;
  aliases: string[];
  handled_notes: HandledNote[];
  season_markers: SeasonMarker[];
}

export interface Vendor {
  vendor_code: string;
  name: string;
  country: string | null;
  lead_time_days_bluetide: number | null;
  lead_time_bluetide_text: string | null;
  lead_time_days: number;
  cushion_days: number;
  order_cycle_days: number;
  source: string;
  note: string | null;
  updated_at: string | null;
  updated_by: string | null;
}

export interface IssueRule {
  rule_code: string;
  severity: string;
  action: string;
  count: number;
  example: string;
}

export interface IssueTrap {
  trap_id: string | null;
  title: string;
  count: number;
  rules: IssueRule[];
}

export interface DataIssueSummary {
  load_run_id: number | null;
  total: number;
  by_trap: IssueTrap[];
}

export interface DataIssue {
  id: number;
  source_file: string;
  source_line_number: number | null;
  trap_id: string | null;
  rule_code: string;
  severity: string;
  action: string;
  item_code: string | null;
  field: string | null;
  original_value: string | null;
  new_value: string | null;
  message: string;
  raw: Record<string, string> | null;
}

export interface DataIssuePage {
  total: number;
  limit: number;
  offset: number;
  items: DataIssue[];
}

export interface AuditEntry {
  id: number;
  occurred_at: string;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  request_id: string | null;
}

export interface EventEntry {
  id: number;
  occurred_at: string;
  level: string;
  source: string;
  event: string;
  request_id: string | null;
  details: Record<string, unknown> | null;
}

export interface LoadRun {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  as_of_date: string;
  git_sha: string | null;
  files: { name: string; sha256: string; rows: number }[];
  summary: Record<string, unknown>;
}

export interface Rule {
  name: string;
  value: unknown;
  unit: string;
  doc: string;
  source: string;
}

/** The error envelope every failed API call returns. */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    request_id: string | null;
    details?: { field: string; problem: string }[];
  };
}

// ---- On the way (ADR-032): mirrors OnTheWayLineOut in schemas.py ------------------------------

/** GET /purchase-orders: one open BlueTide PO line, as the plan counts it. */
export interface OnTheWayLine {
  po_no: string;
  line_no: number;
  item_code: string;
  description: string;
  sell_uom: string;
  vendor_name: string;
  qty: number;
  /** Our arrival date; null = late, not counted until Dana sets one. */
  eta: string | null;
  eta_source: string;
  bluetide_date: string | null;
  is_late: boolean;
  flags: string[];
}

// ---- Weekly uploads of BlueTide's files (ADR-029) ---------------------------------------------

export interface ImportSlot {
  slot: string;
  label: string;
  expected_name: string;
}

export interface ImportFile {
  slot: string;
  file_name: string;
  rows: number;
  size_bytes: number;
  sha256: string;
}

export interface ImportReport {
  kind: "bluetide";
  files: {
    slot: string;
    label: string;
    file_name: string;
    rows: number;
    source?: "uploaded" | "last load";
    previous_rows?: number | null;
    same_as_last?: boolean;
  }[];
  blockers: string[];
  warnings: string[];
  changes?: { what: string; now?: number; after?: number; count?: number }[];
  snapshot_date?: string;
  current_snapshot_date?: string | null;
  /** Today in Boston when the check ran (ADR-034). */
  today?: string;
  /** Where the numbers would start once loaded: the day after these files' stock count. */
  data_date?: string;
  /** Days from these files' count to today. */
  count_age_days?: number;
  /** How this week's sales file merged with the stored history (sales accumulate). */
  sales?: {
    new: number;
    updated: number;
    unchanged: number;
    kept: number;
    months_of_history: number;
  };
  notes?: { total: number; by_problem: { trap_id: string; title: string; count: number }[] };
  loaded?: Record<string, unknown>;
}

/** GET /imports, /imports/{id} */
export interface Import {
  id: number;
  kind: "bluetide";
  status: "open" | "checked" | "loaded" | "failed" | "discarded";
  created_at: string;
  created_by: string;
  slots: ImportSlot[];
  files: ImportFile[];
  report: ImportReport | null;
  confirm_code: string | null;
  load_run_id: number | null;
  error: string | null;
}

// ---- Harbor storage (P1 #1; ADR-031): mirrors HarborOut in schemas.py ----------------------

export interface HarborLot {
  lot_no: string;
  location_name: string;
  cases: number;
  expiry_date: string | null;
}

export interface HarborItem {
  item_code: string;
  description: string;
  sell_uom: string;
  cases: number;
  lots: HarborLot[];
  cases_per_pallet: number | null;
  pallets: number | null;
  cost_per_month: number | null;
  /** Why its Harbor stock is on the stuck list, if it is. */
  stuck_tag: StuckTag | null;
  /** Sold by the pound with no pounds per case: these lots can't be put on pallets. */
  unconverted_lots: number;
}

export interface HarborTotals {
  items: number;
  cases: number;
  priced_items: number;
  pallets: number;
  cost_per_month: number;
}

export interface HarborRow {
  id: number;
  kind: "at_harbor" | "what_if";
  as_of_date: string;
  item_code: string;
  description: string;
  cases: number;
  lots: number;
  cases_per_pallet: number;
  pallets: number;
  rate_per_pallet_month: number;
  cost_per_month: number;
  created_at: string;
  created_by: string;
}

export interface Harbor {
  as_of: string;
  rate_per_pallet_month: number;
  cases_per_pallet_max: number;
  location_names: string[];
  items: HarborItem[];
  totals: HarborTotals;
  saved: HarborRow[];
}
