# Backend — Supplier Quote Autopilot

FastAPI service that owns persistence, validation, the public supplier form's
ingestion pipeline, the follow-up scheduler, and the comparison engine's persistence
layer.

Deployment (Neon + Render + Vercel), free-tier limits, and the LLM provider setup are
covered in the [root README](../README.md). This document is about the backend itself.

---

## Tech stack

| Concern | Choice |
| --- | --- |
| Language | Python 3.13 |
| Web framework | FastAPI + Uvicorn |
| ORM / DB | SQLAlchemy 2 (sync) · PostgreSQL via `psycopg` 3 |
| Migrations | Alembic |
| Validation / config | Pydantic v2 · pydantic-settings |
| Auth | PBKDF2 password hashing · HS256 JWT (`PyJWT`) |
| LLM | Any OpenAI-compatible endpoint via a hand-written `httpx` client |
| Email | HTTPS APIs only — Resend · SendGrid · Mailgun · Brevo. **No SMTP.** |
| Storage | Local filesystem · any S3-compatible store (`boto3`, imported lazily) |
| Chat assistant | LangChain 1 · LangGraph 1 (inherited from the base codebase) |
| Tooling | uv · pytest · Docker |

---

## Layout

```
backend/
├── app/
│   ├── main.py               app wiring, lifespan, /health, /files proxy
│   ├── models.py             imports every model so create_all + Alembic see them
│   │
│   ├── core/
│   │   ├── config.py         every setting, one place; no os.environ elsewhere
│   │   ├── database.py       engine, SessionLocal, get_db, warm_up
│   │   ├── dependencies.py   DBSession, CurrentUser
│   │   ├── exceptions.py     domain error hierarchy -> JSON at the edge
│   │   ├── security.py       PBKDF2, JWT, invitation tokens
│   │   ├── llm_client.py     OpenAI-compatible client: throttle, retry, JSON repair
│   │   ├── email.py          HTTPS transactional email, four providers + console
│   │   ├── storage.py        local + S3 backends, traversal-safe keys
│   │   ├── rate_limit.py     honeypot, sliding window, optional CAPTCHA
│   │   └── mixins.py         TimestampMixin, utcnow, RFQ number generator
│   │
│   ├── features/             one slice per domain: model · schema · service · router
│   │   ├── auth/             buyer accounts and sessions
│   │   ├── rfq/              RFQs; procurement taxonomy, deadline, required fields, weights
│   │   ├── supplier/         supplier directory + response statistics
│   │   ├── invitation/       tokenized form links, status derivation, resend
│   │   ├── quote/            quotes from every source + CSV/PDF importers
│   │   ├── attachment/       validated uploads, claim-by-key
│   │   ├── public_form/      supplier-facing, token-authenticated ingestion
│   │   ├── followup/         scheduler, snapshots, drafts, approvals, log
│   │   ├── comparison/       scoring snapshots, narrative, approvals, CSV export
│   │   ├── dashboard/        workspace roll-up
│   │   └── chat/             conversational assistant (from the base codebase)
│   │
│   └── ai/
│       ├── llm.py            LangChain factory, now provider-agnostic
│       ├── completer.py      bridges the pure agents to the LLM client
│       ├── registry.py       agent name -> callable
│       └── agents/           rfq_assistant · procurement_assistant ·
│                             procurement_orchestrator · supplier_mailer ·
│                             quote_extraction
│
├── alembic/                  migrations (env.py reads DATABASE_URL_DIRECT)
├── scripts/                  seed_demo.py · list_routes.py
└── tests/                    pytest suite, offline and deterministic
```

The two **pure** domain packages live outside this directory, as siblings, so they
carry no web or database dependency:

```
../agents/quote_parser/       supplier submission -> typed quote + completeness
../agents/followup/           invitation snapshot -> chase / ask / escalate
../comparison/                FX, Incoterms, units, landed cost, scoring, export
```

`app/__init__.py` puts the repository root on `sys.path`, so `import comparison` and
`import agents.quote_parser` work under `uv run`, Docker, Render, and pytest with no
`PYTHONPATH` configuration from an operator.

---

## Layering rules

- **Routers** parse and validate, then delegate. They never touch the session directly
  and never contain business logic.
- **Services** own DB access and business rules, and raise domain errors
  (`NotFoundError`, `BadRequestError`, `ConflictError`, `InvitationExpiredError`,
  `ExternalServiceError`) — never `HTTPException`.
- **`core/exceptions.py`** translates those to HTTP, so the domain stays
  framework-agnostic. `RequestValidationError` is flattened into a single readable
  `detail` string because the API client renders `detail` verbatim.
- **`agents/` and `comparison/` do no I/O.** An LLM is injected as a plain `async`
  callable and every path has a deterministic fallback. That is what makes the policy
  and the engine unit-testable without a database, a server, or a network.
- **Tenancy is enforced in the service, not the router.** Every lookup takes
  `user_id` and returns 404 — not 403 — for another tenant's row.

---

## Database

Sync SQLAlchemy with `psycopg` 3. The base codebase was sync, and rewriting every slice
to async would have been a rewrite rather than an extension; the genuinely
latency-bound work (LLM, email, storage) *is* async. See INTEGRATION_PLAN.md
assumption A1.

```bash
# Local: DATABASE_URL_DIRECT is unset and falls back to DATABASE_URL.
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "add something"
uv run alembic check          # fails if the models and the migration disagree
uv run alembic downgrade -1
```

**Two connection strings, deliberately.** On Neon:

| Variable | Used by | Shape |
| --- | --- | --- |
| `DATABASE_URL` | the app | hostname contains `-pooler` (PgBouncer, transaction mode) |
| `DATABASE_URL_DIRECT` | Alembic only | no `-pooler` |

Alembic's DDL and its `alembic_version` bookkeeping do not behave reliably through
transaction pooling. Locally, `DATABASE_URL_DIRECT` is empty and everything uses one
URL.

**`create_all` is kept, and is not the source of truth.** It runs at startup so a first
boot on a fresh database works with no manual step. It only ever *adds* missing tables
and never alters or drops, so it cannot conflict with Alembic. Once you have
migrations, Alembic is the authority — and CI runs `alembic check` on every push.

Pool settings are tuned for Neon's scale-to-zero: `pool_pre_ping=True` so a socket the
compute closed while idle is never handed to a request, and
`pool_recycle=DB_POOL_RECYCLE_SECONDS` (300 s) below Neon's idle timeout.

---

## Data model

```
User ──┬── RFQ ──┬── Invitation ──┬── SupplierQuote
       │         │                └── FollowUp
       │         ├── SupplierQuote
       │         ├── FollowUp
       │         └── Comparison ── Approval
       └── Supplier ──┬── Invitation
                      └── SupplierQuote
```

| Table | Purpose | Notes |
| --- | --- | --- |
| `users` | Buyer accounts. **The tenant boundary.** | Single-tenant: no team/role model. |
| `suppliers` | Reusable supplier directory. | Unique per `(user_id, contact_email)`. `risk_rating` feeds the score. |
| `rfqs` | The request. | Carries `deadline`, `required_fields` (the completeness contract), `scoring_weights`, `currency`, `incoterms`, `procurement_type` and `category`. Services columns: `site_name`, `site_address`, `site_access_notes`, `required_response_hours`, `required_accreditations`, `gst_rate`. |
| `invitations` | One tokenized link per (RFQ, supplier). | Unique per pair. Tracks `status`, `sent_at`, `responded_at`, `view_count`, `reminder_count`. |
| `supplier_quotes` | Quotes from any source. | Raw submitted figures are **never overwritten**; normalized results live in separate `normalized_*` and `cost_breakdown` columns. Services columns: `response_time_hours`, `callout_charge`, `labour_rate`, `materials_markup_pct`, `compliance_accreditations`, `gst_rate`. |
| `follow_ups` | Every message, sent or pending. | The communication log. `kind` distinguishes no-response / incomplete / deadline / manual. |
| `comparisons` | Immutable scoring snapshots. | Stores the weights, FX rates, per-quote results and rationale used, so a past recommendation stays explicable. |
| `approvals` | Human award decisions. | Records the recommendation at decision time, whether it was overridden, and the buyer's reason. |

All new columns added on top of the base codebase are nullable or defaulted, so the
original rows and the existing importer paths keep working.

---

## The `required_fields` contract

An RFQ declares which fields a quote must carry to count as complete. That list is the
single input to completeness checking, and therefore to what the follow-up engine is
allowed to ask for. `app/features/rfq/taxonomy.py` holds one contract per procurement type,
and the default follows the type — `RFQCreate.effective_required_fields` resolves it, and
`rfq/model.py`'s `DEFAULT_REQUIRED_FIELDS` is the **services** list because `service` is this
product's default type:

```
service  unit_price · currency · unit · response_time · payment_terms · validity_date
goods    unit_price · currency · lead_time · moq · payment_terms · incoterms · validity_date
```

MOQ and Incoterms are deliberately **not** in the services contract: a minimum callout is a
charge that already shows up inside the price rather than a quantity gate, and nothing is
being shipped. An RFQ that lists `required_fields` explicitly gets exactly that list —
nothing is added to it.

The rules (`agents/quote_parser/completeness.py`):

- A field is answered when it carries a concrete value.
- **An explicit "none" is an answer.** "No MOQ at this stage" is complete.
- **"TBD" is not.** Neither is a promise to send something later.
- A field the buyer never required is never reported as missing.
- A `blocking_question` short-circuits the whole report: the summary says to resolve the
  supplier's question rather than send a reminder.
- The field's *label* comes from the same module's `label_for(field, procurement_type)`,
  which applies the services wording (`unit_price` → "rate", `moq` → "minimum callout
  charge", `lead_time` → "mobilisation time"). That one table feeds the API schemas, the
  dashboard, the public form and the follow-up emails, so they cannot drift apart.

---

## AI subsystem

Two paths, on purpose.

**New autopilot features** (`quote parsing`, `follow-up drafting`, comparison
narrative) use `core/llm_client.py` — a small `httpx` client with request spacing,
bounded concurrency, retry with backoff honouring `Retry-After`, fail-fast on
non-retryable errors, and JSON recovery for the ways small free models wrap objects in
prose or fences. `ai/completer.py` adapts it to the plain callable that
`agents/quote_parser` and `agents/followup` accept.

Two constants in that client exist for the same reason, and both matter. `chat_json`
defaults to `max_tokens=4096` rather than a tight 1500, and a model recognised as a
reasoning model is sent `reasoning_effort` from `LLM_REASONING_EFFORT` (default `low`).
The recommended free models emit a reasoning trace before their JSON: at a tight budget the
trace consumed the whole completion and Groq rejected the call with HTTP 400
`json_validate_failed` — "max completion tokens reached before generating a valid
document" — so quote parsing, follow-up drafting and comparison summaries all fell back to
their deterministic paths without ever saying why. `is_reasoning_model()` matches by
substring against a deliberately narrow marker list, because a false positive sends the
field to a model that rejects it and turns a working configuration into a broken one.

**The pre-existing chat assistant** (`rfq_assistant`, `procurement_assistant`,
`procurement_orchestrator`, `supplier_mailer`, `quote_extraction`) still uses
LangChain/LangGraph. `ai/llm.py` was changed to read `LLM_BASE_URL` / `LLM_API_KEY` /
`LLM_MODEL` and pass `base_url` through, so it works against Groq, OpenRouter and
Gemini without touching the agents.

Every LLM call site catches the unavailable error and falls back:

| Feature | Fallback when no key, or the quota is spent |
| --- | --- |
| Quote parsing | Deterministic labelled-line extraction (`agents/quote_parser/heuristic.py`) |
| Follow-up drafting | Deterministic templates that follow the same writing rules |
| Comparison narrative | `build_rationale()` — generated from the scoring run, always present |

The test suite runs with `LLM_API_KEY` empty, so the fallbacks are what is exercised by
default rather than an afterthought.

---

## Email

`core/email.py` has **no SMTP code path**. Render's free tier blocks outbound ports
25/465/587, so an SMTP client would fail at connect time in production. Providers:

```
console    logs the message, sends nothing (local default)
resend     https://api.resend.com/emails
sendgrid   https://api.sendgrid.com/v3/mail/send
mailgun    https://api.mailgun.net/v3/<domain>/messages   (domain from MAIL_FROM)
brevo      https://api.brevo.com/v3/smtp/email
```

A test and a CI step both assert that `smtplib` never appears in the source tree.

Failures are handled where they happen, not by aborting the caller:

- An invitation whose email fails is still created, its token stays valid, and the
  failure is recorded on the `FollowUp` row. The buyer sees it and can resend.
- A batch send replaces individual failures with a `failed` result, so one bad address
  does not stop the rest of a sweep.

---

## Storage

`STORAGE_BACKEND=local|s3`. Both backends implement the same three methods
(`save`, `read`, `delete`) plus `url_for`.

Security properties that matter, because uploads come from an unauthenticated public
endpoint:

- Size, extension and content-type are validated **before** anything is written, and
  `text/html` is always rejected.
- Storage keys are generated (`invitations/<id>/<uuid><ext>`). The supplier's filename
  is kept only as display metadata, so path traversal is impossible by construction —
  and `LocalStorage` additionally resolves and bounds-checks every path.
- A submission references files by key, and `AttachmentService.resolve` verifies each
  key was issued to *that* invitation. Otherwise one supplier could attach another's
  file.

`boto3` is imported lazily, so the local backend and the test suite never load it —
which matters at 512 MB of RAM.

---

## Scheduler

`features/followup/scheduler.py` runs `run_scheduler` on an interval from inside the web
process, started in the lifespan and cancelled on shutdown. A plain `asyncio` task, not
APScheduler: one dependency fewer for a single fixed interval.

Render's free tier has no always-on worker, so the same work is exposed at
`POST /internal/scheduler/tick` for an external free cron. Both paths call the same
function, and overlapping runs are safe: `find_recent_duplicate` suppresses a second
draft of the same kind for the same invitation, and the reminder counter is incremented
in the same transaction as the send.

The tick endpoint requires `SCHEDULER_SECRET` and returns **403 while it is unset**. An
unauthenticated endpoint that sends email is not an acceptable default, even in
development.

---

## Running locally

```bash
uv sync --all-groups
cp .env.example .env            # DATABASE_URL already points at localhost:5432
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

| URL | |
| --- | --- |
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Health | http://localhost:8000/health |

`/health` always returns 200 with the truth in the body — database, storage, LLM,
email, and scheduler state — so an uptime ping counts a cold-but-working service as up
while a human can still see what is unreachable.

A local Postgres:

```bash
docker run --name sqa-postgres -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=supplier_quote_db \
  -p 5432:5432 -d postgres:17
```

---

## Testing

```bash
uv run pytest -q
uv run pytest --cov=app --cov-report=term-missing
uv run pytest tests/test_acceptance.py -q
```

The suite needs **no services**: a temporary SQLite database, `EMAIL_PROVIDER=console`,
and no LLM key. `tests/conftest.py` pins the environment *before* `app.core.config` is
imported, because settings are read once at import time — a test that changed them
afterwards would be testing a different application than the one that boots in
production.

| File | Covers |
| --- | --- |
| `test_acceptance.py` | The whole product through the HTTP API, end to end. |
| `test_public_form.py` | The unauthenticated surface: bad/expired/withdrawn links, honeypot, both rate-limit windows, upload limits, cross-invitation attachment claims, resubmission semantics, and escalation of a supplier's question. |
| `test_regressions.py` | Bugs found in development, with the failure mode in each docstring. |
| `test_comparison_engine.py` | FX, Incoterms rebasing, units, landed cost, scoring, ranking, CSV. |
| `test_quote_parser.py` | Grounding, layer precedence, normalization, completeness rules. |
| `test_followup_policy.py` | Every branch of the decision order, caps, escalate-don't-chase. |
| `test_transports.py` | Email providers, LLM retry/backoff, and no-SMTP enforcement. |
| `test_rfq.py` · `test_quote.py` · `test_chat.py` · `test_csv_import.py` | Kept from the base codebase, unmodified. |

---

## Scripts

```bash
uv run python -m scripts.seed_demo --reset --run-scheduler   # demo workspace
uv run python -m scripts.list_routes                         # live route table (Markdown)
```

`seed_demo` drives the real services — including the public-form ingestion pipeline — so
the seeded quotes have genuine normalized costs, completeness assessments and risk
flags rather than values a fixture made up. The scenario is the product's actual subject: a
Singapore facilities team buying electrical minor works — 24 points priced per point in SGD
with 9% GST, a 4-hour attendance requirement and a required electrical licence — with four
suppliers chosen so the dashboard shows every state the product handles: cheapest but
unlicensed, dearer but faster and fully accredited, incomplete, and silent.

---

## File import

`POST /rfqs/{id}/quotes/import` accepts CSV or PDF (dispatched by extension, max 2 MB)
and returns `{imported, failed, errors}`. Valid rows are committed even when others fail.
After importing, every new quote is assessed for completeness and the comparison is
recomputed, so an imported quote does not skip the pipeline that a form submission goes
through.

```csv
supplier_name,unit_price,currency,lead_time,payment_terms,remarks
ABC Metals,10.50,USD,7,Net 30,High quality
XYZ Industries,9.75,USD,10,Advance Payment,Fast delivery
```

PDFs are read by the vision-capable LangGraph agent, so extraction quality depends on
the document and requires a configured LLM. Without one, the import reports the
provider error rather than silently importing nothing.

---

## Configuration

Every setting is defined in `app/core/config.py` with a default and a comment. The
annotated list — including which are required in production — is in the
[root README §9](../README.md#9-configuration-reference) and
[.env.example](.env.example).

The settings that decide what the product *is*, rather than whether it runs:

| Setting | Default | Effect |
| --- | --- | --- |
| `DEFAULT_PROCUREMENT_TYPE` | `service` | The default type of a new RFQ, and therefore its field contract, its default scoring weights and its vocabulary. `goods` restores the original behaviour. |
| `BASE_CURRENCY` | `SGD` | The currency a comparison falls back to when an RFQ names none. |
| `DEFAULT_GST_RATE` | `9.0` | Becomes the `gst_rate` of a new SGD RFQ, and is applied to a quote that states no tax rate of its own. Set `0` where there is no such tax. |
| `LLM_REASONING_EFFORT` | `low` | `low` \| `medium` \| `high`, or empty. Sent only to models matched as reasoning models; keeps the reasoning trace from consuming the whole completion budget. |

`ENV=production` has two effects: exception details are no longer echoed in 500 responses,
and insecure or lossy defaults are logged loudly at startup — when `SECRET_KEY` is still the
development placeholder, when `ALLOWED_ORIGINS` is `*`, when `STORAGE_BACKEND=local` (lost
on the next deploy), when `EMAIL_PROVIDER=console` (no email is sent), and when
`SCHEDULER_SECRET` is unset (no cron-driven follow-ups).

---

## Extending

**A feature slice.** Create `app/features/<name>/` with `model.py`, `schema.py`,
`service.py`, `router.py`; add the model to `app/models.py`; register the router in
`app/main.py`; generate a migration. Raise domain errors from the service.

**A domain agent.** Put the logic in `../agents/<name>/` with no I/O: schemas,
prompts, and pure functions that accept an optional `async` LLM callable. Add a
deterministic fallback. Then expose it through a service in `app/features/`, which is
where the database and the LLM client live.

**An email provider.** Add one `_send_<provider>` function and one `PROVIDERS` entry in
`core/email.py`. HTTPS only.

**An S3-compatible store.** Nothing to do — `STORAGE_BACKEND=s3` with the `S3_*`
variables works with R2, B2, Neon Object Storage, MinIO and AWS alike.
