import { Navigate, Route, Routes } from "react-router-dom";

import Header from "@/shared/layout/Header";
import ChatWidget from "@/features/chat/components/ChatWidget";

import RFQListPage from "@/features/rfq/pages/RFQListPage";
import CreateRFQPage from "@/features/rfq/pages/CreateRFQPage";
import RFQDetailsPage from "@/features/rfq/pages/RFQDetailsPage";

function App() {
  return (
    <div className="theme-transition flex min-h-screen flex-col text-content">
      <Header />

      <main className="mx-auto w-full max-w-7xl flex-1 px-5 py-8 sm:px-6 lg:py-10">
        <Routes>
          <Route path="/" element={<RFQListPage />} />

          <Route path="/rfqs/new" element={<CreateRFQPage />} />

          <Route path="/rfqs/:id" element={<RFQDetailsPage />} />

          <Route path="*" element={<Navigate replace to="/" />} />
        </Routes>
      </main>

      <footer className="border-t border-border-default/70">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 px-6 py-5 text-xs text-subtle sm:flex-row">
          <span>RFQ Comparison Tool</span>
          <span>Compare supplier quotes with confidence.</span>
        </div>
      </footer>

      <ChatWidget />
    </div>
  );
}

export default App;
