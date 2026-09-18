/**
 * Where to send the buyer after signing in.
 *
 * Two sources, in priority order:
 *  1. `?next=/rfqs/12` — written by the axios 401 interceptor, which cannot use
 *     router state (it redirects through the browser).
 *  2. router state `{ from: location }` — written by `ProtectedRoute`.
 *
 * Only same-origin, absolute paths are accepted: an attacker-supplied
 * `?next=https://evil.example` must never turn the login page into an open
 * redirect.
 */
export function resolveRedirectTarget(search, state, fallback = "/") {
  const fromQuery = new URLSearchParams(search || "").get("next");
  const fromState = state?.from?.pathname
    ? `${state.from.pathname}${state.from.search || ""}`
    : null;

  const candidate = fromQuery || fromState;

  if (!candidate) return fallback;

  if (!candidate.startsWith("/") || candidate.startsWith("//")) return fallback;

  // Never bounce back to an auth screen — that would loop.
  if (candidate.startsWith("/login") || candidate.startsWith("/register")) {
    return fallback;
  }

  return candidate;
}

/** Builds the login/register cross-links while preserving the `next` target. */
export function withNext(path, target) {
  if (!target || target === "/") return path;

  return `${path}?next=${encodeURIComponent(target)}`;
}
