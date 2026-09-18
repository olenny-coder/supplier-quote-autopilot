import { Navigate, Outlet, useLocation } from "react-router-dom";

import Loading from "@/shared/components/Loading";

import { useAuth } from "../useAuth";

/**
 * Route guard for every buyer screen.
 *
 * Waits for the session check to settle, then either renders the matched child
 * routes (`<Outlet />` when used as a layout route) or its `children`, or
 * redirects to /login carrying the attempted location in router state so the
 * login page can send the buyer straight back to where they were headed.
 */
function ProtectedRoute({ children }) {
  const { token, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <Loading message="Checking your session…" />;
  }

  if (!token) {
    return <Navigate replace to="/login" state={{ from: location }} />;
  }

  return children ?? <Outlet />;
}

export default ProtectedRoute;
