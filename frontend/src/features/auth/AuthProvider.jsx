import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { toast } from "sonner";

import {
  clearStoredToken,
  getStoredToken,
  setStoredToken,
} from "@/shared/api/client";

import { getMe, login as loginRequest, register as registerRequest } from "./api";
import { AuthContext } from "./AuthContext";

/**
 * Owns the buyer's session for the whole app.
 *
 * The token lives in `localStorage` under `sqa_token` (the key the axios
 * request interceptor reads) and is mirrored in React state so components
 * re-render on sign-in/sign-out. `loading` is true while `GET /auth/me`
 * resolves on boot — routing waits for it rather than flashing the login page
 * at an already-signed-in buyer.
 */
export function AuthProvider({ children }) {
  const navigate = useNavigate();

  const [token, setToken] = useState(() => getStoredToken());
  const [user, setUser] = useState(null);
  // Only "loading" when there is actually a token to validate.
  const [loading, setLoading] = useState(() => Boolean(getStoredToken()));

  useEffect(() => {
    if (!token) {
      setUser(null);
      setLoading(false);
      return undefined;
    }

    let active = true;

    setLoading(true);

    (async () => {
      try {
        const profile = await getMe();
        if (active) setUser(profile);
      } catch (error) {
        // A rejected token must never leave the app half-authenticated: drop it
        // and fall back to the signed-out view. A 401 was already handled by the
        // response interceptor (which redirects), so only other failures — a
        // backend outage, say — are worth telling the buyer about.
        if (active) {
          clearStoredToken();
          setToken(null);
          setUser(null);
        }

        if (error.status !== 401) {
          toast.error(error.message);
        }
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
    };
  }, [token]);

  const login = useCallback(async (credentials) => {
    const response = await loginRequest(credentials);

    setStoredToken(response.access_token);
    setToken(response.access_token);
    setUser(response.user || null);

    return response;
  }, []);

  const register = useCallback(async (payload) => {
    const response = await registerRequest(payload);

    setStoredToken(response.access_token);
    setToken(response.access_token);
    setUser(response.user || null);

    return response;
  }, []);

  const logout = useCallback(() => {
    clearStoredToken();
    setToken(null);
    setUser(null);
    navigate("/login", { replace: true });
  }, [navigate]);

  const value = useMemo(
    () => ({ token, user, loading, login, register, logout }),
    [token, user, loading, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
