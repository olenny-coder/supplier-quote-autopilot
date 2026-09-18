# Frontend — Supplier Quote Autopilot

React single-page app for the buyer side of Supplier Quote Autopilot: create an
RFQ, invite suppliers, watch who has responded, chase the gaps, compare quotes
side by side, and approve an award. Built with Vite and styled with Tailwind CSS
v4 using a token-driven light/dark theme.

---

## Tech stack

| Concern     | Choice                                       |
| ----------- | -------------------------------------------- |
| Framework   | React 19                                      |
| Build tool  | Vite 7                                        |
| Styling     | Tailwind CSS 4 (`@tailwindcss/vite`)          |
| Routing     | React Router 7                                |
| HTTP        | Axios (shared client: bearer token + 401 handling) |
| Markdown    | react-markdown + remark-gfm (chat rendering)  |
| Toasts      | Sonner                                        |
| Lint        | ESLint 9                                      |

JavaScript + JSX (no TypeScript). The `@` alias maps to `src/` (configured in
`vite.config.js` and `jsconfig.json`).

---

## Project structure

The app is organized into **feature slices** (`src/features/*`) and cross-cutting
**shared** modules (`src/shared/*`). A feature owns its API calls, hooks,
components and pages; shared holds the API client, UI primitives, status
vocabulary, layout and theming.

```
src/
├── main.jsx                 # entry: ThemeProvider → Router → ChatProvider → App + Toaster
├── App.jsx                  # AuthProvider, route tree, app shell (header/footer/chat)
├── index.css                # Tailwind import, semantic design tokens, print styles
│
├── features/
│   ├── auth/                # login/register, session, ProtectedRoute, redirect targets
│   ├── dashboard/           # / — summary counters, closing soon, needs attention
│   ├── rfq/                 # register, create form + suppliers step, tabbed detail page
│   ├── quote/               # quote table, manual entry, CSV/PDF import
│   ├── comparison/          # ranked table, weights, recommendation, award approval
│   ├── supplier/            # supplier directory (CRUD + response stats)
│   ├── followup/            # approval queue + communication log
│   └── chat/                # procurement assistant widget (mounts for signed-in buyers)
│
└── shared/
    ├── api/client.js        # axios instance: base URL, bearer token, 401 redirect, Error(message)
    ├── components/          # Modal, ConfirmModal, Loading, EmptyState, StatusBadge, ui/ primitives
    ├── layout/Header.jsx    # wordmark, Dashboard/RFQs/Suppliers nav, account menu, theme toggle
    ├── lib/                 # format.js, status.js (status→badge mapping), clipboard.js
    └── theme/               # ThemeProvider, ThemeToggle, ThemedToaster
```

Each feature has its own `README.md` describing its files, endpoints and the
decisions behind it.

### Routes

| Path            | Page                   | Access    | Purpose                                                  |
| --------------- | ---------------------- | --------- | -------------------------------------------------------- |
| `/login`        | `LoginPage`            | public    | Sign in; returns to the attempted path via `?next=`.     |
| `/register`     | `RegisterPage`         | public    | Create a buyer account.                                   |
| `/`             | `DashboardPage`        | protected | Counters, closing-soon deadlines, suppliers to chase.     |
| `/rfqs`         | `RFQListPage`          | protected | RFQ register with search and status filters.              |
| `/rfqs/new`     | `CreateRFQPage`        | protected | Create an RFQ and invite up to N suppliers in one go.     |
| `/rfqs/:id`     | `RFQDetailsPage`       | protected | Tabbed workbench: suppliers · quotes · comparison · follow-ups · details. |
| `/suppliers`    | `SupplierListPage`     | protected | Supplier directory.                                       |
| `/follow-ups`   | `PendingFollowUpsPage` | protected | Workspace-wide queue of drafts awaiting approval.         |
| `*`             | —                      | —         | Redirects to `/` when signed in, otherwise `/login`.      |

The RFQ detail tab is part of the URL (`/rfqs/12?tab=comparison`), so the
dashboard's deep links open the exact tab they refer to.

---

## Key concepts

### API client (`shared/api/client.js`)

One Axios instance for every call:

- **Base URL** — `VITE_API_URL`, falling back to the legacy `VITE_API_BASE_URL`,
  then `http://localhost:8000`.
- **Request interceptor** — attaches `Authorization: Bearer <token>` when a token
  is stored in `localStorage` under `sqa_token`.
- **Response interceptor** — normalises `{detail: ...}` (string *or* FastAPI's
  validation array) into a plain `Error(message)` with a `status`, so callers can
  `catch (e) => toast.error(e.message)`. On 401 it clears the token and redirects
  to `/login?next=<current path>`, except when already on `/login` or `/register`.

### Auth and the award guardrail

`AuthProvider` mirrors the token into React state and validates it with
`GET /auth/me` on boot; `ProtectedRoute` waits for that check before rendering a
protected route, so a signed-in buyer never sees a login flash. Awarding a
supplier is the one action that is deliberately hard: it requires a chosen quote,
a decision and a mandatory note, and the comparison tab is the only caller of
`POST /rfqs/{id}/comparison/approve`.

### Data hooks

Every slice follows the same shape — `useState`/`useEffect`, no data-fetching
library: a fetch on mount, `loading`, an `error` string that is **also** toasted,
and an idempotent `refresh()`. Pages render a skeleton/spinner while loading, an
`EmptyState` when there is nothing, and the error message with a retry when the
request failed — never a blank screen.

### Status vocabulary (`shared/lib/status.js`)

One module maps every status string (RFQ lifecycle, invitation, completeness,
follow-up delivery, approval decision, supplier risk) to a `Badge` variant, with
small per-domain label overrides; `shared/components/StatusBadge.jsx` renders it.
Pages use these instead of picking their own colours, so "incomplete" is amber and
"overdue" is red everywhere.

### Formatting (`shared/lib/format.js`)

`formatPrice` / `formatDate` are unchanged for existing callers. Added:
`formatDateTime`, `formatRelativeTime` ("in 3 days", "2 hours ago"),
`formatNumber`, `formatPercent`, `formatHoursRemaining`, `formatLeadTime`,
`formatFieldKey`, and **`toNumber`** — the backend serialises Python `Decimal`
fields as JSON *strings*, so every numeric API value is parsed before it is
formatted, compared or summed. A missing value renders as an em dash, not `$NaN`.

### Theming (`index.css` + `shared/theme`)

A single set of **semantic CSS custom properties** flips between light and dark
under the `.dark` class and is surfaced to Tailwind via `@theme inline`, so the
whole UI re-themes by toggling one class on `<html>` — **no `dark:` variants in
markup**. `index.css` also carries the `@media print` block used by the
comparison tab's "Print / save as PDF", which hides the header, nav, footer,
buttons, tab bar and chat widget, forces the light palette, and stops wide tables
being clipped.

### Procurement assistant (chat)

`ChatProvider` sits above the router so the transcript survives navigation (it is
intentionally in-memory). `ChatWidget` renders a draggable launcher and a sliding
panel, and is mounted for authenticated buyers only. `POST /chat` may return a
`pending_email` draft, which the buyer must confirm before `POST /chat/email/send`
is called — nothing is sent to a supplier without a click.

---

## Running locally

### Prerequisites

- Node.js 22+
- The backend API running (see [../backend/README.md](../backend/README.md))

### 1. Install dependencies

```bash
npm install
```

### 2. Configure `frontend/.env`

```env
VITE_API_URL=http://localhost:8000
```

See [`.env.example`](.env.example). Point this at wherever the backend is
reachable. The dev server listens on `0.0.0.0:5173`.

### 3. Start the dev server

```bash
npm run dev
```

App runs at http://localhost:5173 (hot reload enabled).

---

## npm scripts

| Script             | Description                             |
| ------------------ | --------------------------------------- |
| `npm run dev`      | Start the Vite dev server (port 5173).   |
| `npm run build`    | Production build to `dist/`.             |
| `npm run preview`  | Serve the built bundle (port 4173).      |
| `npm run lint`     | Run ESLint.                              |
| `npm run lint:fix` | Run ESLint with autofix.                 |

---

## Deployment

### Vercel

The repository holds the backend and the frontend side by side, so the Vercel
project must set **Root Directory: `frontend`**. Then:

| Setting          | Value            |
| ---------------- | ---------------- |
| Framework preset | Vite             |
| Build command    | `npm run build`  |
| Output directory | `dist`           |
| Install command  | `npm install`    |

[`vercel.json`](vercel.json) rewrites every path to `/index.html` so client-side
routes (`/rfqs/12`, `/suppliers`) survive a refresh or a direct link instead of
404-ing on the static host.

Set `VITE_API_URL` as an environment variable on the project (Production and
Preview). **It is a build-time value** — Vite inlines `import.meta.env.*` when the
bundle is built, so changing it requires a redeploy.

### Docker / Nginx

`npm run build` outputs a static bundle to `dist/`. The [Dockerfile](Dockerfile)
builds it (Node 22) and serves it with Nginx ([`nginx.conf`](nginx.conf) rewrites
all routes to `index.html`), passing the API URL as the `VITE_API_URL` build arg.

---

## Conventions

- Import via the `@` alias (`@/features/...`, `@/shared/...`) instead of long
  relative paths.
- Keep new domains as feature slices under `src/features/`; put anything
  cross-cutting in `src/shared/`.
- Style with semantic Tailwind utilities and `shared/components/ui` primitives so
  light/dark stays consistent; map new statuses through `shared/lib/status.js`.
- Surface errors through Sonner toasts (`toast.error(error.message)`), relying on
  the client interceptor for the message, and always render a loading and an empty
  state.
- Wide tables scroll horizontally (`overflow-x-auto`) rather than squashing — the
  RFQ detail tables are meant to be scanned, not squeezed onto a phone.
- Never add a state-management or data-fetching library: hooks are plain
  `useState`/`useEffect`.
