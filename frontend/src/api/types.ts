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

// ---- Dana's own records (Phase 6, ADR-026/027) ---------------------------------------------

export type RecordSource = "app" | "bluetide" | "both";

/** GET /item-details */
export interface ItemDetails {
  item_code: string;
  description: string;
  category: string;
  sell_uom: "CS" | "LB";
  lb_per_case: number | null;
  vendor_code: string;
  status: "active" | "discontinued";
  source: RecordSource;
  note: string | null;
  updated_at: string | null;
  updated_by: string | null;
}

export interface Receipt {
  movement_id: number;
  received_on: string;
  qty: number;
  location_code: string;
  location_name: string;
  lot_no: string;
  expiry_date: string | null;
  unit_cost: number | null;
  created_by: string;
  added_to_stock: boolean;
  why_not: string | null;
}

export type POLineStatus = "open" | "shipped" | "received" | "cancelled" | "late";

export interface POLine {
  po_no: string;
  line_no: number;
  item_code: string;
  description: string;
  sell_uom: string;
  source: RecordSource;
  ordered: number;
  received: number;
  remaining: number;
  status: POLineStatus;
  counted: boolean;
  eta: string | null;
  eta_source: string | null;
  bluetide_date: string | null;
  shipped_on: string | null;
  container_no: string | null;
  cancel_reason: string | null;
  unit_cost: number | null;
  flags: string[];
  receipts: Receipt[];
}

export type POStatus = "open" | "shipped" | "late" | "partly_received" | "received" | "cancelled";

/** GET /purchase-orders */
export interface PurchaseOrder {
  po_no: string;
  vendor_code: string;
  vendor_name: string;
  order_date: string;
  source: RecordSource;
  status: POStatus;
  expected_date: string | null;
  note: string | null;
  created_by: string | null;
  lines: POLine[];
}

export interface Movement {
  id: number;
  movement_date: string;
  kind: string;
  item_code: string;
  location_code: string;
  lot_no: string;
  qty: number;
  reverses_id: number | null;
  created_by: string;
}

/** GET /locations */
export interface Location {
  code: string;
  name: string;
  is_sellable: boolean;
  may_return_to_stock: boolean;
  is_third_party_storage: boolean;
  can_receive: boolean;
}

// ---- Shipments and moving stock (Phase 6 step 2) -------------------------------------------

export interface Customer {
  customer_code: string;
  name: string;
  customer_type: string;
  source: RecordSource;
}

export interface Pick {
  line_no: number;
  item_code: string;
  location_code: string;
  location_name: string;
  lot_no: string;
  expiry_date: string | null;
  qty: number;
}

export interface PickPlan {
  picks: Pick[];
  short: Record<string, number>;
}

export interface ShipmentLine {
  line_no: number;
  item_code: string;
  description: string;
  sell_uom: string;
  qty: number;
  unit_price: number | null;
  promised: boolean;
  taken_from_stock: boolean;
  counts_as_demand: boolean;
  flags: string[];
  picks: Pick[];
}

/** GET /shipments */
export interface Shipment {
  order_no: string;
  customer_code: string;
  customer_name: string;
  kind: "customer" | "sample";
  order_date: string;
  ship_date: string;
  location_code: string;
  location_name: string;
  status: "open" | "shipped" | "cancelled";
  shipped_on: string | null;
  cancel_reason: string | null;
  note: string | null;
  created_by: string;
  lines: ShipmentLine[];
}

/** GET /stock-lots?item= */
export interface StockLot {
  item_code: string;
  location_code: string;
  location_name: string;
  lot_no: string;
  qty: number;
  expiry_date: string | null;
  unit_cost: number | null;
  counted: boolean;
  at_harbor: boolean;
}

/** GET /stock-movements?item= */
export interface StockChange {
  id: number;
  movement_date: string;
  kind: string;
  location_code: string;
  lot_no: string;
  qty: number;
  po_no: string | null;
  order_no: string | null;
  note: string | null;
  created_by: string;
  undone: boolean;
  is_undo: boolean;
  can_undo: boolean;
}

// ---- Imports (Phase 6 step 3) ---------------------------------------------------------------

export interface ImportSlot {
  slot: string;
  label: string;
  expected_name: string;
  columns: string[];
}

export interface ImportFile {
  slot: string;
  file_name: string;
  rows: number;
  size_bytes: number;
  sha256: string;
}

export interface ImportReport {
  kind: "bluetide" | "template";
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
  notes?: { total: number; by_problem: { trap_id: string; title: string; count: number }[] };
  conflicts?: string[];
  orphans?: string[];
  problems?: { slot: string; label: string; line: number; message: string }[];
  loaded?: Record<string, unknown>;
}

/** GET /imports, /imports/{id} */
export interface Import {
  id: number;
  kind: "bluetide" | "template";
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
