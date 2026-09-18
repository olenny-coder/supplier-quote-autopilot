import axios from "axios";

/**
 * The single Axios instance every buyer API call goes through.
 *
 * Responsibilities:
 *  - resolve the API base URL from the environment,
 *  - attach the buyer's bearer token to every request,
 *  - normalise backend errors into plain `Error(message)` instances,
 *  - clear an expired token and bounce to /login on 401.
 */

// Vite inlines `import.meta.env.*` at build time, so these are constants in the
// bundle. `VITE_API_URL` is the documented name; `VITE_API_BASE_URL` is the
// legacy name and is still honoured so existing deployments keep working.
const BASE_URL =
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  "http://localhost:8000";

/** localStorage key holding the buyer's JWT. Shared with the auth feature. */
export const TOKEN_STORAGE_KEY = "sqa_token";

/**
 * Read the stored token. Wrapped because storage access throws in private-mode
 * Safari and inside some embedded webviews — a missing token must never crash
 * the app on boot.
 */
export const getStoredToken = () => {
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
};

export const setStoredToken = (token) => {
  try {
    if (token) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    // Storage is unavailable; the in-memory token in AuthProvider still works
    // for the current page session.
  }
};

export const clearStoredToken = () => setStoredToken(null);

/**
 * FastAPI returns validation failures as `{detail: [{msg, loc}, ...]}` and
 * business failures as `{detail: "..."}`. Flatten both to one readable string
 * so `toast.error(error.message)` never prints "[object Object]".
 */
function normaliseDetail(detail) {
  if (!detail) return null;

  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    const parts = detail
      .map((entry) => {
        if (typeof entry === "string") return entry;
        if (entry && typeof entry === "object") {
          const location = Array.isArray(entry.loc)
            ? entry.loc.filter((part) => part !== "body").join(".")
            : "";
          return location ? `${location}: ${entry.msg}` : entry.msg;
        }
        return null;
      })
      .filter(Boolean);

    return parts.length ? parts.join(", ") : null;
  }

  if (typeof detail === "object") return detail.message || null;

  return null;
}

// Paths where a 401 must NOT redirect: the user is already on an auth screen,
// and redirecting would fight the login form's own error handling.
const AUTH_PATHS = ["/login", "/register"];

const client = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

client.interceptors.request.use((config) => {
  const token = getStoredToken();

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;

    if (status === 401) {
      clearStoredToken();

      const { pathname, search } = window.location;

      if (!AUTH_PATHS.includes(pathname)) {
        // Preserve where the buyer was so login can send them back. A full
        // navigation (rather than history.push) guarantees the app boots with
        // no stale authenticated state in memory.
        const next = encodeURIComponent(`${pathname}${search}`);
        window.location.assign(`/login?next=${next}`);
      }
    }

    const message =
      normaliseDetail(error.response?.data?.detail) ||
      error.response?.data?.message ||
      error.message ||
      "Something went wrong";

    const normalised = new Error(message);

    // Callers occasionally need the status code (e.g. to distinguish "not
    // found" from a transport failure) without reaching into the raw response.
    normalised.status = status ?? null;

    return Promise.reject(normalised);
  }
);

export default client;
