/**
 * TypeScript mirrors of the API's shapes (backend/app/api/v1/schemas.py), field for field.
 *
 * Keep these in sync by hand: when a field is added to a Pydantic model, add it here too.
 * The strict TypeScript build then flags every component that needs to handle it.
 * Dates are "YYYY-MM-DD" strings (business dates); timestamps are ISO strings (UTC).
 */

export type Status =
  "TOO_LATE" | "ORDER_THIS_WEEK" | "ORDER_SOON" | "OK" | "NO_RECENT_SALES" | "NOT_PLANNED";

export type StuckTag =
  "EXPIRED" | "STOPPED_SELLING" | "INSIDE_SIX_MONTHS" | "LONG_AT_HARBOR" | "OVERSTOCK";

/** GET /health */
export interface HealthResponse {
  status: "ok" | "degraded";
  db: "ok" | "down" | "not_configured";
  schema_ready: boolean;
  /** Business "today". Always use this, never the browser clock. */
  as_of: string;
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
  sellable: number;
  on_hold: number;
  promised_to_customers: number;
  on_the_way: number;
  late_qty: number;
  weeks_of_cover: number | null;
  covered_only_by_late_po: boolean;
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
  too_late: number;
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
  as_of: string;
  data_snapshot_date: string | null;
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
  note: string | null;
  updated_at: string | null;
  updated_by: string | null;
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
  explanation: string[];
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
