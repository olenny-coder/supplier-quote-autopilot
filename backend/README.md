# Backend — Supplier Quote Comparison Tool

FastAPI service that powers RFQ/quote management, CSV/PDF import, and a multi-agent procurement assistant. It owns persistence (PostgreSQL via SQLAlchemy), request validation (Pydantic v2), and all LLM orchestration (LangChain / LangGraph → OpenAI).

---

## Tech stack

| Concern            | Choice                                            |
| ------------------ | ------------------------------------------------- |
| Language           | Python 3.13                                       |
| Web framework      | FastAPI + Uvicorn                                 |
| ORM / DB           | SQLAlchemy 2.x · PostgreSQL (psycopg 3 driver)    |
| Validation/config  | Pydantic v2 · pydantic-settings                   |
| AI                 | LangChain 1 · LangGraph 1 · langchain-openai      |
| Email              | Resend                                            |
| Tooling            | uv (deps + runner) · pytest · Docker              |

---

## Architecture

The app is organized as **feature slices** under `app/features/`, a shared **core**, and an **AI subsystem** under `app/ai/`. Routers stay thin; business logic lives in service classes; the domain layer raises framework-agnostic exceptions that are translated to HTTP at the edge.

```
app/
├── main.py                  # FastAPI app: lifespan (create tables), CORS, routers, /health
│
├── core/
│   ├── config.py            # Settings (env-driven) + cached settings singleton
│   ├── database.py          # engine, SessionLocal, Base, get_db() dependency
│   ├── dependencies.py      # DBSession = Annotated[Session, Depends(get_db)]
│   └── exceptions.py        # AppError hierarchy + FastAPI exception handlers
│
├── features/
│   ├── rfq/                 # router · service · model · schema
│   ├── quote/               # router · service · model · schema
│   │   └── importers/       # CSVImportService · PDFImportService
│   └── chat/                # router · service · schema · mailer (Resend wrapper)
│
└── ai/
    ├── llm.py               # get_llm() — single LLM factory (model, temperature, structured output)
    ├── registry.py          # name → agent callable; get_agent() / available_agents()
    └── agents/
        ├── rfq_assistant/          # Q&A scoped to a single RFQ
        ├── procurement_assistant/  # Q&A across the whole workspace (catalog formatting helpers)
        ├── procurement_orchestrator/  # entry point for site-wide chat; routes Q&A vs. email drafting
        ├── supplier_mailer/        # drafts a subject+body email (does not send)
        └── quote_extraction/       # LangGraph graph: PDF bytes → structured quotes
```

### Layering rules

- **Routers** (`*/router.py`) only parse/validate input and delegate to a service. They convert ORM models to response schemas where a computed field needs extra context (see `quote/router.py::build_quote_response`).
- **Services** (`*/service.py`) hold all DB access and business logic, and raise domain errors (`NotFoundError`, `BadRequestError`, `ExternalServiceError`) — never `HTTPException`.
- **`core/exceptions.py`** maps those domain errors to JSON responses, keeping the service layer HTTP-agnostic.
- **AI agents** never touch the database. The chat service gathers `(rfq, quotes)` data and hands it to an agent as plain context; agents only build prompts and call the LLM.

---

## AI subsystem

### LLM factory — `app/ai/llm.py`

A single `get_llm()` builds every chat model so model/provider config lives in one place. Default model is `gpt-4.1-mini` at `temperature=0`. Models are created **lazily** by callers (not at import time), so the app and tests import cleanly without an `OPENAI_API_KEY`. Pass `structured_output=<PydanticModel>` to bind a structured-output schema.

### Agent registry — `app/ai/registry.py`

Agents are registered by name and resolved through `get_agent(name)`, so callers (and the orchestrator) route by name instead of importing each agent module:

| Name                       | Entry point          | Role                                                                 |
| -------------------------- | -------------------- | ------------------------------------------------------------------- |
| `rfq_assistant`            | `answer_question`    | Answers questions about a **single** RFQ.                           |
| `procurement_assistant`    | `answer_question`    | Answers questions across the **whole** workspace, with history.    |
| `procurement_orchestrator` | `run`                | Site-wide chat entry point; decides between answering and emailing.|
| `supplier_mailer`          | `draft_email`        | Drafts a supplier email (subject + body) from buyer intent.        |

The `quote_extraction` LangGraph graph is invoked directly by the PDF importer rather than via the registry.

### Chat orchestration flow

`POST /chat` → `ChatService.answer_global` → `procurement_orchestrator.run`:

1. The orchestrator is given the full RFQ/quote catalog as grounded context plus the running conversation.
2. It is bound to a single tool, `DraftSupplierEmail`. If the model decides to email a supplier (and already has the recipient address), the tool call is **dispatched manually** to `supplier_mailer.draft_email`.
3. Drafting produces a subject/body but **sends nothing** — the draft is returned as `pending_email` for the buyer to confirm.
4. On confirmation, `POST /chat/email/send` calls `chat/mailer.py`, which sends via Resend (off the event loop). Without `RESEND_API_KEY` it raises a clear `ExternalServiceError`.

### PDF extraction

`PDFImportService` feeds the PDF bytes (base64) into the `quote_extraction` LangGraph graph, which calls the vision-capable LLM with a structured-output schema (`ExtractedQuotes`) and returns a list of quotes to persist.

---

## Running locally

### Prerequisites

- Python 3.13 and [uv](https://docs.astral.sh/uv/)
- A running PostgreSQL instance

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure `backend/.env`

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/supplier_quote_db

OPENAI_API_KEY=        # required for chat + PDF import
RESEND_API_KEY=        # required to send supplier emails
MAIL_FROM=Procurement Assistant <onboarding@resend.dev>
```

See [.env.example](.env.example). `OPENAI_API_KEY`/`RESEND_API_KEY` may be left blank to run the CRUD/CSV features; AI/email calls will surface a clear error until set.

### 3. Provision the database

Create a database named `supplier_quote_db` on your local PostgreSQL, or start one with Docker:

```bash
docker run --name supplier-quote-postgres-local \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=supplier_quote_db \
  -p 5432:5432 -d postgres:17
```

Tables are created automatically on startup from SQLAlchemy metadata — **no migration tool is configured.** Schema changes require recreating the tables.

### 4. Start the server

```bash
uv run uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## API reference

Interactive docs live at `/docs`. Summary:

### RFQs — `app/features/rfq`

| Method | Endpoint      | Description                          |
| ------ | ------------- | ------------------------------------ |
| GET    | `/rfqs`       | List all RFQs (newest first).        |
| POST   | `/rfqs`       | Create an RFQ.                        |
| GET    | `/rfqs/{id}`  | Get a single RFQ.                    |
| PUT    | `/rfqs/{id}`  | Update an RFQ (partial).             |
| DELETE | `/rfqs/{id}`  | Delete an RFQ (cascades to quotes).  |

### Supplier quotes — `app/features/quote`

| Method | Endpoint                     | Description                                       |
| ------ | ---------------------------- | ------------------------------------------------- |
| GET    | `/rfqs/{id}/quotes`          | List quotes for an RFQ (cheapest unit price first).|
| POST   | `/rfqs/{id}/quotes`          | Create a quote.                                   |
| POST   | `/rfqs/{id}/quotes/import`   | Import quotes from a CSV or PDF file (≤ 2 MB).    |
| PUT    | `/quotes/{id}`               | Update a quote (partial).                         |
| DELETE | `/quotes/{id}`               | Delete a quote.                                   |

Quote responses include a computed `total_price` (`unit_price × the RFQ's quantity`); comparison/ranking is based on it.

### Chat — `app/features/chat`

| Method | Endpoint              | Description                                                              |
| ------ | --------------------- | ----------------------------------------------------------------------- |
| POST   | `/chat`               | Site-wide assistant (whole catalog + history); may return `pending_email`.|
| POST   | `/chat/email/send`    | Send a supplier email the buyer confirmed in the chat.                   |
| POST   | `/rfqs/{id}/chat`     | Ask about a single RFQ.                                                  |

### Misc

| Method | Endpoint   | Description           |
| ------ | ---------- | --------------------- |
| GET    | `/health`  | Liveness check.       |

---

## File import

A single endpoint (`/rfqs/{id}/quotes/import`) accepts both formats and dispatches by extension. Max upload size is **2 MB**. Each importer returns `{ imported, failed, errors }`; valid rows are committed even when others fail.

### CSV format

```csv
supplier_name,unit_price,currency,lead_time,payment_terms,remarks
ABC Metals,10.50,USD,7,Net 30,High quality
XYZ Industries,9.75,USD,10,Advance Payment,Fast delivery
```

### PDF

PDFs are parsed by the `quote_extraction` agent (vision LLM, structured output) — no fixed template required, but extraction quality depends on the document. Requires `OPENAI_API_KEY`.

---

## Data model

```
RFQ (rfqs)                         SupplierQuote (supplier_quotes)
├── id                             ├── id
├── item_name                      ├── rfq_id  ─── FK → rfqs.id (ON DELETE CASCADE)
├── specification                  ├── supplier_name
├── quantity                       ├── unit_price   (Numeric 12,2)
├── delivery_expectation (date)    ├── currency
├── notes (nullable)               ├── lead_time    (days)
└── quotes ──┐ 1─*                 ├── payment_terms (nullable)
             └──────────────────▶  └── remarks       (nullable)
```

`total_price` is **not stored** — it is computed per response as `unit_price × rfq.quantity`.

---

## Testing

```bash
uv run pytest
```

Tests run against an **in-memory SQLite** database (`tests/conftest.py`) with a fresh schema per test, so no PostgreSQL or API keys are required. Suites: `test_rfq.py`, `test_quote.py`, `test_csv_import.py`, `test_chat.py`.

---

## Configuration reference

All settings are loaded from the environment (and `backend/.env`) via `app/core/config.py`:

| Setting           | Default                                              | Notes                                              |
| ----------------- | ---------------------------------------------------- | -------------------------------------------------- |
| `APP_NAME`        | `Supplier Quote Comparison Tool`                     | Shown in OpenAPI metadata.                         |
| `DATABASE_URL`    | — (required)                                          | SQLAlchemy URL.                                    |
| `OPENAI_API_KEY`  | `""`                                                 | Needed for chat + PDF import.                      |
| `RESEND_API_KEY`  | `""`                                                 | Needed to send supplier emails.                    |
| `MAIL_FROM`       | `Procurement Assistant <onboarding@resend.dev>`      | From-address for emails.                           |
| `ALLOWED_ORIGINS` | `["*"]`                                               | Comma-separated origins for CORS.                  |

---

## Extending

- **Add a feature slice:** create `app/features/<name>/` with `router.py`, `service.py`, `schema.py`, and (if persisted) `model.py`; register the router in `app/main.py`. Raise domain errors from the service, not `HTTPException`.
- **Add an AI agent:** create `app/ai/agents/<name>/`, expose an entry-point callable, register it in `app/ai/registry.py`, and build its model through `get_llm()`.
