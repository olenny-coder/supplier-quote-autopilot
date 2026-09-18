# Auth slice

Buyer identity for Supplier Quote Autopilot: sign-in, registration, the session
that every other feature depends on, and the route guard.

## Files

| File | Purpose |
| --- | --- |
| `api.js` | The four endpoints: `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `PATCH /auth/me`. |
| `AuthContext.js` | The React context object, kept separate so Fast Refresh can swap the provider without invalidating consumers. |
| `AuthProvider.jsx` | Owns `{ token, user, loading, login, register, logout }`, mirrors the token into `localStorage` under `sqa_token`, and validates it with `GET /auth/me` on boot. |
| `useAuth.js` | Context hook; throws outside the provider instead of returning `null`. |
| `navigation.js` | `resolveRedirectTarget` / `withNext` — where to land after signing in, from `?next=` (set by the axios 401 interceptor) or router state (set by `ProtectedRoute`). Only same-origin absolute paths are accepted, so `?next=https://evil.example` cannot turn login into an open redirect. |
| `components/ProtectedRoute.jsx` | Route guard: waits for the session check, then renders the matched routes (or its children) or redirects to `/login`, preserving the attempted location. |
| `components/AuthLayout.jsx` | The public shell (brand panel + form) used by both auth pages. |
| `pages/LoginPage.jsx`, `pages/RegisterPage.jsx` | The two public screens, with inline validation and a form-level error panel. |

## Notes

- The token itself is owned by `shared/api/client.js`: the request interceptor
  reads the same `sqa_token` key, and the response interceptor clears it and
  redirects on 401.
- `loading` is true only while a stored token is being validated, so routing
  never flashes the login page at an already-signed-in buyer.
- Passwords are never persisted anywhere in the frontend.
