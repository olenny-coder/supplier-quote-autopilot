# Supplier Quote Comparison Tool

A full-stack application for running **Request for Quotations (RFQs)** and comparing supplier quotes side by side. Procurement teams create RFQs, collect quotes (typed in, or imported from CSV/PDF), and rank them by total cost — with an AI procurement assistant that answers questions about the catalog and drafts supplier emails on request.

| Layer        | Stack                                                                 |
| ------------ | --------------------------------------------------------------------- |
| **Backend**  | FastAPI · SQLAlchemy 2 · PostgreSQL · LangChain / LangGraph · OpenAI  |
| **Frontend** | React 19 · Vite 7 · Tailwind CSS 4 · React Router 7                    |
| **Infra**    | Docker Compose · GitHub Actions CI/CD · Nginx · Resend (email)        |

---

## Table of Contents

- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Feature overview](#feature-overview)
- [Quick start (Docker)](#quick-start-docker)
- [Local development](#local-development)
- [Environment variables](#environment-variables)
- [CI/CD](#cicd)
- [Further reading](#further-reading)

---

## Architecture

```
┌──────────────────────┐        HTTP/JSON         ┌────────────────────────┐
│   Frontend (React)   │  ───────────────────────▶ │   Backend (FastAPI)    │
│   Vite + Tailwind    │   VITE_API_BASE_URL       │   feature-slice API    │
│   served by Nginx    │ ◀───────────────────────  │                        │
└──────────────────────┘                            └───────────┬────────────┘
                                                                 │
                                       ┌─────────────────────────┼───────────────────────┐
                                       │                         │                       │
                                 ┌─────▼──────┐         ┌────────▼────────┐      ┌────────▼────────┐
                                 │ PostgreSQL │         │  app/ai agents  │      │     Resend      │
                                 │  (quotes)  │         │ LangChain/Graph │      │  (email send)   │
                                 └────────────┘         │  → OpenAI API   │      └─────────────────┘
                                                        └─────────────────┘
```

Both services are independently runnable and containerized. The frontend talks to the backend purely over HTTP using a configurable base URL; the backend owns persistence, validation, and all AI orchestration.

---

## Repository layout

```
rfq-comparison-tool/
├── backend/                 # FastAPI service (see backend/README.md)
│   ├── app/
│   │   ├── core/            # config, DB, dependencies, exception handling
│   │   ├── features/        # rfq / quote / chat feature slices
│   │   └── ai/              # LLM factory, agent registry, agents
│   └── tests/               # pytest suite (in-memory SQLite)
├── frontend/                # React SPA (see frontend/README.md)
│   └── src/
│       ├── features/        # rfq / quote / chat feature slices
│       └── shared/          # api client, UI primitives, theme, layout
├── docker-compose.yml       # postgres + backend + frontend
├── .github/workflows/       # CI/CD pipeline
└── .env.example             # root env used by docker-compose
```

The codebase follows a **feature-slice** convention on both ends — each domain (RFQ, quote, chat) keeps its router/model/schema/service (backend) or api/hooks/components (frontend) together rather than splitting by technical layer.

---

## Feature overview

- **RFQ management** — create, view, update, delete RFQs.
- **Supplier quotes** — add/edit/delete quotes per RFQ; quotes are compared on **total price** (`unit_price × RFQ quantity`) and the cheapest is highlighted.
- **Bulk import** — upload supplier quotes from **CSV** (parsed directly) or **PDF** (extracted by a vision-capable LLM via a LangGraph agent).
- **Procurement assistant** — a site-wide chat widget backed by a multi-agent orchestrator that answers questions about every RFQ/quote and can **draft a supplier email**, which the buyer reviews and confirms before it is sent via Resend.
- **Theming** — class-based light/dark mode driven by semantic design tokens.

---

## Quick start (Docker)

The fastest way to run the whole stack. Requires **Docker** and **Docker Compose**.

```bash
# 1. Create the root env file and fill in secrets
cp .env.example .env
#    → set POSTGRES_PASSWORD, OPENAI_API_KEY, and (for email) RESEND_API_KEY

# 2. Build and start postgres + backend + frontend
docker compose up --build
```

| Service     | URL                            |
| ----------- | ------------------------------ |
| Frontend    | http://localhost:5173          |
| Backend API | http://localhost:8000          |
| Swagger UI  | http://localhost:8000/docs     |
| Healthcheck | http://localhost:8000/health   |

Ports are configurable via `FRONTEND_PORT`, `BACKEND_PORT`, and `POSTGRES_PORT` in `.env`.

```bash
docker compose down       # stop the stack
docker compose down -v     # stop and drop the postgres volume
```

> **Note:** `VITE_API_BASE_URL` is baked into the frontend image **at build time** (it is a Vite build arg). If you change it, rebuild the frontend image.

---

## Local development

Run each side natively for hot reload. See the per-service READMEs for the full walkthrough:

- **[backend/README.md](backend/README.md)** — `uv sync` → configure `backend/.env` → `uv run uvicorn app.main:app --reload`
- **[frontend/README.md](frontend/README.md)** — `npm install` → configure `frontend/.env` → `npm run dev`

The backend defaults to a locally installed PostgreSQL on `localhost:5432`; the frontend dev server runs on `http://localhost:5173` and proxies API calls to `VITE_API_BASE_URL` (default `http://localhost:8000`).

---

## Environment variables

The **root `.env`** is consumed by `docker-compose.yml`. For native local development each service also reads its own `backend/.env` / `frontend/.env`.

| Variable            | Used by             | Description                                                            |
| ------------------- | ------------------- | --------------------------------------------------------------------- |
| `POSTGRES_USER`     | postgres, DB URL    | Database username.                                                     |
| `POSTGRES_PASSWORD` | postgres, DB URL    | Database password.                                                     |
| `POSTGRES_DB`       | postgres, DB URL    | Database name (`supplier_quote_db`).                                   |
| `POSTGRES_PORT`     | docker-compose      | Host port mapped to postgres `5432`.                                  |
| `DATABASE_URL`      | backend             | SQLAlchemy URL, e.g. `postgresql+psycopg://user:pass@postgres:5432/db`.|
| `OPENAI_API_KEY`    | backend (AI)        | Required for chat and PDF extraction.                                  |
| `RESEND_API_KEY`    | backend (email)     | Required to actually send supplier emails; drafting works without it.  |
| `MAIL_FROM`         | backend (email)     | From-address for supplier emails.                                      |
| `ALLOWED_ORIGINS`   | backend (CORS)      | Comma-separated allowed origins.                                       |
| `BACKEND_PORT`      | docker-compose      | Host port mapped to backend `8000`.                                  |
| `FRONTEND_PORT`     | docker-compose      | Host port mapped to frontend `80`.                                   |
| `VITE_API_BASE_URL` | frontend (build)    | Backend base URL baked into the frontend bundle.                      |

See [.env.example](.env.example) for a starting point.

---

## CI/CD

[`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml) runs on every push/PR to `main`:

1. **Backend** — `uv sync` then `uv run pytest` (against in-memory SQLite, no external services needed).
2. **Frontend** — `npm ci` then `npm run build`.
3. **Deploy** — on push to `main` only: SSH into the VPS, `git reset --hard origin/main`, and `docker compose up --build -d`.

---

## Further reading

- [backend/README.md](backend/README.md) — API reference, AI agent architecture, importers, testing.
- [frontend/README.md](frontend/README.md) — feature-slice structure, theming system, chat widget.
