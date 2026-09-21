import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import Loading from "@/shared/components/Loading";
import Header from "@/shared/layout/Header";

import { AuthProvider } from "@/features/auth/AuthProvider";
import ProtectedRoute from "@/features/auth/components/ProtectedRoute";
import { useAuth } from "@/features/auth/useAuth";
import LoginPage from "@/features/auth/pages/LoginPage";
import RegisterPage from "@/features/auth/pages/RegisterPage";
import ChatWidget from "@/features/chat/components/ChatWidget";
import DashboardPage from "@/features/dashboard/pages/DashboardPage";
import DemoPage from "@/features/demo/pages/DemoPage";
import PendingFollowUpsPage from "@/features/followup/pages/PendingFollowUpsPage";
import CreateRFQPage from "@/features/rfq/pages/CreateRFQPage";
import RFQDetailsPage from "@/features/rfq/pages/RFQDetailsPage";
import RFQListPage from "@/features/rfq/pages/RFQListPage";
import SupplierListPage from "@/features/supplier/pages/SupplierListPage";

/**
 * Chrome shared by every authenticated screen. It is a layout route, so the
 * header, footer and the procurement assistant survive navigation between
 * pages instead of being re-mounted on each route change.
 */
function AppShell() {
  return (
    <div className="theme-transition flex min-h-screen flex-col text-content">
      <Header />

      <main className="mx-auto w-full max-w-7xl flex-1 px-5 py-8 sm:px-6 lg:py-10">
        <Outlet />
      </main>

      <footer className="border-t border-border-default/70">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 px-6 py-5 text-xs text-subtle sm:flex-row">
          <span>Supplier Quote Autopilot</span>
          <span>Award decisions always stay with a human buyer.</span>
        </div>
      </footer>

      <ChatWidget />
    </div>
  );
}

/**
 * Unknown path handler. An authenticated buyer lands back on the dashboard; an
 * anonymous visitor is sent to login. The session check has to settle first,
 * otherwise a signed-in buyer would be bounced to /login for a beat.
 */
function FallbackRedirect() {
  const { token, loading } = useAuth();

  if (loading) {
    return <Loading message="Checking your session…" />;
  }

  return <Navigate replace to={token ? "/" : "/login"} />;
}

function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* Public */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Public, read-only: one sample tender, rendered from
            `GET /demo/workspace`, for a visitor with no account. Deliberately
            outside `ProtectedRoute` and outside `AppShell` — the demo calls no
            authenticated endpoint, and the shell's chat widget does. */}
        <Route path="/demo" element={<DemoPage />} />

        {/* Protected: everything below shares the header/footer/chat shell. */}
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route path="/" element={<DashboardPage />} />

            <Route path="/rfqs" element={<RFQListPage />} />
            <Route path="/rfqs/new" element={<CreateRFQPage />} />
            <Route path="/rfqs/:id" element={<RFQDetailsPage />} />

            <Route path="/suppliers" element={<SupplierListPage />} />

            {/* The workspace-wide follow-up approval queue, linked from the
                dashboard's "awaiting your approval" card. */}
            <Route path="/follow-ups" element={<PendingFollowUpsPage />} />
          </Route>
        </Route>

        <Route path="*" element={<FallbackRedirect />} />
      </Routes>
    </AuthProvider>
  );
}

export default App;
