/**
 * App entry: providers only. TanStack Query handles loading, error and retry for every
 * API call. React Router handles pages. Unexpected errors (browser errors, failed reads)
 * are reported to POST /api/v1/client-events so they show up on the Activity page.
 */
import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { App } from "./App";
import { ApiError } from "./api/client";
import { ToastProvider } from "./components/Toast";
import { installGlobalErrorReporting, reportClientEvent } from "./lib/reportError";
import "./styles/index.css";

installGlobalErrorReporting();

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => {
      // A 404 for an unknown item code is an answer, not a fault.
      if (error instanceof ApiError && error.status === 404) return;
      reportClientEvent("query_failed", {
        query: JSON.stringify(query.queryKey),
        message: error.message,
        status: error instanceof ApiError ? error.status : null,
        request_id: error instanceof ApiError ? error.requestId : null,
      });
    },
  }),
  defaultOptions: {
    queries: {
      // Dana's numbers only change when she edits something or data is reloaded;
      // don't refetch every time the window regains focus.
      refetchOnWindowFocus: false,
    },
  },
});

const root = document.getElementById("root");
if (!root) throw new Error("index.html is missing <div id='root'>");

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  </StrictMode>,
);
