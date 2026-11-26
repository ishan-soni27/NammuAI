/**
 * One TanStack Query hook per API endpoint, plus the mutations for Dana's edits.
 *
 * Reads are cached and refreshed after any edit that could change them: an edit to a lead time,
 * a PO date, a handled note or an item setting can move items between sections, so the dashboard,
 * the item, the items list and the activity log are all refetched (`refreshAfterEdit`).
 * Each mutation's success message says exactly what happened (BUILD_PROMPT §9.5).
 *
 * How to add an endpoint: add its type to types.ts and a hook here; components only call hooks.
 */
import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useToast } from "../components/Toast";
import { ApiError, apiGet, apiSend, apiUpload } from "./client";
import type {
  AuditEntry,
  Customer,
  Import,
  PickPlan,
  Shipment,
  StockChange,
  StockLot,
  Dashboard,
  DataIssuePage,
  DataIssueSummary,
  EventEntry,
  HandledNote,
  ItemCard,
  ItemDetail,
  ItemSettings,
  ItemDetails,
  LoadRun,
  Location,
  Movement,
  PurchaseOrder,
  Rule,
  Vendor,
} from "./types";

const enc = encodeURIComponent;

export const keys = {
  dashboard: ["dashboard"] as const,
  items: ["items"] as const,
  item: (code: string) => ["item", code] as const,
  vendors: ["vendors"] as const,
  issueSummary: ["data-issues", "summary"] as const,
  issues: (trap: string, offset: number) => ["data-issues", trap, offset] as const,
  audit: ["audit-log"] as const,
  events: ["events"] as const,
  loadRuns: ["load-runs"] as const,
  settings: ["settings"] as const,
  purchaseOrders: (status: string, q: string) => ["purchase-orders", status, q] as const,
  itemDetails: ["item-details"] as const,
  locations: ["locations"] as const,
  customers: ["customers"] as const,
  shipments: (status: string, q: string) => ["shipments", status, q] as const,
  picks: (orderNo: string) => ["picks", orderNo] as const,
  stockLots: (item: string) => ["stock-lots", item] as const,
  stockChanges: (item: string) => ["stock-changes", item] as const,
  imports: ["imports"] as const,
};

// ---- Reads ---------------------------------------------------------------------------------

export const useDashboard = () =>
  useQuery({
    queryKey: keys.dashboard,
    queryFn: ({ signal }) => apiGet<Dashboard>("/dashboard", signal),
  });

export const useItems = () =>
  useQuery({ queryKey: keys.items, queryFn: ({ signal }) => apiGet<ItemCard[]>("/items", signal) });

export const useItem = (code: string) =>
  useQuery({
    queryKey: keys.item(code),
    queryFn: ({ signal }) => apiGet<ItemDetail>(`/items/${enc(code)}`, signal),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
  });

export const useVendors = () =>
  useQuery({
    queryKey: keys.vendors,
    queryFn: ({ signal }) => apiGet<Vendor[]>("/vendors", signal),
  });

export const useDataIssueSummary = () =>
  useQuery({
    queryKey: keys.issueSummary,
    queryFn: ({ signal }) => apiGet<DataIssueSummary>("/data-issues/summary", signal),
  });

export const useDataIssues = (trapId: string, offset: number, enabled: boolean) =>
  useQuery({
    queryKey: keys.issues(trapId, offset),
    queryFn: ({ signal }) =>
      apiGet<DataIssuePage>(
        `/data-issues?trap_id=${enc(trapId)}&limit=50&offset=${offset}`,
        signal,
      ),
    enabled,
  });

export const useAuditLog = () =>
  useQuery({
    queryKey: keys.audit,
    queryFn: ({ signal }) => apiGet<AuditEntry[]>("/audit-log?limit=100", signal),
  });

export const useEvents = () =>
  useQuery({
    queryKey: keys.events,
    queryFn: ({ signal }) => apiGet<EventEntry[]>("/events?limit=100", signal),
  });

export const useLoadRuns = () =>
  useQuery({
    queryKey: keys.loadRuns,
    queryFn: ({ signal }) => apiGet<LoadRun[]>("/load-runs", signal),
  });

export const useRules = () =>
  useQuery({
    queryKey: keys.settings,
    queryFn: ({ signal }) => apiGet<Rule[]>("/settings", signal),
  });

export const usePurchaseOrders = (status: string, q: string) =>
  useQuery({
    queryKey: keys.purchaseOrders(status, q),
    queryFn: ({ signal }) =>
      apiGet<PurchaseOrder[]>(`/purchase-orders?status=${enc(status)}&q=${enc(q)}`, signal),
    placeholderData: (previous) => previous, // keep the list on screen while a filter reloads
  });

export const useItemDetails = () =>
  useQuery({
    queryKey: keys.itemDetails,
    queryFn: ({ signal }) => apiGet<ItemDetails[]>("/item-details", signal),
  });

export const useLocations = () =>
  useQuery({
    queryKey: keys.locations,
    queryFn: ({ signal }) => apiGet<Location[]>("/locations", signal),
    staleTime: Infinity,
  });

export const useCustomers = () =>
  useQuery({
    queryKey: keys.customers,
    queryFn: ({ signal }) => apiGet<Customer[]>("/customers", signal),
  });

export const useShipments = (status: string, q: string) =>
  useQuery({
    queryKey: keys.shipments(status, q),
    queryFn: ({ signal }) =>
      apiGet<Shipment[]>(`/shipments?status=${enc(status)}&q=${enc(q)}`, signal),
    placeholderData: (previous) => previous,
  });

export const usePickPlan = (orderNo: string, enabled: boolean) =>
  useQuery({
    queryKey: keys.picks(orderNo),
    queryFn: ({ signal }) => apiGet<PickPlan>(`/shipments/${enc(orderNo)}/picks`, signal),
    enabled,
  });

export const useStockLots = (item: string, enabled = true) =>
  useQuery({
    queryKey: keys.stockLots(item),
    queryFn: ({ signal }) => apiGet<StockLot[]>(`/stock-lots?item=${enc(item)}`, signal),
    enabled: enabled && Boolean(item),
  });

export const useStockChanges = (item: string) =>
  useQuery({
    queryKey: keys.stockChanges(item),
    queryFn: ({ signal }) => apiGet<StockChange[]>(`/stock-movements?item=${enc(item)}`, signal),
  });

export const useImports = () =>
  useQuery({
    queryKey: keys.imports,
    queryFn: ({ signal }) => apiGet<Import[]>("/imports", signal),
  });

// ---- Edits ---------------------------------------------------------------------------------

function refreshAfterEdit(client: QueryClient) {
  const all = [
    keys.dashboard,
    keys.items,
    keys.audit,
    ["item"],
    ["purchase-orders"],
    keys.itemDetails,
    keys.vendors,
    ["shipments"],
    ["picks"],
    ["stock-lots"],
    ["stock-changes"],
    keys.customers,
    keys.imports,
    ["data-issues"],
    keys.loadRuns,
  ];
  for (const key of all) {
    void client.invalidateQueries({ queryKey: key });
  }
}

function useEdit<TVars, TResult>(
  send: (vars: TVars) => Promise<TResult>,
  successMessage: (vars: TVars, result: TResult) => string,
  after?: (client: QueryClient, vars: TVars, result: TResult) => void,
) {
  const client = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: send,
    onSuccess: (result, vars) => {
      refreshAfterEdit(client);
      after?.(client, vars, result);
      toast.show(successMessage(vars, result), "success");
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : "That didn't save. Please try again.";
      const reference =
        error instanceof ApiError && error.requestId ? ` (reference ${error.requestId})` : "";
      toast.show(message + reference, "error");
    },
  });
}

export interface HandledInput {
  code: string;
  qty: number | null;
  eta: string | null;
  note: string | null;
}

export const useMarkHandled = () =>
  useEdit(
    (v: HandledInput) =>
      apiSend<HandledNote>("POST", `/items/${enc(v.code)}/handled`, {
        qty: v.qty,
        eta: v.eta,
        note: v.note,
      }),
    () => "Marked as handled",
  );

export const useClearHandled = () =>
  useEdit(
    (v: { id: number; reason: string | null }) =>
      apiSend<HandledNote>("DELETE", `/handled/${v.id}`, { reason: v.reason }),
    () => "Handled note cleared",
  );

export const useSetPoDate = () =>
  useEdit(
    (v: { poNo: string; lineNo: number; eta: string | null; note: string | null }) =>
      apiSend("PATCH", `/purchase-orders/${enc(v.poNo)}/lines/${v.lineNo}`, {
        eta: v.eta,
        note: v.note,
      }),
    (v) => (v.eta ? "Arrival date saved" : "Arrival date cleared"),
  );

export const useUpdateVendor = () =>
  useEdit(
    (v: { code: string; lead_time_days?: number; cushion_days?: number; note?: string | null }) => {
      const { code, ...body } = v;
      return apiSend<Vendor>("PATCH", `/vendors/${enc(code)}`, body);
    },
    (_v, result) => `Saved ${result.name}`,
    (client) => void client.invalidateQueries({ queryKey: keys.vendors }),
  );

export const useUpdateItemSettings = () =>
  useEdit(
    (v: {
      code: string;
      lifecycle_override?: string | null;
      safety_days_override?: number | null;
      note?: string | null;
    }) => {
      const { code, ...body } = v;
      return apiSend<ItemSettings>("PATCH", `/items/${enc(code)}/settings`, body);
    },
    () => "Item settings saved",
  );

// ---- Dana's own records (Phase 6) ----------------------------------------------------------

export interface POCreateInput {
  vendor_code: string;
  po_no: string | null;
  order_date: string | null;
  expected_date: string | null;
  note: string | null;
  lines: { item_code: string; qty: number; unit_cost: number | null }[];
  clear_handled_notes: boolean;
}

export const useCreatePO = () =>
  useEdit(
    (v: POCreateInput) => apiSend<PurchaseOrder>("POST", "/purchase-orders", v),
    (_v, po) => `Saved ${po.po_no}`,
  );

const line = (po: string, n: number) => `/purchase-orders/${enc(po)}/lines/${n}`;

export const useShipLine = () =>
  useEdit(
    (v: { po: string; line: number; container_no: string | null; eta: string | null }) =>
      apiSend<PurchaseOrder>("POST", `${line(v.po, v.line)}/ship`, {
        container_no: v.container_no,
        eta: v.eta,
      }),
    (v) => `${v.po} line ${v.line} marked shipped`,
  );

export const useCancelLine = () =>
  useEdit(
    (v: { po: string; line: number; reason: string | null }) =>
      apiSend<PurchaseOrder>("POST", `${line(v.po, v.line)}/cancel`, { reason: v.reason }),
    (v) => `${v.po} line ${v.line} cancelled`,
  );

export const useReopenLine = () =>
  useEdit(
    (v: { po: string; line: number }) =>
      apiSend<PurchaseOrder>("DELETE", `${line(v.po, v.line)}/status`),
    (v) => `${v.po} line ${v.line} reopened`,
  );

export interface ReceiveInput {
  po: string;
  line: number;
  qty: number;
  location_code: string;
  lot_no: string;
  expiry_date: string;
  unit_cost: number | null;
  allow_over_receipt: boolean;
}

export const useReceiveLine = () =>
  useEdit(
    ({ po, line: n, ...body }: ReceiveInput) =>
      apiSend<PurchaseOrder>("POST", `${line(po, n)}/receive`, body),
    (v) => `Received ${v.qty.toLocaleString("en-US")} on ${v.po} line ${v.line}`,
  );

export const useUndoMovement = () =>
  useEdit(
    (v: { id: number; reason: string | null }) =>
      apiSend<Movement>("POST", `/stock-movements/${v.id}/undo`, { reason: v.reason }),
    () => "Receipt undone",
  );

export interface VendorCreateInput {
  vendor_code: string | null;
  name: string;
  country: string | null;
  lead_time_days: number;
  cushion_days: number;
  note: string | null;
}

export const useCreateVendor = () =>
  useEdit(
    (v: VendorCreateInput) => apiSend<Vendor>("POST", "/vendors", v),
    (_v, vendor) => `Added ${vendor.name}`,
  );

export interface ItemInputBody {
  item_code: string;
  description: string;
  category: string;
  sell_uom: "CS" | "LB";
  lb_per_case: number | null;
  vendor_code: string;
  status: "active" | "discontinued";
  note: string | null;
}

export const useCreateItem = () =>
  useEdit(
    (v: ItemInputBody) => apiSend<ItemDetails>("POST", "/items", v),
    (_v, item) => `Added ${item.item_code}`,
  );

export const useUpdateItemDetails = () =>
  useEdit(
    ({ item_code, ...body }: Partial<ItemInputBody> & { item_code: string }) =>
      apiSend<ItemDetails>("PATCH", `/items/${enc(item_code)}/details`, body),
    (v) => `Saved ${v.item_code}`,
  );

// ---- Shipments and moving stock (Phase 6 step 2) ----------------------------------------------

export const useCreateCustomer = () =>
  useEdit(
    (v: { name: string; customer_code: string | null; customer_type: string }) =>
      apiSend<Customer>("POST", "/customers", v),
    (_v, c) => `Added ${c.name}`,
  );

export interface ShipmentCreateInput {
  customer_code: string;
  order_no: string | null;
  kind: "customer" | "sample";
  order_date: string | null;
  ship_date: string | null;
  location_code: string;
  note: string | null;
  lines: { item_code: string; qty: number; unit_price: number | null }[];
}

export const useCreateShipment = () =>
  useEdit(
    (v: ShipmentCreateInput) => apiSend<Shipment>("POST", "/shipments", v),
    (_v, sh) => `Saved order ${sh.order_no}`,
  );

export const useShipOrder = () =>
  useEdit(
    (v: { orderNo: string; picks: { line_no: number; lot_no: string; qty: number }[] | null }) =>
      apiSend<Shipment>("POST", `/shipments/${enc(v.orderNo)}/ship`, { picks: v.picks }),
    (v) => `Order ${v.orderNo} shipped`,
  );

export const useCancelOrder = () =>
  useEdit(
    (v: { orderNo: string; reason: string | null }) =>
      apiSend<Shipment>("POST", `/shipments/${enc(v.orderNo)}/cancel`, { reason: v.reason }),
    (v) => `Order ${v.orderNo} cancelled`,
  );

export const useUndoShip = () =>
  useEdit(
    (v: { orderNo: string }) =>
      apiSend<Shipment>("POST", `/shipments/${enc(v.orderNo)}/undo-ship`, {}),
    (v) => `Order ${v.orderNo} is open again`,
  );

export interface MoveInput {
  item_code: string;
  from_location: string;
  lot_no: string;
  to_location: string;
  qty: number;
  note: string | null;
}

export const useMoveStock = () =>
  useEdit(
    (v: MoveInput) => apiSend<Movement[]>("POST", "/stock-moves", v),
    (v) => `Moved ${v.qty.toLocaleString("en-US")} of ${v.item_code} to ${v.to_location}`,
  );

// ---- Imports (Phase 6 step 3) -------------------------------------------------------------------

export const useStartImport = () =>
  useEdit(
    (v: { kind: "bluetide" | "template" }) => apiSend<Import>("POST", "/imports", v),
    (v) =>
      v.kind === "bluetide"
        ? "Started a BlueTide import"
        : "Started an import of your spreadsheets",
  );

export const usePutImportFile = () =>
  useEdit(
    (v: { id: number; slot: string; file: File }) =>
      apiUpload<Import>(`/imports/${v.id}/files/${enc(v.slot)}?name=${enc(v.file.name)}`, v.file),
    (v) => `${v.file.name} uploaded`,
  );

export const useCheckImport = () =>
  useEdit(
    (v: { id: number }) => apiSend<Import>("POST", `/imports/${v.id}/check`),
    (_v, imp) =>
      imp.confirm_code ? "Checked: ready to load" : "Checked: something needs fixing first",
  );

export const useLoadImport = () =>
  useEdit(
    (v: { id: number; confirm_code: string }) =>
      apiSend<Import>("POST", `/imports/${v.id}/load`, { confirm_code: v.confirm_code }),
    () => "Loaded. The Monday numbers now use the new data.",
  );

export const useDiscardImport = () =>
  useEdit(
    (v: { id: number }) => apiSend<Import>("DELETE", `/imports/${v.id}`),
    () => "Import discarded",
  );
