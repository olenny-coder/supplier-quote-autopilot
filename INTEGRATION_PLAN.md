# INTEGRATION_PLAN.md — Supplier Quote Autopilot

Mapping of what is **reused**, **adapted**, or **reimplemented** from the two reference
repositories already present in this workspace, plus the license position for each.

> **App root.** All application code lives in
> `./rfq-comparison-tool-main/rfq-comparison-tool-main/` (referred to below as the
> *app root*). This is the `rfq-comparison-tool` repository, extended **in place**.
> `INTEGRATION_PLAN.md` (this file) sits at the workspace root as requested.

---

## 1. Source repositories and licenses

| Repo | Path | License | Position |
| --- | --- | --- | --- |
| `rfq-comparison-tool` | `./rfq-comparison-tool-main/rfq-comparison-tool-main` | **None declared** — no `LICENSE`, `COPYING`, or `NOTICE` file anywhere in the tree | Treated as **first-party, user-supplied code**. The user explicitly directs us to extend it in place ("This is your foundation… You may restructure it in place"). No third-party code is being vendored, so no license obligation is triggered. |
| `ForgeFlow` | `./ForgeFlow-main/ForgeFlow-main` | **MIT** — `Copyright (c) 2026 JayleeBot` | **Redistributable and adaptable.** MIT permits use, modification, and redistribution provided the copyright notice and permission notice are retained. ForgeFlow code is **not** vendored into the app tree; instead selected *concepts and prompt patterns* are adapted, and the required attribution notice is carried in `NOTICE` and in the header of each adapted file. |

### License compliance actions taken

* `NOTICE` at the app root reproduces ForgeFlow's MIT copyright + permission notice and
  lists exactly which files contain adapted material.
* Every adapted file carries a short header: `Adapted from ForgeFlow (MIT, Copyright (c)
  2026 JayleeBot) — see NOTICE`.
* ForgeFlow's own `LICENSE` file is untouched in its own directory.
* No ForgeFlow file was copied byte-for-byte into the app tree.

**Not merged.** The two repositories are *not* merged into one build tree. The app tree is
`rfq-comparison-tool`; ForgeFlow remains a read-only reference at its original path.

---

## 2. Base: `rfq-comparison-tool` — reused as-is

These pieces are kept working, with only the changes listed in §3 layered on.

| KEPT AS-IS | Path (app root) | Why |
| --- | --- | --- |
| Feature-slice convention | `backend/app/features/*/{model,schema,service,router}.py` | Every new domain (`auth`, `supplier`, `invitation`, `followup`, `comparison`, `public_form`) follows the existing 4-file slice. No architectural churn. |
| Domain exception hierarchy | `backend/app/core/exceptions.py` | `AppError` / `NotFoundError` / `BadRequestError` / `ExternalServiceError` + `register_exception_handlers` reused verbatim; new errors (`ConflictError`, `ForbiddenError`, `RateLimitedError`) subclass `AppError`. |
| DB session dependency | `backend/app/core/dependencies.py` (`DBSession`) | Reused; extended with `CurrentUser` and `AdminOrBuyer` aliases in the same file. |
| Settings pattern | `backend/app/core/config.py` | Same `BaseSettings` + `lru_cache` + `NoDecode` comma-list trick; the existing `ALLOWED_ORIGINS` validator is kept and the new variables are added alongside. |
| Sync SQLAlchemy engine + `Base` | `backend/app/core/database.py` | Kept sync (see §5 assumption A1). Now takes Neon pooling options. |
| Comparison table UI primitives | `frontend/src/features/quote/components/QuoteTable*.jsx`, `useQuoteTable` hook | The sortable/searchable table shell is reused for the new side-by-side comparison grid. |
| Shared UI kit & theme | `frontend/src/shared/**` (`ui/index.jsx`, `Modal`, `ConfirmModal`, `EmptyState`, `Loading`, `format.js`, `ThemeProvider`) | Reused by the new dashboard pages; the public form reuses the same *design tokens* (copied `index.css` token block) so buyer and supplier surfaces look related. |
| API client + interceptor | `frontend/src/shared/api/client.js` | Reused; extended to attach the JWT bearer token and to surface 401s. |
| Chat feature (widget + orchestrator) | `backend/app/features/chat/**`, `frontend/src/features/chat/**` | Working piece; kept. Only its LLM factory changed to be provider-agnostic (§3). |
| CSV / PDF quote importers | `backend/app/features/quote/importers/**` | Kept and still reachable at `POST /rfqs/{id}/quotes/import`. |
| CI/CD workflow | `.github/workflows/ci-cd.yml` | Kept; extended with a `public_form` build job and an Alembic migration check. |
| Docker Compose topology | `docker-compose.yml` | Kept (`postgres` + `backend` + `frontend`), extended with `public_form`, a `minio` S3-compatible service, and the scheduler sidecar. |

## 3. Base: `rfq-comparison-tool` — ADAPTED / EXTENDED

| Change | Files | Notes |
| --- | --- | --- |
| **Data model growth** | `backend/app/features/rfq/model.py`, `quote/model.py` | `RFQ` gains `user_id`, `rfq_number`, `currency`, `incoterms`, `required_fields`, `scoring_weights`, `deadline`, `status`, `buyer_company`. `SupplierQuote` gains `invitation_id`, `supplier_id`, `contact_email`, `unit`, `moq`, `incoterms`, `validity_date`, `notes`, `attachments`, the normalized columns, the cost breakdown and `completeness`. All new columns are nullable/have defaults so the existing importer and manual-entry paths keep working unchanged. |
| **LLM factory made provider-agnostic** | `backend/app/ai/llm.py` | Was hard-wired to `openai` + `OPENAI_API_KEY` with no `base_url`. Now reads `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` and passes `base_url` to `ChatOpenAI`, so the existing chat/orchestrator/PDF agents work against Groq, OpenRouter, or Gemini. Return type and call signature unchanged. |
| **Email: Resend SDK → own HTTP provider layer** | `backend/app/features/chat/mailer.py` → thin shim over new `backend/app/core/email.py` | The old mailer was Resend-SDK-only. New layer supports `console` (dev), `resend`, `sendgrid`, `mailgun`, `brevo` — **all over HTTPS**, never SMTP. `send_email(to, subject, body)` signature preserved so the chat feature is untouched. |
| **API client auth** | `frontend/src/shared/api/client.js` | Request interceptor adds `Authorization: Bearer <jwt>`; response interceptor clears the token and redirects to `/login` on 401. Default export and error-normalisation behaviour preserved. |
| **Router tree** | `frontend/src/App.jsx` | Was 3 routes. Now: public `/login`, `/register`; protected layout with `/` (dashboard), `/rfqs`, `/rfqs/new`, `/rfqs/:id` (tabs: Suppliers · Quotes · Comparison · Follow-ups), `/suppliers`. Existing `RFQListPage` / `CreateRFQPage` / `RFQDetailsPage` are kept and extended rather than replaced. |
| **Header/nav** | `frontend/src/shared/layout/Header.jsx` | Nav items become Dashboard / RFQs / Suppliers; user menu + logout added; logo wordmark changed to *Supplier Quote Autopilot*. |
| **CI/CD** | `.github/workflows/ci-cd.yml` | Added public-form build + import-path check. The original VPS-deploy job is replaced by Render/Vercel deploy hooks driven by `RENDER_DEPLOY_HOOK` / `VERCEL_DEPLOY_HOOK` secrets (the original SSH deploy target does not exist for this deployment). |

## 4. Reference: `ForgeFlow` — concept reuse (MIT, adapted, not vendored)

ForgeFlow is an Anthropic-SDK, email-inbox-driven RFQ follow-up agent. Its *inbox
plumbing* (`parser.py` MIME threading, `butterbase` storage, `managed_agent.py`,
`evals.py`, `simulator.py`, the `next-ui` app) is **not reused** — the spec requires
webhook/form ingestion from our own database instead of email inboxes. What *is* reused is
the reasoning design, which is the hard-won part.

| ForgeFlow concept | Where it landed | How it was adapted |
| --- | --- | --- |
| **Verbatim-or-null grounding** (`prompts/extraction.txt`): "only record values that appear literally… never infer, estimate, or paraphrase a commercial value" | `agents/quote_parser/prompts.py` | Kept as the governing rule for parsing free-text supplier notes. Extended with an explicit `evidence` field per extracted value so the UI can show the buyer *why* a number was recorded. |
| **`SupplierQuoteData` schema shape** (`agent.py` L54–71): `price_breaks`, `quote_valid_until`, `incoterms`, `coo`, `payment_terms`, `moq`, `nre`, `blocking_question`, `missing_fields` | `agents/quote_parser/schemas.py` | Reimplemented as Pydantic models matching our columns. Dropped `price_breaks[]`/`service_tier`/`nre`/`coo` (single-line-item MVP quotes) and added the fields our form actually collects: `currency`, `unit`, `lead_time_days`, `shipping_cost`, `duties`, `taxes`, `discount`, `warranty_months`. |
| **Two-tier missing-field taxonomy** (`MissingFields.per_part` vs `.quote_level`) | `agents/quote_parser/completeness.py` | Reimplemented single-tier (`missing_required` / `missing_recommended`) because MVP quotes have one line item, so the per-part dimension collapses. The *rule set* is preserved: an explicit "none"/"TBD" is an answer; a promise to send later is not; never re-ask an answered field. |
| **`blocking_question` → flag the buyer, don't chase the supplier** (`prompts/response.txt` decision order 1–2–3) | `agents/followup/policy.py` | Reimplemented as a 3-way decision (`skip` / `request_missing_fields` / `remind`) with the same ordering discipline and the same guardrail: a supplier waiting on the buyer is surfaced to the buyer, never chased. |
| **"Ask only for what is genuinely outstanding" + "re-asking an answered question is the most damaging thing you can do"** | `agents/followup/prompts.py` | Kept nearly verbatim in spirit; the prompt is scoped to our field vocabulary and must return JSON so the requested-field list is machine-checkable. |
| **Supplier-facing writing rules** (`prompts/reply_agent.txt`): thank once without flattery, use the supplier's own vocabulary not internal field names ("country of origin", not `coo`), no invented deadlines, 4–8 lines, don't restate their pricing | `agents/followup/prompts.py` | Adopted directly (wording generalised to our field set, signature changed to the buyer's company). |
| **Never recommend a commercial outcome in a follow-up; surface decisions instead** | `agents/followup/prompts.py` + `comparison/recommend.py` | Follow-up emails keep the "do not recommend" rule. The *comparison* agent is the one place allowed to recommend — and it does so only as a ranked suggestion, with `POST /rfqs/{id}/comparison/approve` being the only path to an award (human approval required). |
| **Classification taxonomy** (`rfq_sent` / `supplier_quote` / `supplier_reminder` / `ignore`) | `agents/quote_parser/classify.py` | Reimplemented for our channel: an inbound *form submission* is always `supplier_quote`; free-text notes are classified as `quote_data` / `question` / `other` so a supplier question becomes a buyer flag rather than a reminder. |
| **Long-lead-time flagging** (`long_lead_time_parts`, ≥8 calendar weeks) | `comparison/score.py` | Reimplemented as a lead-time score term plus a `risks[]` entry, driven by our own `LEAD_TIME_RISK_DAYS` threshold. |
| **Eval discipline** (`data/eval_cases/eval_cases.json`, `evals.py`, `docs/eval_report.html`) | `backend/tests/fixtures/*.json`, `backend/tests/test_quote_parser.py` | Reimplemented as a small offline case set: raw note text → expected parsed fields, and raw quote → expected missing fields. No LLM call needed to run them (the deterministic fallback path is what is tested); the LLM path is exercised behind an opt-in marker. |
| **Human-in-the-loop before irreversible action** (`send_reply` only after coordinator brief; buyer flag path) | `backend/app/features/followup/service.py`, `backend/app/features/comparison/router.py` | `AUTO_SEND_FOLLOWUPS=false` queues drafts for approval; `AUTO_SEND_FOLLOWUPS=true` sends reminders but **awards are always blocked** without an `Approval` row. |

**Not reused from ForgeFlow:** `anthropic` SDK, `butterbase/` deployment scripts,
`managed_agent.py`, `simulator.py`, `store.py`, `next-ui/`, `cli.py`, and all
`.eml` sample data. Reason: wrong channel (email inbox vs. web form + webhook), wrong
model vendor (Anthropic vs. OpenAI-compatible free tier), and wrong deployment target.

## 5. Reimplemented from scratch (no source repo covers it)

| Module | Path (app root) | Why new |
| --- | --- | --- |
| Tokenized supplier invitations | `backend/app/features/invitation/**` | Nothing in either repo issues per-supplier public links or tracks `Pending/Submitted/Incomplete/Expired`. |
| Public quote form (supplier-facing) | `public_form/**` | The base repo's frontend is buyer-only and unauthenticated; suppliers must reach a tokenized, mobile-first, login-free surface. |
| Object storage abstraction | `backend/app/core/storage.py` | Base repo has no uploads at all. Needed because Render free tier has no persistent disk. |
| Follow-up scheduler | `backend/app/features/followup/scheduler.py` + `POST /internal/scheduler/tick` | Base repo has no scheduler; ForgeFlow's is GitHub-Actions-over-IMAP. Ours is an in-process interval job **plus** an HTTP tick endpoint so an external free cron can drive it without a paid worker. |
| Comparison engine | `comparison/**` | Base repo ranks by `unit_price × qty` in SQL. The spec needs FX + incoterms + landed-cost + weighted multi-criteria scoring. |
| Buyer auth | `backend/app/features/auth/**` | Base repo has no auth at all (assumes trusted network). |
| CSV/PDF comparison export | `comparison/exporters.py` | New. |
| Alembic migrations | `backend/alembic/**` | Base repo used `Base.metadata.create_all` at startup. Migrations are required to use Neon's direct connection string. |

## 6. Documented assumptions and deviations

* **A1 — sync SQLAlchemy, not `asyncpg`.** The brief lists `asyncpg` as "inherited from
  rfq-comparison-tool", but the repo actually inherits **sync SQLAlchemy + `psycopg` 3**
  (`pyproject.toml`, `core/database.py`). Rewriting every slice to async would be a
  rewrite, not an extension, and would put the working pieces at risk — which the brief
  forbids. **Decision: keep sync `psycopg`.** Rationale: the workload is small
  request-scoped CRUD; `psycopg` 3 is fully supported by Neon's pooled endpoint; and sync
  sessions keep the DB session usable from both `def` and `async def` endpoints (FastAPI
  runs `def` handlers in a threadpool). All LLM/email/storage I/O — the genuinely
  latency-bound work — **is** async (`httpx.AsyncClient`, `asyncio.to_thread` for boto3).
  Documented in the README.
* **A2 — `Base.metadata.create_all` kept at startup *and* Alembic added.** `create_all` is
  retained so `docker compose up` and first-boot on Render work with zero steps; Alembic is
  the authority thereafter. Because `create_all` is additive and never drops or alters,
  the two coexist safely.
* **A3 — public form is a separate SPA, deployed as a second Vercel project.** The brief
  asks for `public_form/` as a separate module *and* for Vercel with `root = frontend/`.
  A second Vercel project with `root = public_form/` satisfies both. Both `vercel.json`
  files are provided.
* **A4 — scheduler lives in the API process.** Render's free tier has no always-on worker,
  and a paid Background Worker would break the free tier. An APScheduler interval job runs
  inside the web service, and the same work is exposed at
  `POST /internal/scheduler/tick` (shared-secret header) so a free external cron can drive
  it reliably even though the service spins down after 15 idle minutes.
* **A5 — FX rates are a static, env-overridable table, not a live feed.** A live FX API is
  another network dependency and another free-tier quota. `comparison/fx.py` ships a
  documented baseline table, overridable via `FX_RATES_JSON`, with the rate and its
  `as_of` date surfaced in the comparison output so a stale rate is visible rather than
  silently wrong.
* **A6 — CAPTCHA is optional and off by default.** `CAPTCHA_PROVIDER=none|turnstile|hcaptcha`.
  Honeypot + per-IP/per-token rate limiting are always on; CAPTCHA needs a site key, which
  an MVP operator may not have, so it must not be a hard startup requirement.
* **A7 — `SECRET_KEY` has a dev default and the app warns loudly in production** when it is
  left at the default. Refusing to boot would break `docker compose up` acceptance.
* **A8 — JWT auth, single-tenant.** One buyer account owns its suppliers and RFQs. There is
  no organisation/team model; `User` is the tenant boundary. Documented rather than
  half-built.
* **A9 — public form reference number** is `SQ-{rfq_number}-{invitation_id:04d}`, generated
  at submission time and stored on the quote so the confirmation page and the buyer
  dashboard agree.

## 7. Build order (each step committed)

1. `INTEGRATION_PLAN.md` + `NOTICE` + app root git repo. → *verify: file exists, tree clean*
2. Freeze the data model: `User`, `Supplier`, `RFQ` (extended), `Invitation`, `Quote`
   (extended), `FollowUp`, `Comparison`, `Approval` + Alembic migration.
   → *verify: `alembic upgrade head` on a scratch SQLite/Postgres, models import*
3. Core services: auth/JWT, storage, email transport, rate limiting, LLM client with
   retry-with-backoff + queue. → *verify: unit tests per module*
4. Pure engines: `comparison/**`, `agents/quote_parser/**`, `agents/followup/**`.
   → *verify: standalone pytest, no DB, no network*
5. Feature slices + routers: `invitation`, `public_form`, `followup`, `comparison`,
   `dashboard`. → *verify: FastAPI `TestClient` end-to-end test of the acceptance path*
6. `public_form/**` supplier SPA. → *verify: `npm run build`*
7. Frontend buyer dashboard extension. → *verify: `npm run build` + `npm run lint`*
8. Deploy configs (`render.yaml`, `vercel.json` ×2, `docker-compose.yml`, `.env.example`)
   + seed script + README. → *verify: `docker compose config` parses; seed script runs*
9. Full test pass + acceptance walkthrough. → *verify: `uv run pytest`, both `npm run build`*

## 8. Acceptance-criteria traceability

| Criterion | Where it is exercised |
| --- | --- |
| Create RFQ, add 3 suppliers, get 3 unique links | `backend/tests/test_acceptance.py::test_full_acceptance_flow` |
| Simulate a supplier submission → quote appears | same, via `POST /public/invitations/{token}/quotes` |
| Auto follow-up for non-responders after deadline | same, via `POST /internal/scheduler/tick` |
| Compare 3 quotes + recommendation | same, via `GET /rfqs/{id}/comparison` |
| File attachment on submission | `backend/tests/test_public_form.py` + local storage backend |
| Honeypot / rate limit / CAPTCHA hook | `backend/tests/test_public_form.py` |
| No SMTP anywhere | `backend/tests/test_email.py::test_no_smtp_ports_in_source` (static assertion) |
| Buyer dashboard | `frontend/src/features/**` (built in `npm run build`) |

---

## 9. Defects found and fixed during the build

Recorded here because the *reason* each one existed is more useful than the fix, and
because every one of them now has a regression test in
`backend/tests/test_regressions.py` or a named test in the suites the review produced.

**Found by an adversarial review of the domain packages** (the reviewer wrote failing
tests rather than touching the source):

1. **A per-unit price converted in the same direction as a quantity.** 1 t = 1000 kg,
   so a per-tonne *price* must be divided by 1000; it was multiplied. A mass-quoted
   supplier came out 10⁶ more expensive than a count-quoted one — enough to invert an
   award. Fixed by deriving the multiplier from physical unit sizes
   (`size(target) / size(quoted)`) instead of a hand-written factor table, which is a
   shape that cannot be flipped by accident.
2. **Negative-phrase matching was substring-based and included `"na"`.** "final",
   "Canada", and "maintenance" all meant "no answer yet", so `parse_money("final price
   3.00")` returned `None`: a stated price silently discarded. Now word-boundary
   matched.
3. **`parse_currency` invented currencies from ordinary words.** Upper-casing the
   whole input and taking any three-letter token turned "We try to ship quickly." into
   `TRY` — the Turkish lira, which *is* in the FX table — so the engine converted at
   the lira rate rather than reporting the quote incomparable. A confidently wrong
   landed cost is worse than a missing one. Codes must now be uppercase in the source
   (or the input must be the code alone), and a non-answer is never a currency.
4–5, 11. **`ParsedQuote.classification` defaulted to `"quote_data"`.** The heuristic
   layer always carried that default, so it won the merge and overrode the classifier —
   meaning that with no LLM configured (the documented free-tier case, and the
   configuration the test suite runs in) a supplier waiting on the buyer was recorded
   as ordinary quote data and then **chased**. That is precisely the failure the
   escalate-don't-chase rule exists to prevent. Classification is now `None` until a
   layer actually decides, and `classify_text` no longer treats a bare "price" in a
   question as data.
6. **Merged provenance reported whichever layer ran last**, so a quote whose price came
   from the form and a term from the LLM was labelled `"heuristic"`. Now names the
   combination, agreeing with `field_sources`.
7. **The MOQ coercion bypassed `parse_moq`**, so "No MOQ" recorded a *gap* rather than
   an answer and scored 55 instead of 100 — penalising the supplier who answered.
8. **The static-FX caveat only inspected `results[0]`**, so a batch containing a
   converted EUR quote raised no warning at all whenever a USD quote won. The caveat now
   covers the batch and names the suppliers; an Incoterms-rebasing caveat was added
   alongside it.
9. **The missing-fields email hard-coded "this is the only item we still need"**
   regardless of how many fields were outstanding — a false statement sitting directly
   under a correct list.
10. **The follow-up label fallback could surface internal snake_case field names** to a
    supplier. Always derived through `label_for` now.

**Found by live verification** (a real uvicorn process, real HTTP, CORS with two
distinct origins):

11. **An incomplete quote could be recommended over a complete one**, simply because it
    was cheaper. Complete quotes now always rank ahead of incomplete ones regardless of
    score; incomplete quotes are still scored and still listed immediately below, and
    the rationale explains the ordering by name when it changed the outcome.
12. **The tie-break note compared scores across differently classified quotes**, which
    printed "within -3.5 points".

**Found by the demo seed script** (which is why it drives the real ingestion pipeline
rather than inserting fixtures):

13. **A scoring run emitted one row for three quotes**, and a supplier who had just
    submitted a partial quote was **silently never chased**. Root cause: with
    `expire_on_commit=False`, a long-lived session handed back *cached* relationship
    collections, so `rfq.quotes` and `invitation.quote` were stale. Fixed by restoring
    SQLAlchemy's default (`expire_on_commit=True`) and querying explicitly in the two
    places where the collection is load-bearing.
14. **The RFQ counters double-counted.** `incomplete_count` was treated as an
    alternative to `responded_count` rather than a subset, so the dashboard's
    "Incomplete" figure read zero. It is now a subset, and both are derived from the
    *quote's* completeness rather than a potentially stale invitation status.

**Found by the pre-deployment review.** The theme is "green locally, broken in
production", because the test suite runs on SQLite while production is PostgreSQL:

15. **`is_current IS true` on an Integer column.** Four flag columns were declared
    `Integer` while the application filtered them with `.is_(True)`, which SQLAlchemy
    compiles to ``col IS true``. PostgreSQL rejects that outright —

    ```
    ERROR: argument of IS must be boolean, not type integer
    ```

    — so `repository.latest_for_rfq` would have failed, taking down the entire
    comparison feature: every read, every scoring run, and every award approval.
    SQLite accepts `IS 1` without complaint, so all 300 tests passed. The columns are
    now real `Boolean`, and `backend/tests/test_postgres_compat.py` compiles the
    queries and the schema against the PostgreSQL dialect so this class of bug fails
    in CI instead. Verified by reintroducing the bug and watching the guard catch it.
16. **Boolean `server_default` was SQLite-flavoured.** Autogenerate run against SQLite
    wrote `sa.text('0')`, and `BOOLEAN DEFAULT 0` is invalid on PostgreSQL ("column is
    of type boolean but default expression is of type integer"). The migration would
    apply locally and fail on Neon. Switched to `sa.text('false')`/`('true')`, which
    both dialects accept, and a test now asserts every boolean `server_default` is a
    real boolean literal.
17. **`docker compose up` could not reach the database.** The root `.env.example`
    (which Compose reads) set `DATABASE_URL=…@localhost:5432/…`, but inside the backend
    container `localhost` is the container itself and the database is the `postgres`
    service. Every request would have failed with a connection error on a fresh clone.
    The Compose template now uses the service hostname; `backend/.env.example` keeps
    `localhost` because there is no container in native development. Confirmed with
    `docker compose config`.
18. **Attachment links 404'd in the default configuration.** `LocalStorage.url_for`
    hands out `/files/<key>`, but the route serving that path refused to serve the
    local backend — reasoning that local files are "dev only". Local storage *is* the
    default, so every upload a supplier made and every link a buyer clicked returned
    404. The route now serves any backend; access stays capability-based on the
    unguessable key, and a test downloads the exact URL the API returns.
19. **A test file was not valid UTF-8.** `test_followup_policy.py` held a lone `0x97`
    byte (Windows-1252's em dash) plus three mojibake em-dash sequences, written by a
    `Set-Content` call that used the ANSI codepage. Repaired, and a repo-wide scan
    confirms every text file is now valid UTF-8.
20. **`render.yaml` pinned a Python version that contradicted `.python-version`**
    (`3.13.7` vs `3.13`): two sources of truth for one fact, and an exact patch Render
    cannot resolve fails the build before anything runs. The env var is gone, leaving
    the file as the single source. Also swapped the newer `autoDeployTrigger` key for
    the long-standing `autoDeploy`, because an unrecognised key fails blueprint
    validation outright rather than being ignored.
21. **CI referenced `secrets` in a step-level `if`**, which GitHub does not reliably
    permit and which rejects the workflow rather than skipping the step. The deploy
    hooks are now mapped to `env` and tested with `env.X != ''`. CI also uses `python3`
    rather than `python`, and installs PyYAML before validating `render.yaml` — the
    previous fallback silently skipped that check when the import failed.
22. **The Docker image ran `uv run` at container start**, making startup depend on uv's
    resolution logic and, in a misconfigured case, on network access. The virtualenv is
    now on `PATH` and the container execs `uvicorn` directly.

Dead code removed in the same pass: a speculative `GET /quotes/{id}/line-items` alias
that duplicated `GET /quotes/{id}`, two unused private helpers, an unused `warm_up()`
whose docstring claimed a caller that did not exist, and 14 unused imports. Lint
(correctness rules only — `F` and `E9`) is now part of CI.
