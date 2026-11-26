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
  Harbor,
  Import,
  Dashboard,
  DataIssuePage,
  DataIssueSummary,
  EventEntry,
  HandledNote,
  ItemCard,
  ItemDetail,
  ItemSettings,
  LoadRun,
  OnTheWayLine,
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
  onTheWay: (q: string) => ["on-the-way", q] as const,
  imports: ["imports"] as const,
  harbor: ["harbor"] as const,
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

/** BlueTide's open PO lines as the plan counts them (the On the way page). */
export const useOnTheWay = (q: string) =>
  useQuery({
    queryKey: keys.onTheWay(q),
    queryFn: ({ signal }) => apiGet<OnTheWayLine[]>(`/purchase-orders?q=${enc(q)}`, signal),
    placeholderData: (previous) => previous, // keep the list on screen while a search reloads
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
    ["on-the-way"],
    keys.vendors,
    keys.imports,
    ["data-issues"],
    keys.loadRuns,
    keys.harbor,
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

// ---- Weekly uploads of BlueTide's files (ADR-029) ---------------------------------------------

export const useStartImport = () =>
  useEdit(
    () => apiSend<Import>("POST", "/imports", { kind: "bluetide" }),
    () => "Started a BlueTide upload",
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

// ---- Harbor storage (P1 #1; ADR-031) -------------------------------------------------------

export const useHarbor = () =>
  useQuery({
    queryKey: keys.harbor,
    queryFn: ({ signal }) => apiGet<Harbor>("/harbor-storage", signal),
  });

/** No cases = what's at Harbor now for that item; cases = a what-if amount. */
export interface HarborRowInput {
  item_code: string;
  cases_per_pallet: number;
  cases?: number;
}

export const useAddHarborRows = () =>
  useEdit(
    (v: { rows: HarborRowInput[] }) => apiSend<Harbor>("POST", "/harbor-storage/rows", v),
    (v) =>
      v.rows.length === 1 ? "Added to your table" : `Added ${v.rows.length} rows to your table`,
    (client, _v, result) => client.setQueryData(keys.harbor, result),
  );

export const useDeleteHarborRow = () =>
  useEdit(
    (v: { id: number }) => apiSend<Harbor>("DELETE", `/harbor-storage/rows/${v.id}`),
    () => "Removed from your table",
    (client, _v, result) => client.setQueryData(keys.harbor, result),
  );

export const useSaveCasesPerPallet = () =>
  useEdit(
    (v: { code: string; cases_per_pallet: number }) =>
      apiSend<ItemSettings>("PATCH", `/items/${enc(v.code)}/settings`, {
        cases_per_pallet: v.cases_per_pallet,
      }),
    (v) => `Saved: ${v.cases_per_pallet.toLocaleString("en-US")} cases per pallet for ${v.code}`,
  );
