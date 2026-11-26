/**
 * Page routes. Every route shares the header. Deep links (e.g. /items/SHR-1620) work on
 * Vercel because the web service in the root vercel.json rewrites every non-file path to
 * index.html. The item page (with the chart library) loads on first visit, so the Monday
 * screen stays small and fast.
 */
import { lazy, Suspense, useState } from "react";
import { Navigate, Route, Routes } from "react-router";
import { ActorPrompt } from "./components/ActorPrompt";
import { AppHeader } from "./components/AppHeader";
import { LoadingState } from "./components/LoadingState";
import { getActor, hasChosenActor } from "./lib/actor";
import { ActivityPage } from "./pages/ActivityPage";
import { DataNotesPage } from "./pages/DataNotesPage";
import { ItemsPage } from "./pages/ItemsPage";
import { LeadTimesPage } from "./pages/LeadTimesPage";
import { MondayPage } from "./pages/MondayPage";
import { NewPOPage } from "./pages/NewPOPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PurchaseOrdersPage } from "./pages/PurchaseOrdersPage";

const ItemPage = lazy(() => import("./pages/ItemPage").then((m) => ({ default: m.ItemPage })));

export function App() {
  const [actor, setActorName] = useState(getActor);
  const [askActor, setAskActor] = useState(() => !hasChosenActor());

  return (
    <div className="min-h-screen bg-ice">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:m-2 focus:rounded focus:bg-hull focus:p-2"
      >
        Skip to content
      </a>
      <AppHeader actor={actor} onChangeActor={() => setAskActor(true)} />
      <main id="main" className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <Suspense fallback={<LoadingState label="Loading this page" />}>
          <Routes>
            <Route path="/" element={<MondayPage />} />
            <Route path="/items" element={<ItemsPage />} />
            <Route path="/items/:code" element={<ItemPage />} />
            <Route path="/purchase-orders" element={<PurchaseOrdersPage />} />
            <Route path="/purchase-orders/new" element={<NewPOPage />} />
            <Route path="/suppliers" element={<LeadTimesPage />} />
            <Route path="/lead-times" element={<Navigate to="/suppliers" replace />} />
            <Route path="/data-notes" element={<DataNotesPage />} />
            <Route path="/activity" element={<ActivityPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </main>
      <ActorPrompt
        open={askActor}
        onDone={(name) => {
          setActorName(name);
          setAskActor(false);
        }}
      />
    </div>
  );
}
