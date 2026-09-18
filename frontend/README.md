# Frontend — Supplier Quote Comparison Tool

React single-page app for creating RFQs, managing and comparing supplier quotes, importing quotes from CSV/PDF, and chatting with the procurement assistant. Built with Vite and styled with Tailwind CSS v4 using a token-driven light/dark theme.

---

## Tech stack

| Concern        | Choice                                            |
| -------------- | ------------------------------------------------- |
| Framework      | React 19                                          |
| Build tool     | Vite 7                                            |
| Styling        | Tailwind CSS 4 (`@tailwindcss/vite`)              |
| Routing        | React Router 7                                    |
| HTTP           | Axios (shared client with error interceptor)      |
| Markdown       | react-markdown + remark-gfm (chat rendering)      |
| Toasts         | Sonner                                            |
| Lint           | ESLint 9                                          |

JavaScript + JSX (no TypeScript). The `@` alias maps to `src/` (configured in `vite.config.js` and `jsconfig.json`).

---

## Project structure

The app is organized into **feature slices** (`src/features/*`) and cross-cutting **shared** modules (`src/shared/*`). A feature owns its API calls, hooks, and components; shared holds the API client, UI primitives, layout, and theming.

```
src/
├── main.jsx                 # entry: ThemeProvider → Router → ChatProvider → App + Toaster
├── App.jsx                  # layout shell, routes, footer, ChatWidget mount
├── index.css                # Tailwind import + semantic design tokens (light/dark)
│
├── features/
│   ├── rfq/
│   │   ├── api.js           # RFQ HTTP calls
│   │   ├── hooks.js         # useRFQs / useRFQ (fetch + loading + error toast)
│   │   ├── components/      # RFQCard, RFQForm
│   │   └── pages/           # RFQListPage, CreateRFQPage, RFQDetailsPage
│   ├── quote/
│   │   ├── api.js           # quote CRUD + import (CSV/PDF) calls
│   │   ├── hooks.js         # useQuotes + useQuoteTable (search/sort/best-quote view-model)
│   │   └── components/      # QuoteTable, QuoteForm, FileImport, QuoteTableToolbar
│   └── chat/
│       ├── api.js           # /chat + /chat/email/send calls
│       ├── ChatContext.js   # React context
│       ├── ChatProvider.jsx # site-wide conversation state (above the router)
│       ├── useChat.js        # context hook
│       ├── useDockedLauncher.js  # draggable, side-docking launcher behavior
│       └── components/      # ChatWidget, EmailConfirmCard, Markdown, AgentIcon
│
└── shared/
    ├── api/client.js        # axios instance; normalizes backend errors to Error(message)
    ├── components/          # Modal, ConfirmModal, Loading, EmptyState, ui/ primitives
    ├── layout/Header.jsx    # top nav + theme toggle
    ├── lib/format.js        # formatting helpers
    └── theme/               # ThemeProvider, ThemeToggle, ThemedToaster
```

### Routes

| Path          | Page              | Purpose                                   |
| ------------- | ----------------- | ----------------------------------------- |
| `/`           | `RFQListPage`     | List all RFQs.                            |
| `/rfqs/new`   | `CreateRFQPage`   | Create an RFQ.                            |
| `/rfqs/:id`   | `RFQDetailsPage`  | RFQ detail, quote table, import, compare. |
| `*`           | →  `/`            | Unknown paths redirect to the list.       |

---

## Key concepts

### API client (`shared/api/client.js`)

A single Axios instance reads the backend base URL from `VITE_API_BASE_URL` (default `http://localhost:8000`). A response interceptor unwraps the backend's `{ detail }` error shape into a plain `Error(message)`, so feature code can `catch (e) => toast.error(e.message)` uniformly.

### Data hooks

Feature hooks (`useRFQs`, `useRFQ`, `useQuotes`) encapsulate the fetch + loading + error-toast pattern and expose a `refresh()`. `useQuoteTable` is a pure client-side view-model over a quote list: it handles search filtering, column sorting, and best-quote detection (lowest `total_price`), keeping `QuoteTable` presentational.

### Theming (`index.css` + `shared/theme`)

Theming uses a single set of **semantic CSS custom properties** (e.g. `--surface`, `--content`, `--primary`) that flip values under the `.dark` class. They're surfaced to Tailwind via `@theme inline`, generating utilities like `bg-surface` / `text-content` that resolve to the live variable. The result: the whole UI re-themes by toggling one class on `<html>` — **no `dark:` variants scattered through markup.**

`ThemeProvider` picks the initial theme from `localStorage` (falling back to the OS `prefers-color-scheme`), persists explicit choices, and follows OS changes until the user overrides. When styling, **reuse the semantic utilities and the `shared/components/ui` primitives** rather than hard-coded colors.

### Procurement assistant (chat)

`ChatProvider` sits above the router so the transcript and open/closed state survive navigation (it is intentionally in-memory — a full refresh starts a new conversation). `ChatWidget` renders a draggable launcher that docks to either screen edge (`useDockedLauncher`) and a sliding panel.

The conversation flow:

1. `ask()` posts the question plus prior turns to `POST /chat`; assistant replies render as GitHub-flavored Markdown.
2. If the response includes a `pending_email` draft, an `EmailConfirmCard` is shown. The buyer reviews it and chooses **Send** (`POST /chat/email/send`) or **Cancel** — nothing is sent without confirmation. The card stays actionable so a failed send can be retried.

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
VITE_API_BASE_URL=http://localhost:8000
```

Point this at wherever the backend is reachable. With the default Vite proxy config the dev server listens on `0.0.0.0:5173`.

### 3. Start the dev server

```bash
npm run dev
```

App runs at http://localhost:5173 (hot reload enabled).

---

## npm scripts

| Script             | Description                              |
| ------------------ | ---------------------------------------- |
| `npm run dev`      | Start the Vite dev server (port 5173).  |
| `npm run build`    | Production build to `dist/`.            |
| `npm run preview`  | Serve the built bundle (port 4173).    |
| `npm run lint`     | Run ESLint.                             |
| `npm run lint:fix` | Run ESLint with autofix.               |

---

## Production build & Docker

`npm run build` outputs a static bundle to `dist/`. The [Dockerfile](Dockerfile) builds it (Node 22) and serves it with Nginx (`nginx.conf` rewrites all routes to `index.html` for client-side routing).

> **`VITE_API_BASE_URL` is a build-time value.** Vite inlines `import.meta.env.*` at build, so the API URL is fixed when the bundle/image is built. In Docker it is passed as the `VITE_API_BASE_URL` build arg (see `docker-compose.yml`); changing it requires a rebuild.

---

## Conventions

- Import via the `@` alias (`@/features/...`, `@/shared/...`) instead of long relative paths.
- Keep new domains as feature slices under `src/features/`; put anything cross-cutting in `src/shared/`.
- Style with semantic Tailwind utilities and `shared/components/ui` primitives so light/dark stays consistent.
- Surface errors through Sonner toasts (`toast.error(error.message)`), relying on the client interceptor for messages.
