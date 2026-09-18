# Supplier Quote Autopilot

Run a request for quotation, hand every supplier their own private web form, watch
who has answered, chase the gaps automatically, and compare what comes back on
**landed cost** rather than headline unit price — then decide, as a human, who wins.

Built on top of [`rfq-comparison-tool`](INTEGRATION_PLAN.md) and extended with
concepts from [ForgeFlow](https://github.com/JayleeBot/ForgeFlow). See
[INTEGRATION_PLAN.md](../INTEGRATION_PLAN.md) for exactly what was reused, adapted,
or reimplemented, and the license position for each.

| Layer | Stack |
| --- | --- |
| **Backend** | FastAPI · SQLAlchemy 2 · PostgreSQL (Neon) · Alembic |
| **Buyer dashboard** | React 19 · Vite 7 · Tailwind CSS 4 · React Router 7 |
| **Supplier form** | React 19 · Vite 7 · Tailwind CSS 4 (separate app, no login) |
| **AI** | Any OpenAI-compatible provider — Groq by default (free tier) |
| **Email** | HTTPS API only — Resend / SendGrid / Mailgun / Brevo. **No SMTP.** |
| **Files** | Local filesystem in dev · any S3-compatible store in production |
| **Infra** | Docker Compose · GitHub Actions · Neon + Render + Vercel (all free tier) |

---

## Table of contents

1. [What it does](#1-what-it-does)
2. [Quick start (Docker)](#2-quick-start-docker)
3. [Local development without Docker](#3-local-development-without-docker)
4. [Free LLM provider setup](#4-free-llm-provider-setup)
5. [Deployment: Neon + Render + Vercel](#5-deployment-neon--render--vercel)
6. [Free-tier limits and the workarounds built for them](#6-free-tier-limits-and-the-workarounds-built-for-them)
7. [Keeping the free tier alive](#7-keeping-the-free-tier-alive)
8. [Architecture](#8-architecture)
9. [Configuration reference](#9-configuration-reference)
10. [API](#10-api)
11. [Testing](#11-testing)
12. [Demo data](#12-demo-data)
13. [Guardrails and deliberate limitations](#13-guardrails-and-deliberate-limitations)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. What it does

**For the buyer**

- Create an RFQ with an item, specification, quantity, unit, currency, Incoterms and
  a submission deadline, and pick which fields a quote must contain to count as complete.
- Add suppliers inline or from a directory; each one instantly gets a **unique
  tokenized web-form link**.
- See at a glance who is `Pending`, who has `Submitted`, whose quote is `Incomplete`,
  and which links have `Expired` — including whether a supplier **opened the form
  without submitting**.
- Let the follow-up engine chase non-responders and suppliers who left fields blank.
  Reminders are drafted (optionally by an LLM) and, by default, queued for your
  approval before anything is sent.
- Compare every quote side by side after normalizing currency, unit of measure and
  Incoterms, with a landed-cost breakdown and a weighted score across price, lead
  time, payment terms, MOQ, validity, warranty and supplier risk.
- Export the comparison as CSV or PDF, and record an award decision with a reason.
  **Nothing is ever auto-awarded.**

**For the supplier**

- Open a link. No account, no sign-up, no app.
- See exactly who is asking, for what, and by when.
- Enter price, currency, lead time, MOQ, payment terms, Incoterms, validity,
  warranty, additional costs and notes; attach a spec sheet or brochure.
- Get a confirmation page with a reference number and the buyer's contact details.

**The supplier form is custom-built.** No Microsoft Forms, no Power Automate, no
third-party form service.

---

## 2. Quick start (Docker)

Requires Docker and Docker Compose. Nothing else.

```bash
git clone <your-repo-url> supplier-quote-autopilot
cd supplier-quote-autopilot

cp .env.example .env
# Minimum viable edit: set SECRET_KEY.
#   python -c "import secrets; print(secrets.token_urlsafe(48))"
# Everything else has a working default; EMAIL_PROVIDER=console logs mail instead
# of sending it, and an empty LLM_API_KEY uses the deterministic AI fallbacks.

docker compose up --build
```

| Service | URL |
| --- | --- |
| Buyer dashboard | http://localhost:5173 |
| Supplier quote form | http://localhost:5174/quote/`<rfq_id>`/`<token>` |
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Health | http://localhost:8000/health |

Then create an account, or load the demo workspace — `docker compose exec backend
uv run python -m scripts.seed_demo` — which prints a working supplier link and the
demo login.

Optional extras:

```bash
docker compose --profile s3 up      # adds MinIO on :9000 (console :9001) so the
                                    # production upload path can be exercised locally
docker compose exec backend uv run alembic upgrade head   # apply migrations manually
docker compose exec backend uv run pytest                 # run the test suite
docker compose down          # stop
docker compose down -v       # stop and delete the database volume
```

---

## 3. Local development without Docker

You need PostgreSQL (the Docker service is fine: `docker compose up postgres`), plus
[`uv`](https://docs.astral.sh/uv/) and Node 22.

### Backend

```bash
cd backend
cp .env.example .env          # DATABASE_URL already points at localhost:5432
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

> **Import layout.** The repository keeps three importable top-level packages —
> `backend/`, `agents/`, `comparison/` — and `backend/app/__init__.py` puts the
> repository root on `sys.path`. That means `uv run …` from `backend/` works with no
> `PYTHONPATH` configuration. If you run Python from somewhere else, add the repo
> root to `PYTHONPATH` yourself.

### Buyer dashboard

```bash
cd frontend
npm install
echo "VITE_API_URL=http://localhost:8000" > .env
npm run dev                   # http://localhost:5173
```

### Supplier form

```bash
cd public_form
npm install
echo "VITE_API_URL=http://localhost:8000" > .env
npm run dev                   # http://localhost:5174
```

### Tests

```bash
cd backend && uv run pytest -q
```

---

## 4. Free LLM provider setup

The AI layer is **optional by design**: with no key configured, quote parsing,
follow-up drafting and the comparison narrative all fall back to deterministic
implementations and the product works end to end. A key makes the copy more fluent
and the parsing more tolerant; it never gates a feature.

The client is OpenAI-compatible, so switching providers means changing **three
environment variables**:

```
LLM_BASE_URL=…
LLM_API_KEY=…
LLM_MODEL=…
```

### Option A — Groq (default; recommended)

Fastest of the three and generous limits.

1. Sign up at <https://console.groq.com> (no credit card).
2. **API Keys → Create API Key**, copy it.
3. Set:

```env
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
LLM_API_KEY=gsk_…
```

**Free-tier limits:** roughly **30 requests/minute** and **14,400 requests/day** per
model. Context window varies by model.

### Option B — OpenRouter

20+ permanently free models, including Llama 3.3 70B, Gemma 3 27B, Mistral Small and
Qwen 3 Coder. Use the `:free` suffix.

1. Sign up at <https://openrouter.ai>.
2. **Keys → Create Key**, copy it.
3. Set:

```env
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=deepseek/deepseek-r1:free
LLM_API_KEY=sk-or-v1-…
```

**Free-tier limits:** model-dependent request and daily caps (commonly 50 requests/day
without credit, 1,000/day with a one-time credit purchase). `:free` models are shared
and can return 429 under load — the client retries with backoff.

### Option C — Google Gemini

Exposes an OpenAI-compatible endpoint.

1. Sign up at <https://aistudio.google.com>.
2. **Get API key**, copy it.
3. Set:

```env
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=gemini-2.0-flash
LLM_API_KEY=AIza…
```

**Free-tier limits:** per-minute and per-day request caps that vary by model (Gemini
2.0 Flash is roughly 15 requests/minute and 1,500 requests/day).
⚠️ **Note:** the free tier is **not available in the EU, UK or Switzerland**, and
Google may use free-tier prompts to improve its products. Do not send confidential
pricing through it without checking your obligations.

### How the client respects those limits

Rate limits are the reason most free-tier integrations look fine in a demo and break
in use. `backend/app/core/llm_client.py` handles them:

| Guard | Setting | What it does |
| --- | --- | --- |
| Request spacing | `LLM_REQUESTS_PER_MINUTE` | A sliding window of recent call timestamps. When the window is full, the *caller waits* instead of collecting a 429. |
| Concurrency cap | `LLM_MAX_CONCURRENCY` | Bounds in-flight requests so a batch cannot stampede. |
| Retry with backoff | `LLM_MAX_RETRIES` | Exponential backoff with jitter on 429 and 5xx, honouring the provider's `Retry-After` when present. |
| Fail-fast on real errors | — | A non-429 4xx (bad key, bad model id) is **not** retried — it cannot succeed, and retrying burns quota. |
| Batch ceiling | `LLM_BATCH_MAX_CALLS` | A scheduler sweep stops issuing LLM calls after this many, so a backlog cannot consume a whole day's quota in one pass. |
| Graceful degradation | — | Every call site catches the unavailable error and uses the deterministic path. An exhausted quota degrades the product; it does not break it. |

**Practical sizing.** One quote submission costs at most one LLM call (parsing), one
follow-up costs at most one (drafting), and one comparison costs at most one
(narrative). At 30/minute and 14,400/day, Groq comfortably covers a small
procurement team. If you batch-import hundreds of quotes, raise
`LLM_REQUESTS_PER_MINUTE` only up to what your tier actually allows — the client
cannot make the provider more generous, it can only stop you from being rude.

---

## 5. Deployment: Neon + Render + Vercel

Everything below fits in the free tier of all three services. Total cost: **$0**.
Total credit cards required: **0**.

```
   ┌──────────────┐   ┌──────────────┐
   │  Vercel      │   │  Vercel      │
   │  frontend/   │   │  public_form/│
   │  (dashboard) │   │  (suppliers) │
   └──────┬───────┘   └──────┬───────┘
          │   HTTPS          │
          └────────┬─────────┘
                   ▼
            ┌──────────────┐        ┌──────────────┐
            │  Render      │───────▶│  Neon        │
            │  backend/    │ pooled │  PostgreSQL  │
            │  FastAPI     │◀───────│              │
            └──┬────────┬──┘ direct └──────────────┘
               │        │
               ▼        ▼
        ┌──────────┐ ┌──────────────────┐
        │ HTTPS    │ │ S3-compatible    │
        │ email API│ │ object storage   │
        └──────────┘ └──────────────────┘
                     + free OpenAI-compatible LLM
```

### Step 1 — Neon (database)

1. Sign up at <https://neon.tech> (no credit card) and create a project.
2. Neon gives you **two** connection strings. Copy both:
   - **Pooled** — the hostname contains `-pooler`. This is `DATABASE_URL`.
   - **Direct** — no `-pooler`. This is `DATABASE_URL_DIRECT`, used only by Alembic.
3. Append `?sslmode=require` to both.

```
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@ep-xxx-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require
DATABASE_URL_DIRECT=postgresql+psycopg://USER:PASSWORD@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
```

> **Why two strings.** Neon's pooled endpoint runs PgBouncer in *transaction* mode.
> The app loves it — many short-lived sessions, low connection count. Alembic's DDL
> and its `alembic_version` bookkeeping do not tolerate it reliably. Using the direct
> string for migrations is the supported path. Locally, leave `DATABASE_URL_DIRECT`
> empty and it falls back to `DATABASE_URL`.

**Free tier:** 20 projects, 0.5 GB storage per project, 100 CU-hours/month compute,
5 GB outbound transfer/month. Compute **scales to zero after 5 idle minutes**, so the
first request after a quiet period takes a few seconds while it cold-starts. `/health`
reports the database state so a cold start is distinguishable from an outage.

### Step 2 — Push to GitHub

```bash
git init
git add .
git commit -m "Supplier Quote Autopilot"
git remote add origin git@github.com:YOU/supplier-quote-autopilot.git
git push -u origin main
```

Confirm `.env` was **not** committed (`.gitignore` covers it; `.env.example` is safe).

### Step 3 — Render (backend API)

**Option A — Blueprint (recommended).** `render.yaml` is committed at the repo root
and provisions the service with every variable pre-declared.

1. Render dashboard → **New → Blueprint** → connect the repo.
2. Render reads `render.yaml`. Fill in the variables marked `sync: false`:
   `DATABASE_URL`, `DATABASE_URL_DIRECT`, `BACKEND_URL`, `FRONTEND_URL`,
   `PUBLIC_FORM_URL`, `ALLOWED_ORIGINS`, `LLM_API_KEY`, `EMAIL_API_KEY`, `MAIL_FROM`,
   and the `S3_*` values.
3. `SECRET_KEY` and `SCHEDULER_SECRET` are auto-generated — read them from the
   dashboard afterwards; you need `SCHEDULER_SECRET` for the cron.
4. Deploy.

**Option B — manual Web Service.** New → **Web Service** → connect the repo, then:

| Setting | Value |
| --- | --- |
| Root Directory | `backend` |
| Runtime | Python 3 |
| Build Command | `pip install --upgrade pip && pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |
| Plan | Free |

Add every variable from the [configuration reference](#9-configuration-reference).
At minimum: `ENV=production`, the two database URLs, `SECRET_KEY`, `LLM_BASE_URL`,
`LLM_API_KEY`, `LLM_MODEL`, `EMAIL_PROVIDER`, `EMAIL_API_KEY`, `MAIL_FROM`,
`STORAGE_BACKEND=s3` plus the `S3_*` values, `BACKEND_URL`, `FRONTEND_URL`,
`PUBLIC_FORM_URL`, `ALLOWED_ORIGINS`, `SCHEDULER_SECRET`.

> **`requirements.txt` is generated, not hand-written.** It is produced from
> `uv.lock` by
> `uv export --format requirements-txt --no-dev --no-hashes --no-emit-project -o requirements.txt`
> and CI fails if the two drift. Rendering the lock out means Render can use the plain
> `uvicorn …` start command with no virtualenv indirection. If you change a
> dependency, change it in `pyproject.toml`, then regenerate.

### Step 4 — Run migrations against the direct connection string

Run once, from your machine (or a Render shell):

```bash
cd backend
DATABASE_URL="<direct string>" DATABASE_URL_DIRECT="<direct string>" uv run alembic upgrade head
```

`alembic/env.py` reads `DATABASE_URL_DIRECT` first, so setting only that is enough:

```bash
DATABASE_URL_DIRECT="postgresql+psycopg://…@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require" \
  uv run alembic upgrade head
```

> The app also runs `Base.metadata.create_all` at startup, so a first boot works with
> no manual step. That is a convenience, not the source of truth: `create_all` only
> ever *adds* missing tables and never alters or drops, so it cannot conflict with
> Alembic. Once you have migrations, Alembic is the authority.

### Step 5 — Vercel (both frontends)

Two separate Vercel projects, because suppliers must reach a different origin from
buyers (and eventually a different domain).

**Buyer dashboard**

1. Vercel → **Add New → Project** → import the repo.
2. **Root Directory:** `frontend`
3. Framework preset: Vite (auto-detected).
4. Environment variable: `VITE_API_URL` = your Render URL, e.g.
   `https://supplier-quote-autopilot-api.onrender.com`.
5. Deploy. `frontend/vercel.json` handles SPA routing so a deep link like
   `/rfqs/12` does not 404.

**Supplier form**

Repeat with **Root Directory:** `public_form`, the same `VITE_API_URL`, and its own
project name. `public_form/vercel.json` handles its routing.

> ⚠️ **Vite variables are baked in at build time.** Changing `VITE_API_URL` requires a
> redeploy, not just an env-var edit.

### Step 6 — Point everything at everything

Back on Render, set and redeploy:

```env
BACKEND_URL=https://supplier-quote-autopilot-api.onrender.com
FRONTEND_URL=https://supplier-quote-autopilot.vercel.app
PUBLIC_FORM_URL=https://quote-autopilot-form.vercel.app
ALLOWED_ORIGINS=https://supplier-quote-autopilot.vercel.app,https://quote-autopilot-form.vercel.app
```

`PUBLIC_FORM_URL` matters more than it looks: it is what the invitation email puts in
front of the supplier. Get it wrong and every link 404s.

CORS must list the Vercel origins exactly — scheme included, no trailing slash. A
wildcard `*` works but is not appropriate for production, and the app logs a warning
when `ENV=production` and `ALLOWED_ORIGINS` contains one.

### Step 7 — Verify end to end

```bash
# 1. API is up
curl https://YOUR-API.onrender.com/health | jq

# 2. Register, then create an RFQ with three suppliers (see docs/API.md for the body)
# 3. Open the buyer dashboard, sign in
# 4. Copy a supplier link, open it on your phone
# 5. Submit a quote, confirm the reference number appears
# 6. Back in the dashboard: the quote is there, and the comparison recommends a winner
```

The `/health` payload tells you which optional pieces are live:

```json
{
  "status": "ok",
  "database": { "connected": true },
  "storage":  { "backend": "s3", "ok": true },
  "llm":      { "configured": true, "provider": "groq", "model": "llama-3.3-70b-versatile" },
  "email":    { "provider": "resend", "transport": "https-api", "smtp_used": false },
  "scheduler":{ "running": true, "external_tick_enabled": true, "auto_send_followups": false }
}
```

---

## 6. Free-tier limits and the workarounds built for them

Everything in this section is enforced by code, not by convention.

### Render free tier

| Limit | Consequence | What this project does |
| --- | --- | --- |
| **512 MB RAM, 0.1 CPU** | Heavy processes get OOM-killed. | No pandas, no Celery, no headless browser. Object storage is imported lazily so the local backend and the tests never load `boto3`. |
| **Spins down after 15 min idle; ~1 min cold start** | The first request after a quiet period is slow. | `/health` always returns 200 so a keep-alive ping counts as "up". See [§7](#7-keeping-the-free-tier-alive). |
| **750 instance hours/month** | A background worker or cron job would be a *second* billable service and blow the budget. | The follow-up scheduler runs **inside the web process**, and the same work is exposed at `POST /internal/scheduler/tick` for a free external cron. No worker, no Render cron job. |
| **No persistent disk** | Anything written locally is lost on the next deploy. | `STORAGE_BACKEND=s3` in production. `render.yaml` sets it; the app logs a loud warning if `local` is used with `ENV=production`. |
| **Outbound SMTP ports 25/465/587 are BLOCKED** | Any SMTP client fails at connect time. | There is **no SMTP code path**. `app/core/email.py` speaks HTTPS to Resend/SendGrid/Mailgun/Brevo. A test and a CI step assert that `smtplib` never appears in the source. |
| **Free Render Postgres expires after 30 days** | The database disappears a month after creation. | Postgres is Neon, not Render. Render stores nothing stateful. |
| **Build minutes and repo size** | Slow builds. | `requirements.txt` is generated from the lockfile so the build is a plain `pip install` with no resolver work. |

### Neon free tier

| Limit | Consequence | What this project does |
| --- | --- | --- |
| **Scale to zero after 5 min idle** | First query after idle takes seconds. | `pool_pre_ping=True` plus `pool_recycle=300` so a dead socket is never handed to a request. `/health` reports the database state explicitly. |
| **0.5 GB storage** | Large tables matter. | JSON columns instead of child tables where the data is a snapshot (scoring results, cost breakdowns); uploads go to object storage, never the database. |
| **Connection limits** | Too many connections get rejected. | The **pooled** string for the app (`pool_size` 5, `max_overflow` 5), the **direct** string only for migrations. |
| **100 CU-hours/month** | Sustained CPU burns the allowance. | Indexes on every column the app filters by; list endpoints use bulk counter queries instead of N+1. |

### Vercel free tier

| Limit | Consequence | What this project does |
| --- | --- | --- |
| **100 GB bandwidth/month** | Enough for an MVP. | Two small SPAs, no large assets, supplier form uses plain `fetch`. |
| **10 s serverless function timeout (Hobby)** | A slow API call inside a Vercel function would be killed. | **Both frontends are static sites.** Every API route, including the long-running ones (comparison with an LLM narrative, PDF import, follow-up sweeps), lives on Render. There is no `api/` directory in either app. |
| **No commercial usage on the Hobby plan** | Using Hobby for a business violates the terms. | ⚠️ **Documented limitation.** See [§13](#13-guardrails-and-deliberate-limitations). Upgrade to Vercel Pro before using this commercially. |

### Free LLM tier

Covered in [§4](#4-free-llm-provider-setup): request spacing, a concurrency cap,
retry-with-backoff honouring `Retry-After`, fail-fast on non-retryable errors, a
per-sweep call ceiling, and a deterministic fallback at every call site.

---

## 7. Keeping the free tier alive

Render spins the service down after **15 minutes** with no inbound traffic. A cold
start takes about a minute, which is noticeable if a supplier clicks their link at the
wrong moment.

**Keep the API warm.** Point a free uptime monitor at `/health` every **14 minutes**:

1. Create a free account at <https://uptimerobot.com> (or cron-job.org, or
   BetterStack).
2. New monitor → HTTP(S) → URL `https://YOUR-API.onrender.com/health` →
   interval **14 minutes**.
3. `/health` returns 200 even when a dependency is unhealthy (the body says
   `"status": "degraded"`), so the monitor never marks a cold database as an outage.

**Drive the scheduler from outside.** The in-process scheduler only runs while the
service is awake, which is exactly when it is least needed. Point a second free cron
at the tick endpoint so follow-ups fire on schedule regardless:

1. Generate a secret and set it on Render:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

   ```env
   SCHEDULER_SECRET=<that value>
   ```

   > The endpoint is **disabled** (403) while `SCHEDULER_SECRET` is empty. An
   > unauthenticated endpoint that sends email is not an acceptable default, even in
   > development.

2. Create a cron at <https://cron-job.org> (free) or a GitHub Actions schedule:

   ```
   URL:     https://YOUR-API.onrender.com/internal/scheduler/tick
   Method:  POST
   Header:  X-Scheduler-Secret: <the same value>
   Schedule: every 15 minutes
   ```

3. The response tells you exactly what happened:

   ```json
   {
     "status": "ok",
     "scanned": 4, "drafted": 2, "sent": 0, "queued_for_approval": 2,
     "skipped": 2, "expired": 1, "failed": 0, "llm_calls": 1,
     "auto_send_enabled": false,
     "actions": [
       { "supplier": "Nova Metals S.L.", "action": "request_missing_fields",
         "kind": "incomplete_quote", "reason": "…", "requested": ["minimum order quantity"],
         "llm_generated": true, "result": "awaiting_approval" }
     ]
   }
   ```

   Running the tick twice in quick succession is safe: a second run will not create a
   duplicate draft for a supplier who already has one pending.

With a GitHub Actions schedule, note that GitHub's cron is best-effort and can be
delayed by several minutes under load — fine for reminders, not a scheduler you would
use for billing.

---

## 8. Architecture

```
rfq-comparison-tool-main/
├── backend/                    FastAPI application
│   ├── app/
│   │   ├── core/               config, database, security, LLM client, email,
│   │   │                       storage, rate limiting, exceptions
│   │   ├── features/           one slice per domain, each with
│   │   │   ├── auth/           model · schema · service · router
│   │   │   ├── rfq/
│   │   │   ├── supplier/
│   │   │   ├── invitation/     tokenized links, status, resend
│   │   │   ├── quote/          quotes from every source
│   │   │   ├── attachment/     validated uploads, claim-by-key
│   │   │   ├── public_form/    supplier-facing, token-authenticated
│   │   │   ├── followup/       scheduler, drafts, approvals, log
│   │   │   ├── comparison/     scoring snapshots, approvals, CSV export
│   │   │   ├── dashboard/      workspace roll-up
│   │   │   └── chat/           conversational assistant (from the base repo)
│   │   ├── ai/                 LLM factory, agent registry, completer bridge
│   │   └── main.py
│   ├── alembic/                migrations
│   ├── scripts/seed_demo.py    demo data
│   └── tests/                  pytest suite
│
├── agents/                     pure domain logic — no web, no database
│   ├── quote_parser/           submission → typed quote (+ completeness)
│   └── followup/               invitation → chase / ask / escalate decision
│
├── comparison/                 pure domain logic — landed cost and scoring
│   ├── fx.py  incoterms.py  units.py  cost.py  score.py
│   ├── recommend.py  engine.py  exporters.py
│
├── frontend/                   buyer dashboard (Vercel project 1)
├── public_form/                supplier form (Vercel project 2)
├── docker-compose.yml  render.yaml  .env.example  NOTICE
```

### The layering rule

`agents/` and `comparison/` contain **no I/O**: no FastAPI, no SQLAlchemy, no HTTP.
An LLM is injected as a plain `async` callable, and everything has a deterministic
fallback path. Consequences worth the discipline:

- The whole comparison engine and the entire follow-up policy are unit-testable
  without a database, a server, or a network — see `tests/test_comparison_engine.py`.
- The test suite runs with **no LLM key configured by default**, so the fallback paths
  are what is exercised, not an afterthought.
- A provider outage or an exhausted free tier degrades quality, never availability.

### The follow-up decision order

Inherited from ForgeFlow, and the ordering is the point:

```
1. nothing to do          → skip    (already complete, cancelled, declined, expired)
2. deadline passed        → skip    (the window is closed)
3. supplier blocked on us → skip,   escalate to the buyer
4. quote is incomplete    → ask for exactly the missing fields
5. not submitted          → remind
6. not due yet            → skip
```

Step 3 before steps 4–5 is deliberate: a supplier waiting on the buyer for a spec or a
volume **cannot be reminded into answering**. Chasing them asks for something they have
already said they cannot give — it produces nothing, damages the relationship, and
hides the fact that the buyer is the blocker. That case is surfaced to the buyer instead.

### Award guardrail

The comparison endpoint *recommends*. `POST /rfqs/{id}/comparison/approve` is the only
path to an award, and the call graph enforces it: nothing in the scheduler, the parser,
or the LLM can reach `ComparisonService.approve`. The rule is structural, not a prompt
instruction.

---

## 9. Configuration reference

Every variable, its default, and why it exists. `.env.example` carries the same
information with more commentary.

### Core

| Variable | Default | Notes |
| --- | --- | --- |
| `ENV` | `development` | `production` hides exception details from 500 responses and enables startup safety warnings. |
| `APP_NAME` | `Supplier Quote Autopilot` | Shown in the API docs and the OpenRouter attribution header. |

### Database

| Variable | Default | Notes |
| --- | --- | --- |
| `DATABASE_URL` | local Postgres | The app's connection. **Neon pooled** string in production. |
| `DATABASE_URL_DIRECT` | *(falls back to `DATABASE_URL`)* | Alembic only. **Neon direct** string. |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `5` / `5` | Keep small — Neon's free tier has limited connections. |
| `DB_POOL_RECYCLE_SECONDS` | `300` | Must be below Neon's idle timeout so dead sockets are not reused. |

### Auth

| Variable | Default | Notes |
| --- | --- | --- |
| `SECRET_KEY` | dev placeholder | **Required in production.** Signs JWTs. Rotating it signs everyone out. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` (7 days) | |

### URLs and CORS

| Variable | Default | Notes |
| --- | --- | --- |
| `BACKEND_URL` | `http://localhost:8000` | Used to build storage URLs and the OpenRouter referer header. |
| `FRONTEND_URL` | `http://localhost:5173` | |
| `PUBLIC_FORM_URL` | `http://localhost:5174` | **The base of every supplier link.** Wrong value = every invitation 404s. |
| `ALLOWED_ORIGINS` | `*` | Comma-separated. Set explicitly in production. |

### AI

| Variable | Default | Notes |
| --- | --- | --- |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | Any OpenAI-compatible endpoint. |
| `LLM_API_KEY` | *(empty)* | Empty ⇒ deterministic fallbacks everywhere. |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | |
| `LLM_ENABLED` | `true` | A kill switch that does not require removing the key. |
| `LLM_REQUESTS_PER_MINUTE` | `30` | Matches Groq's free tier. Lower it, never raise it above your actual tier. |
| `LLM_MAX_CONCURRENCY` | `2` | |
| `LLM_MAX_RETRIES` | `4` | |
| `LLM_TIMEOUT_SECONDS` | `60` | |
| `LLM_BATCH_MAX_CALLS` | `50` | Per scheduler sweep. |

### Email

| Variable | Default | Notes |
| --- | --- | --- |
| `EMAIL_PROVIDER` | `console` | `console` \| `resend` \| `sendgrid` \| `mailgun` \| `brevo`. `console` logs and sends nothing. |
| `EMAIL_API_KEY` | *(empty)* | |
| `EMAIL_API_URL` | *(empty)* | Optional endpoint override. |
| `MAIL_FROM` | Resend test sender | Must be on a domain verified with your provider. For Mailgun the domain is taken from this address. |

### Storage

| Variable | Default | Notes |
| --- | --- | --- |
| `STORAGE_BACKEND` | `local` | `local` \| `s3`. **Must be `s3` on Render.** |
| `UPLOAD_DIR` | `./var/uploads` | Local backend only. |
| `MAX_UPLOAD_MB` | `10` | Enforced server-side and surfaced to the form. |
| `ALLOWED_UPLOAD_EXTENSIONS` | pdf, images, csv, xlsx, doc(x) | HTML is always rejected. |
| `S3_ENDPOINT_URL` | | R2 / B2 / Neon Object Storage endpoint. |
| `S3_BUCKET` | | |
| `S3_REGION` | `auto` | `auto` is correct for R2. |
| `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | | |
| `S3_PUBLIC_BASE_URL` | | Set when the bucket has a public domain; otherwise files are proxied through `/files/{key}`. |

### Public form

| Variable | Default | Notes |
| --- | --- | --- |
| `INVITATION_TTL_DAYS` | `30` | Link lifetime. Bounded by the RFQ deadline plus a week when one is set. |
| `PUBLIC_RATE_LIMIT_PER_MINUTE` | `20` | Per IP. |
| `PUBLIC_RATE_LIMIT_PER_HOUR` | `60` | Per IP **and** per token. |
| `CAPTCHA_PROVIDER` | `none` | `none` \| `turnstile` \| `hcaptcha`. |
| `CAPTCHA_SITE_KEY` / `CAPTCHA_SECRET_KEY` | | Required only when a provider is set. |

### Follow-ups

| Variable | Default | Notes |
| --- | --- | --- |
| `AUTO_SEND_FOLLOWUPS` | `false` | `false` queues every reminder as a draft for approval. Does not affect awarding. |
| `FOLLOWUP_INTERVALS_HOURS` | `72,168` | Chase after 3 days, then after 7. One entry per reminder. |
| `FOLLOWUP_BEFORE_DEADLINE_HOURS` | `48` | Also remind this close to the deadline, overriding the interval. |
| `MAX_FOLLOWUPS_PER_INVITATION` | `3` | High-risk suppliers get one extra. |
| `MAX_INCOMPLETE_REMINDERS` | `2` | Cap on chasing specific missing fields. |
| `SCHEDULER_ENABLED` | `true` | The in-process loop. |
| `SCHEDULER_INTERVAL_MINUTES` | `15` | |
| `SCHEDULER_SECRET` | *(empty)* | Required to enable `POST /internal/scheduler/tick`. |

### Comparison

| Variable | Default | Notes |
| --- | --- | --- |
| `BASE_CURRENCY` | `USD` | Fallback when an RFQ does not name one. |
| `FX_RATES_JSON` | *(built-in table)* | Partial override, e.g. `{"EUR": 0.93}`. |
| `DEFAULT_SCORING_WEIGHTS_JSON` | *(built-in weights)* | Overridable per RFQ from the UI. |
| `LEAD_TIME_RISK_DAYS` | `90` | Lead times at or above this are flagged. |
| `QUOTE_VALIDITY_WARNING_DAYS` | `7` | Quotes expiring within this many days are flagged. |

---

## 10. API

Interactive documentation is at **`/docs`** (Swagger UI) and **`/redoc`**. The written
reference — every endpoint, request body, response shape, status code and guardrail —
is in **[docs/API.md](docs/API.md)**.

Two conventions worth knowing up front:

- **Buyer endpoints** need `Authorization: Bearer <token>` from `POST /auth/login`.
  Every list is scoped to your account; another tenant's id returns 404, never 403.
- **`/public/*` endpoints need no credentials.** They are authenticated by the
  invitation token in the URL, which grants exactly the right to answer one RFQ — not
  to read any part of the buyer's workspace.

---

## 11. Testing

```bash
cd backend
uv run pytest -q                       # everything
uv run pytest --cov=app --cov-report=term-missing
uv run pytest tests/test_acceptance.py -q
```

The suite is **fast, offline and deterministic**. It runs against a temporary SQLite
database, with `EMAIL_PROVIDER=console` and **no LLM key**, so it needs no services and
costs nothing.

| File | Covers |
| --- | --- |
| `test_acceptance.py` | The whole product through the public HTTP API: create an RFQ → three suppliers → three unique links → submit (one complete, one partial, one silent) → statuses → scheduler chases both → approve reminders → compare → CSV export → human award → dashboard roll-up. Plus the AI-optional path. |
| `test_regressions.py` | Bugs found during development, with the failure mode recorded in each docstring. |
| `test_comparison_engine.py` | FX, Incoterms rebasing, unit conversion, landed-cost arithmetic, MOQ/payment-term scoring, weighting, ranking, determinism, CSV export. |
| `test_quote_parser.py` | Verbatim-or-null grounding, layer precedence, lead-time/money/date normalization, and every completeness rule — including "explicitly none is an answer" and "TBD is not". |
| `test_followup_policy.py` | Each branch of the decision order, reminder caps, and the escalate-don't-chase rule. |
| `test_transports.py` | The HTTP email providers, the LLM client's retry/backoff/rate-limit behaviour, and an assertion that **no SMTP code exists anywhere**. |
| `test_rfq.py`, `test_quote.py`, `test_chat.py`, `test_csv_import.py` | Kept from the base codebase, unmodified. |

CI (`.github/workflows/ci-cd.yml`) additionally runs `alembic check` (fails if the
migration and the models disagree), verifies `requirements.txt` matches `uv.lock`,
asserts no SMTP imports exist, validates `docker-compose.yml` and `render.yaml`, and
builds and lints both frontends.

---

## 12. Demo data

```bash
cd backend
uv run python -m scripts.seed_demo --reset --run-scheduler
```

Creates a buyer, four suppliers, an RFQ, four tokenized links, three submissions and
two pending follow-up drafts, then prints a working supplier link and the login.

| | |
| --- | --- |
| Email | `buyer@demo-autopilot.example.com` |
| Password | `demo-password-123` |

The scenario is deliberately imperfect, so every state the product handles is visible
at once: one supplier quotes completely, one leaves fields blank, one quotes in EUR on
DDP terms, and one never responds at all. That gives the comparison a real trade-off
rather than an obvious winner — and it is the shape of data that surfaced two bugs
during development (both now covered by `test_regressions.py`).

Flags: `--reset` (delete first), `--run-scheduler` (draft reminders immediately),
`--skip-compare`.

---

## 13. Guardrails and deliberate limitations

**Guardrails, enforced in code**

- **Never auto-award.** `POST /rfqs/{id}/comparison/approve` is the only path to an
  award. It requires an authenticated buyer and a written reason. Nothing in the
  scheduler, the parser, or the LLM can reach it.
- **Never silently drop a supplier.** A quote that cannot be normalized (unknown
  currency, incompatible unit) still appears in the comparison with
  `comparable: false` and a reason. Omitting a supplier from a comparison is the
  failure mode that costs money.
- **Never invent a number.** The parser is verbatim-or-null and every extracted value
  cites the phrase it came from. The comparison narrative receives an already-computed
  scoring run and is instructed not to introduce figures of its own.
- **Never chase a blocked supplier.** See [§8](#the-follow-up-decision-order).
- **Never re-ask an answered question.** "No MOQ at this stage" is an answer.
- **Never send a follow-up that makes a commercial claim.** A model that volunteers
  "your quote is competitive" has its output rejected in favour of the template.
- **No SMTP, ever.** Asserted by a test and by a CI step.

**Deliberate limitations of this MVP**

- **Vercel Hobby forbids commercial use.** Using the free Hobby plan for a business
  violates Vercel's terms. Upgrade to Pro before commercial use, or host the two SPAs
  anywhere that serves static files. (Neon and Render's free tiers do not carry this
  restriction, though they do have the resource limits listed above.)
- **Static FX rates, not a live feed.** The table is documented, dated, and
  overridable via `FX_RATES_JSON`, and every result carries the rate and its as-of
  date so a stale rate is visible rather than silently wrong. Rationale: a live FX API
  is another dependency, another key, and another failure mode, and the failure mode
  of a feed that dies mid-comparison is worse than a slightly stale rate.
- **Indicative Incoterms rebasing.** Comparing an EXW quote against a DDP one uses a
  documented cost ladder as a fraction of goods value, not real freight economics.
  Every rebased quote is labelled and the factors are recorded in the snapshot.
- **Sync SQLAlchemy, not `asyncpg`.** The base codebase is sync SQLAlchemy + `psycopg`
  3, and rewriting every slice to async would have been a rewrite rather than an
  extension. The genuinely latency-bound work (LLM, email, storage) *is* async. See
  INTEGRATION_PLAN.md assumption A1.
- **Rate limiting is in-process.** A sliding window keyed by IP and token, held in
  memory. Correct for the single Render instance the free tier runs; a multi-instance
  deployment needs Redis. Noted rather than pre-built.
- **Single-tenant auth.** A `User` is the tenant boundary. There is no team,
  organisation, or role model — no half-built permissions to misconfigure.
- **Attachment tracking is in-memory until claimed.** A file is dropped unless a
  submission references its key within the same session, which is why the upload and
  the submit happen seconds apart on one page.
- **The Chat assistant** (inherited from the base codebase) still uses LangChain and
  is the one place that does not share the new `llm_client`. It works against any
  OpenAI-compatible provider, but it is heavier than the rest of the AI layer.

---

## 14. Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `Field required [DATABASE_URL]` on boot | No `.env`, or it is in the wrong directory. Docker Compose reads the **root** `.env`; native runs read `backend/.env`. |
| First request after idle takes ~1 minute | Expected. Render spun the service down. See [§7](#7-keeping-the-free-tier-alive). |
| First request succeeds but is slow, then fine | Neon's compute was scaled to zero. Expected; `/health` reports it. |
| Supplier link 404s | `PUBLIC_FORM_URL` is wrong on Render, or the link was copied with a trailing character. It must be `https://…/quote/<rfq_id>/<token>`. |
| CORS error in the browser console | `ALLOWED_ORIGINS` on Render must list the exact Vercel origin, scheme included, no trailing slash. Redeploy after changing it. |
| Emails never arrive | `EMAIL_PROVIDER=console` sends nothing by design. Set a real provider and `EMAIL_API_KEY`, and make sure `MAIL_FROM` is on a **verified** domain. Resend's `onboarding@resend.dev` only delivers to your own account address. |
| `502 Upstream service error` on a reminder | The email provider rejected the send. The provider's message is in the `detail` and in the follow-up's `error` field; the invitation link is unaffected. |
| Follow-ups never send | Three candidates: `AUTO_SEND_FOLLOWUPS=false` (drafts are waiting in **Follow-ups**), the interval has not elapsed (`FOLLOWUP_INTERVALS_HOURS`), or the RFQ deadline has passed, which stops follow-ups by design. |
| Reminders never fire while the service is idle | The in-process scheduler sleeps with the service. Set `SCHEDULER_SECRET` and point an external cron at the tick endpoint. |
| `403` from `/internal/scheduler/tick` | `SCHEDULER_SECRET` is unset (the endpoint is disabled) or the `X-Scheduler-Secret` header does not match. |
| Files vanish after a deploy | `STORAGE_BACKEND=local` on Render. Render's free tier has no persistent disk — switch to `s3`. |
| `alembic` hangs or errors on Neon | You are using the pooled string. Use `DATABASE_URL_DIRECT` (no `-pooler`). |
| Comparison says "no defensible conversion exists" | A supplier quoted in a unit of measure that cannot be converted to the RFQ's (kg vs pcs). Ask them to re-quote, or change the RFQ's unit. |
| Comparison excludes a quote entirely | Unknown currency. Add it to `FX_RATES_JSON`. |
| AI features feel generic or template-like | No `LLM_API_KEY`, or the quota is exhausted. `/health` reports the provider state and the number of calls made. |
| `npm run build` fails on Vercel but not locally | The Vercel root directory is not set to `frontend` / `public_form`, or `VITE_API_URL` is missing. Vite variables are baked in at build time — redeploy after changing one. |
| Migration says "target database is not up to date" | Run `alembic upgrade head` against the direct connection string. |

---

## Further reading

| Document | Contents |
| --- | --- |
| [INTEGRATION_PLAN.md](../INTEGRATION_PLAN.md) | What was reused, adapted, or reimplemented from each reference repo; license analysis; assumptions; build order. |
| [docs/API.md](docs/API.md) | Full API reference with request/response examples. |
| [NOTICE](NOTICE) | Third-party attribution, including the ForgeFlow MIT notice. |
| [backend/README.md](backend/README.md) | Backend-specific notes. |
| [frontend/README.md](frontend/README.md) | Buyer dashboard structure and theming. |
| [public_form/README.md](public_form/README.md) | Supplier form and its tokenized URL scheme. |
