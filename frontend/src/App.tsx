/**
 * Page routes. Every route shares the header. Deep links (e.g. /items/SHR-1620 in
 * Phase 5) work on Vercel because vercel.json rewrites every path to index.html.
 */
import { Route, Routes } from "react-router";
import { AppHeader } from "./components/AppHeader";
import { MondayPage } from "./pages/MondayPage";
import { NotFoundPage } from "./pages/NotFoundPage";

export function App() {
  return (
    <div className="min-h-screen bg-ice">
      <AppHeader />
      <Routes>
        <Route path="/" element={<MondayPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </div>
  );
}
