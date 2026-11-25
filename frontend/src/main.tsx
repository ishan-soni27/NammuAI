/**
 * App entry: providers only. TanStack Query handles loading, error and retry for every
 * API call. React Router handles pages.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { App } from "./App";
import "./styles/index.css";

const queryClient = new QueryClient({
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
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
