# Supplier Quote Autopilot — open-source RFQ and quote comparison for facilities management and building services procurement

Run a request for quotation, give every supplier their own private web form, chase the
ones who go quiet automatically, compare what comes back on total cost rather than
headline price, and award as a human.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.13](https://img.shields.io/badge/python-3.13-3776AB.svg?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg?logo=fastapi&logoColor=white)
![React 19](https://img.shields.io/badge/UI-React%2019-61DAFB.svg?logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/database-PostgreSQL-4169E1.svg?logo=postgresql&logoColor=white)
![424 tests passing](https://img.shields.io/badge/tests-424%20passing-brightgreen.svg)
![Deploy: Neon + Render + Vercel](https://img.shields.io/badge/deploy-Neon%20%2B%20Render%20%2B%20Vercel-3DDC84.svg)
![LLM: Groq / OpenRouter / Gemini](https://img.shields.io/badge/LLM-Groq%20%7C%20OpenRouter%20%7C%20Gemini%20(free%20tiers)-blueviolet.svg)

---

## Contents

1. [What is this?](#1-what-is-this)
2. [Who it is for](#2-who-it-is-for)
3. [Features](#3-features)
4. [Why it exists, and how it differs](#4-why-it-exists-and-how-it-differs)
5. [A tour of the screens](#5-a-tour-of-the-screens)
6. [Guardrails: what it will not do](#6-guardrails-what-it-will-not-do)
7. [Quick start](#7-quick-start)
8. [Deployment: Neon + Render + Vercel](#8-deployment-neon--render--vercel)
9. [Configuration reference](#9-configuration-reference)
10. [Architecture](#10-architecture)
11. [Testing](#11-testing)
12. [FAQ](#12-faq)
13. [Roadmap: what is not built yet](#13-roadmap-what-is-not-built-yet)
14. [GitHub topics](#14-github-topics)
15. [License](#15-license)
16. [Credits](#16-credits)

---

## 1. What is this?

**Supplier Quote Autopilot** is open-source **RFQ software** for facilities management
and building services procurement: it runs a **request for quotation**, gives every
invited supplier their own private web form, chases the ones who go quiet, and compares
what comes back on total cost rather than headline price. It is built for **building
maintenance tendering** and **minor works** — planned preventive maintenance and reactive
repairs, electrical, mechanical (ACMV/HVAC), plumbing and sanitary works, painting and
decorating, plus carpet and flooring, roofing and waterproofing, fire protection, lift
and escalator, CCTV and security, cleaning, pest control, landscaping and waste — so site
name and address, access notes and response-time (SLA) terms are first-class fields
rather than afterthoughts. Defaults are Singaporean: **SGD**, **GST**, and an
accreditation list covering LEW, PUB, BCA, bizSAFE and ISO; currency, tax and
accreditations are all configurable if you buy somewhere else. **Quote comparison**
normalizes currency, rate basis and terms, adds the callout or attendance charge, derives
GST when a supplier states a rate rather than an amount, scores each supplier on nine
criteria — price, response time, mobilisation time, accreditations, payment terms,
minimum callout, rate validity, defect liability period and supplier risk — using
services-first default weights you can override, and writes a recommendation with its
rationale — while the award itself stays a human decision. It also keeps a reusable
directory for **supplier management**, runs **automated supplier follow-up** on a scheduler
with an approval queue, needs **no AI key at all** to work end to end, and the whole thing
fits inside **free tier deployment** on Neon + Render + Vercel.

---

## 2. Who it is for

- **Facilities managers** running planned preventive maintenance, reactive repairs and
  ad-hoc minor works across one site or fifty.
- **Building owners, MCST / management corporations and JMBs** who need a defensible
  three-quote process they can show an auditor or a council.
- **Property and estate managers** obtaining quotes on behalf of owners or tenants.
- **M&E contractors** coordinating subcontractors across trades — electrical, ACMV,
  plumbing, fire, lift, security.
- **SME procurement and admin teams** currently running RFQs through email, WhatsApp and
  a spreadsheet that nobody can reconstruct six months later.
- **Anyone who has to run a three-or-more-quote process for minor works** and needs to
  explain, in writing, why the winner won.

---

## 3. Features

### RFQ management

- Create an RFQ with a scope, specification, quantity or lump sum, rate basis (per job,
  per visit, per hour, per day, per point, per unit, per sqm, per metre, per month, lump
  sum), site name and address, access notes, submission deadline, and the exact list of
  fields a quote must contain to count as complete.
- Two procurement types, each with its own required-field contract, and a services RFQ is
  the default. **Services** require the rate (`unit_price`), the rate basis (`unit`), the
  currency, the response time (SLA), payment terms and rate validity. **Goods** require the
  unit price, currency, production lead time, MOQ, payment terms, Incoterms and validity
  date. MOQ and Incoterms are deliberately absent from the services contract: a minimum
  callout is a charge that already shows up in the price, not a quantity gate, and nothing
  is being shipped.
- Service categories out of the box: building maintenance and handyman, electrical minor
  works, mechanical minor works, plumbing and sanitary minor works, painting and
  decorating, ACMV/air-conditioning, fire protection, lift and escalator, CCTV and
  security, roofing and waterproofing, flooring and carpet, cleaning, pest control,
  landscaping, waste management, signage, general building works, testing and
  commissioning — plus a goods path (spare parts, electrical components, plumbing
  fittings, building materials, tools, safety and PPE) if you buy parts too.
- Declare which accreditations you require from a list of common Singapore credentials
  (EMA Licensed Electrical Worker, PUB Licensed Plumber, BCA Registered Contractor,
  bizSAFE Level 3 and Star, ISO 9001 / 14001 / 45001, SCDF fire safety, WSH Act, Work at
  Height, Confined Space, Lift & Escalator permit holder) or free text.
- Every picker and default — the 19 service categories, the 7 goods categories, the 10
  service rate bases, the 8 goods units, the 13 common accreditations, the required-field
  contract per type, the required-field labels and the nine scoring criteria with their
  per-type default weights — is served by one unauthenticated call, `GET /meta/options`. The
  buyer dashboard reads it directly; the supplier form is handed the same vocabulary on its
  invitation preview (`procurement_type`, `category`, `rate_bases`, `required_fields`,
  `required_field_labels`, `required_accreditations`, `tax_note`), so the two applications
  cannot drift apart.
- The dashboard rolls up what is outstanding across the whole workspace.

### Supplier invitations and tokenized forms

- Add suppliers inline or from a reusable directory; each one instantly gets a **unique
  tokenized web-form link**.
- **No account, no sign-up, no app** for the supplier. Mobile-first, branded with the
  buyer's company name, reachable from the link in the invitation email.
- Track `Pending` / `Submitted` / `Incomplete` / `Expired`, including whether a supplier
  **opened the form without submitting**.
- Resend, withdraw, or let a link expire; the token grants exactly the right to answer one
  RFQ and nothing else in the buyer's workspace.
- Attachments on submission, validated by size, extension and content type, with HTML
  always rejected.
- The submission contract accepts **both spellings** of the three service field names a
  hand-rolled client is most likely to guess wrong: the canonical `response_time_hours`,
  `materials_markup_pct` and `compliance_accreditations` (a list or a delimited string) plus
  the aliases `response_time`, `materials_markup` and `accreditations`. Unknown JSON keys are
  ignored by the schema, so without the aliases a client that guessed would receive a 201
  while its SLA was silently dropped — and since a services RFQ requires a response time, the
  quote would be stored incomplete and the buyer would chase a supplier who had already
  answered.

### Follow-up automation

- A scheduler chases non-responders and suppliers whose quotes are missing required
  fields, plus a reminder shortly before the deadline.
- Reminders are LLM-drafted when a key is configured and deterministic templates when it
  is not. **By default they are queued as drafts for your approval** before anything is
  sent.
- A supplier who is waiting on the buyer for a specification or a volume is **escalated to
  the buyer, never chased** — chasing them asks for something they have already said they
  cannot give.
- An explicit "none" counts as an answer; "TBD" and a promise to send it later do not.
- Complete communication log per invitation and per RFQ.
- Runs inside the web process and, because free-tier services sleep, the same sweep is
  exposed at `POST /internal/scheduler/tick` so an external free cron can drive it.

### Comparison and scoring

- Normalizes currency (a documented, dated, overridable FX table), rate basis and terms
  before anything is ranked. Rate bases that mean the same thing commercially — "per job",
  "lump sum" and "per service" — collapse to one basis, so a supplier who writes "lump sum"
  against a "per job" RFQ is not excluded over a choice of words. "per visit", "per point",
  "per month", "per sqm" and "per unit" stay distinct, and a quote on a genuinely different
  basis is excluded from ranking with a message that shows the buyer what was asked for and
  what came back — for example `Quoted in 'service' but this RFQ is priced in 'per visit' —
  no defensible conversion exists, so this quote is excluded from ranking. Ask the supplier
  to re-quote.` The RFQ side of that message is the buyer's own wording; the supplier side is
  the normalized rate basis the parser recorded, which is usually the canonical code. Two
  units of the same kind (per hour against per day) are converted instead, with the factor
  stated in the quote's notes.
- Works out the works / landed cost as `unit_price × quantity + shipping + callout + duties
  + taxes − discount`, then rebases the total onto the RFQ's Incoterms basis when one is set.
  The callout or attendance charge sits in the same slot as freight — a real cost of getting
  the job done that is not part of the measured works. When a supplier states a GST rate but
  no tax amount, GST is derived from that rate and `breakdown.tax_derived_from_rate` records
  which of the two happened; a quote that states no rate at all is costed at the RFQ's own
  `gst_rate`, so every quote in one RFQ is ranked on the same tax basis. An hourly labour
  rate and a materials markup percentage are carried through and shown, and a markup above
  20% is flagged, but neither enters the cost formula — the total is built only from money
  the supplier actually quoted.
- Scores nine criteria, each 0–100 with higher always better, weighted per RFQ: `price`,
  `response_time`, `lead_time`, `compliance`, `payment_terms`, `moq`, `validity`, `warranty`,
  `risk`. Price is scored **relative to the other quotes in the batch** (the cheapest scores
  100); the other eight are scored against fixed thresholds, so a quote's score does not move
  when an unrelated supplier is added. A criterion a supplier did not state scores the neutral
  55.0 rather than zero — a gap to chase is not evidence of bad service.
- Default weights follow the procurement type, so a services RFQ that never sets weights
  still scores response time and accreditation:

  | Criterion | Services | Goods |
  | --- | --- | --- |
  | `price` | 0.40 | 0.45 |
  | `response_time` | 0.15 | 0.00 |
  | `risk` | 0.15 | 0.10 |
  | `compliance` | 0.10 | 0.00 |
  | `lead_time` | 0.05 | 0.20 |
  | `payment_terms` | 0.05 | 0.10 |
  | `validity` | 0.05 | 0.05 |
  | `warranty` | 0.05 | 0.05 |
  | `moq` | 0.00 | 0.05 |

- **Why those weights.** Price still dominates, because it is the number the buyer has to
  justify — but on a maintenance job the real differentiators are how fast someone turns up
  and whether they are allowed to do the work at all. A cheap contractor without an EMA
  Licensed Electrical Worker cannot legally carry out electrical minor works, so price alone
  would recommend the wrong supplier. `moq` is weighted **zero** for services: a minimum
  callout is a charge that already appears in the price, not a quantity gate, so it is scored
  and displayed but never moves the ranking. The goods column is the original weighting,
  unchanged, and a goods RFQ scores exactly as it always did.
- A quote missing an accreditation the RFQ required has its composite score **capped at
  25.0**. It stays visible and rankable — a quote is never silently dropped — but it cannot
  win on price, and the credentials it does not hold are named in plain words on the result
  and as a risk flag.
- A **complete quote always ranks ahead of an incomplete one**, and a quote that cannot be
  normalized is never silently dropped — it appears with a reason.
- Every comparison records the FX rates and their as-of date, flags any quote whose terms
  were rebased, and names what is missing.
- Export CSV and PDF; write a recommendation with a rationale.
- The buyer can override the recommendation and must give a written reason.

### AI assistance

- Any OpenAI-compatible provider — **Groq by default** (free tier), with OpenRouter and
  Google Gemini as documented alternatives. Switching provider means changing three
  environment variables.
- Retry with exponential backoff honouring `Retry-After`, request spacing for free-tier
  rate limits, a concurrency cap and a per-sweep call ceiling. Models recognised as
  reasoning models also get a bounded thinking budget (`LLM_REASONING_EFFORT=low` by
  default), because a long provider-default trace consumed the whole completion budget and
  the provider then rejected the request — which made every LLM feature fall back to its
  deterministic path without saying why. A generous `max_tokens` on the JSON calls is what
  makes the two work together.
- Quote parsing is **verbatim-or-null**: a value is recorded only when it appears in the
  supplier's own words, and each extracted value cites the phrase it came from.
- **A deterministic fallback at every call site.** With `LLM_API_KEY` empty the product
  works completely: quote parsing, follow-up drafting and the comparison narrative all
  fall back to deterministic implementations.

### Deployment

- Free tier end to end: **Neon** (PostgreSQL) + **Render** (API) + **Vercel** (two static
  SPAs — buyer dashboard and supplier form).
- **No SMTP anywhere.** Email goes over an HTTPS API (Resend, SendGrid, Mailgun or Brevo),
  because Render's free tier blocks outbound ports 25, 465 and 587. A test and a CI step
  assert that `smtplib` never appears in the source.
- File uploads use local storage in development and any S3-compatible store in production
  (Cloudflare R2, Backblaze B2, Neon Object Storage, MinIO, AWS), because Render's free
  tier has no persistent disk.
- Docker Compose for local development with PostgreSQL, plus Alembic migrations and a CI
  workflow.

---

## 4. Why it exists, and how it differs

Most three-quote processes for minor works live in an email thread and a spreadsheet. That
works until someone asks why the winner won, or a supplier goes quiet for two weeks, or
two quotes arrive in different currencies on different rate bases. Commercial procurement
suites solve that, but they are priced and shaped for enterprises with a sourcing
department.

| | Email + spreadsheet | Commercial procurement suite | Supplier Quote Autopilot |
| --- | --- | --- | --- |
| Cost to start | Free | Per-seat / per-module licensing, procurement-led onboarding | Free to self-host; free tier covers a small team |
| Getting a quote out of a supplier | Send a form you built yourself, hope it comes back filled in | Supplier portal account for every supplier | Tokenized link, **no supplier account**, mobile-first |
| Chasing non-responders | Manual, and the first thing to slip | Configurable, but usually assumes suppliers log in | Automated, with drafts queued for your approval by default |
| Comparing quotes | Manual currency and rate-basis arithmetic | Yes | Landed / works cost, weighted scoring, CSV and PDF export |
| Why the winner won | Whoever wrote the email | Audit trail, configured by an administrator | Written rationale stored with the decision, exportable |
| Who awards | Whoever clicks send | Approval workflow | **A human, always** — `POST /rfqs/{id}/comparison/approve` requires an authenticated buyer and a written reason |
| Works with no AI key | n/a | n/a | Yes — deterministic fallbacks everywhere |
| Email requirements | Any mail provider | Usually SMTP or their own sending | HTTPS API only; **no SMTP dependency** |
| Where this project is weaker | — | Multi-entity, roles, catalogues, punchout, contract management, spend analytics, ERP integration | Single buyer account per tenant, one scope per RFQ, no supplier accounts or portal, no contract or catalogue management, static FX table |

The honest summary: this is a focused tool for running a defensible quote round on
maintenance and minor works, not a replacement for a full source-to-pay platform. If you
need multi-entity approval hierarchies, supplier onboarding workflows, catalogue punchout
or spend analytics, you need the commercial suites — and if you just need to stop losing
quotes in an inbox, you do not.

---

## 5. A tour of the screens

**Signing in.** The buyer dashboard has a public login and a registration page. Register
with an email and password and you own a workspace; there is one buyer account per tenant,
and every list you see is scoped to your account. Another tenant's record returns 404, not
403 — the API never confirms that something it will not show you exists.

**The dashboard** is the workspace roll-up: how many RFQs are open, how many invitations
are pending, submitted, incomplete or expired, and what is waiting on you. It is the first
thing that tells you a quote round is stalling.

**The RFQ list** shows every request with its response counters — invited, responded,
incomplete, expired — plus the deadline and status. Create a new RFQ from here.

**Creating an RFQ** is a form that asks for the scope and specification, the quantity or
lump sum and the rate basis, the site name and address, access notes, the submission
deadline, the accreditations you require, and the required-field contract: the exact list
of fields a quote must contain to count as complete. That list is what the follow-up engine
is allowed to ask suppliers for, so it is worth a moment's thought. **Service** is the
default procurement type, so the form opens on the service vocabulary with a "per job" rate
basis; switching the toggle to **goods** swaps the rate bases for units of measure, swaps
the required-field contract to the goods one, and restores MOQ, Incoterms and production
lead time as first-class fields. Suppliers can be added
inline or picked from your directory in the same step, and each one immediately gets a
tokenized form link.

**The RFQ detail page** has four tabs. *Suppliers* lists invited suppliers with their
status, whether the form was opened and not submitted, the tokenized link, and resend and
withdraw actions. *Quotes* shows what came back — raw figures as submitted alongside the
normalized values, the cost breakdown, and which required fields are missing. *Comparison*
is the side-by-side grid, the weighted scores, the caveats (FX rate and as-of date, any
rebasing, anything that could not be normalized), the written recommendation, the CSV and
PDF exports, and the award control. *Follow-ups* is the communication log: every message
sent, every draft waiting for approval, and every escalation where a supplier is blocked on
you rather than the other way round.

**The suppliers directory** is reusable: names, contact details, risk rating, and response
statistics built up from every RFQ they have been invited to. It is how you learn that a
particular contractor never answers after three days.

**The supplier form** is a different application on a different origin, and the supplier
never signs in. They open a link, see who is asking, for what, whether there is a site
visit or access restriction, and by when. They enter the price and rate basis, currency,
response or attendance time, payment terms, validity, callout charge, compliance
accreditations, defect liability period and notes, and attach a quote PDF, spec sheet or
licence. A submission that leaves a required field blank is accepted and marked
*Incomplete* rather than rejected — that is deliberate, because a partial quote you can
chase beats a form the supplier abandons. They finish on a confirmation page with a
reference number (`SQ-<rfq number>-<invitation id>`) and the buyer's contact details, and
they can return to the same link to amend their answer.

**Nothing is auto-awarded.** The comparison recommends; the buyer decides and writes down
why.

---

## 6. Guardrails: what it will not do

These are enforced in code, not by convention or by prompt instruction.

- **Never auto-award.** `POST /rfqs/{id}/comparison/approve` is the only path to an award,
  and it requires an authenticated buyer and a written reason. Nothing in the scheduler,
  the parser or the LLM can reach it.
- **Never silently drop a supplier.** A quote that cannot be normalized (unknown currency,
  incompatible rate basis) still appears in the comparison, marked not comparable, with
  the reason. Omitting a supplier from a comparison is the failure mode that costs money.
- **Never rank an incomplete quote above a complete one.** An incomplete quote is missing
  exactly the fields — callout, payment terms, validity — that would change its own cost
  and terms, so it cannot win a comparison it is not fully entered into. It is still scored
  and still listed, immediately below, and when the rule changes the outcome the rationale
  says so by name.
- **Never let a non-compliant quote win on price.** A quote that does not hold an
  accreditation the RFQ required has its composite score capped at 25.0 and the shortfall
  named in plain words. It is still shown and still ranked — the buyer may want to see it —
  but it cannot be recommended on price alone. A contractor without an EMA Licensed
  Electrical Worker cannot lawfully do electrical minor works, so a cheap bid from one is a
  compliance problem rather than a saving.
- **Never chase a supplier who is blocked on the buyer.** A supplier waiting for a
  specification, a site visit or a volume is escalated to the buyer instead.
- **Never re-ask an answered question.** An explicit "none" is an answer; "TBD" is not.
- **Never invent a number.** Quote extraction is verbatim-or-null with the source phrase
  recorded, and the comparison narrative receives an already-computed scoring run with
  instructions not to introduce figures of its own.
- **Never make a commercial claim in a follow-up email.** A model that volunteers "your
  quote is competitive" has its output rejected in favour of the deterministic template.
- **Always state the caveats.** Every comparison records its FX rates and their as-of date,
  flags any quote whose terms were rebased, and names what is incomplete or incomparable.
- **No SMTP, ever.** Asserted by a test and by a CI step.

---

## 7. Quick start

Two paths. Both run the same three services: the API on `:8000`, the buyer dashboard on
`:5173`, the supplier form on `:5174`.

### Windows, one command (SQLite — nothing to install but uv and Node)

From a plain **Command Prompt**, in the repository root:

```cmd
dev.cmd
```

That is the whole thing. It checks your toolchain, creates `backend\.env` from
`backend\.env.dev` (SQLite, console email, no API key), installs dependencies on the first
run, loads the demo workspace, starts all three services in their own windows, and prints
the buyer login **and every supplier's tokenized form link** — the one thing you cannot
know without asking the database, because the token is generated at invitation time.

```
  BUYER DASHBOARD       http://localhost:5173
  SUPPLIER FORM LINKS   http://localhost:5174/quote/<rfq_id>/<token>
  API DOCS              http://localhost:8000/docs
```

| Command | What it does |
| --- | --- |
| `dev.cmd` | Start everything (installs and seeds on the first run) |
| `dev.cmd key` | **Paste your LLM API key** — prompts, writes it, restarts, verifies |
| `dev.cmd llm` | Check whether the configured LLM key actually works |
| `dev.cmd open` | Re-open the UI in your browser without restarting anything |
| `dev.cmd reset` | Wipe the database, re-seed the demo, then start |
| `dev.cmd seed` | Load the demo workspace without starting anything |
| `dev.cmd links` | Re-print the links for an already-running instance |
| `dev.cmd stop` | Stop everything, including leftover windows from earlier runs |

Each service opens in its own window so you can read its log; closing a window stops that
service. Email is logged, never sent, so no real supplier address is contacted.

An LLM key is optional. Drop a free Groq key in with `dev.cmd key` and restart to swap the
deterministic fallbacks for LLM-written reminders and comparison summaries; confirm it with
`dev.cmd llm`, which sends a real request and tells you whether a failure is a **key**
problem or a **model** problem (providers retire model ids, and a retired id fails every
request with `model_not_found` — that reads like a broken key but is not one).

### Docker Compose (PostgreSQL)

The same stack with **PostgreSQL** instead of SQLite. Requires Docker and Docker Compose.

```bash
cp .env.example .env
# Minimum viable edit: set SECRET_KEY.
#   python -c "import secrets; print(secrets.token_urlsafe(48))"
# Everything else has a working default; EMAIL_PROVIDER=console logs mail instead of
# sending it, and an empty LLM_API_KEY uses the deterministic AI fallbacks.

docker compose up --build
```

| Service | URL |
| --- | --- |
| Buyer dashboard | http://localhost:5173 |
| Supplier quote form | http://localhost:5174/quote/`<rfq_id>`/`<token>` |
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Health | http://localhost:8000/health |

Then create an account in the dashboard, or load the demo workspace:

```bash
docker compose exec backend uv run python -m scripts.seed_demo --run-scheduler
```

That prints a working supplier link and the demo login. Optional extras:

```bash
docker compose --profile s3 up      # adds MinIO on :9000 (console :9001) so the
                                    # production upload path can be exercised locally
docker compose exec backend uv run alembic upgrade head   # apply migrations manually
docker compose down                 # stop
docker compose down -v              # stop and delete the database volume
```

The image is built with `uv sync --no-dev`, so running the test suite inside the container
means uv first fetching the dev dependencies — it works, but running the suite on the host
(`cd backend && uv run pytest -q`) is faster and is the documented path.

Compose service names, should you need them directly: `postgres`, `backend`, `frontend`,
`public_form`, and `minio` + `minio-init` behind the `s3` profile. A one-shot `migrate`
service runs Alembic before the backend starts, so a fresh clone comes up with a correct
schema.

### Running the pieces by hand

```bash
# backend (needs PostgreSQL — `docker compose up postgres` is fine)
cd backend
cp .env.example .env            # DATABASE_URL already points at localhost:5432
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# buyer dashboard                # supplier form
cd frontend                      cd public_form
npm install                      npm install
echo "VITE_API_URL=http://localhost:8000" > .env
npm run dev                      npm run dev
```

The repository keeps three importable top-level packages — `backend/`, `agents/`,
`comparison/` — and `backend/app/__init__.py` puts the repository root on `sys.path`, so
`uv run …` from `backend/` works with no `PYTHONPATH` configuration.

Details for each surface are in [backend/README.md](backend/README.md),
[frontend/README.md](frontend/README.md) and [public_form/README.md](public_form/README.md).

---

## 8. Deployment: Neon + Render + Vercel

Everything below fits in the free tier of all three services. Total cost: **$0**. Total
credit cards required: **0**.

The step-by-step for pushing the repository to GitHub and wiring these services up is in
[GITHUB_SETUP.md](GITHUB_SETUP.md). This section is the shape of the deployment and the
gotchas that actually bite.

```
   ┌──────────────┐   ┌──────────────┐
   │  Vercel      │   │  Vercel      │
   │  frontend/   │   │  public_form/│
   │  (buyers)    │   │  (suppliers) │
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

**1 · Neon (database).** Sign up at <https://neon.tech> (no credit card) and create a
project. Neon gives you **two** connection strings and you need both:

```
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@ep-xxx-pooler.REGION.aws.neon.tech/DBNAME?sslmode=require
DATABASE_URL_DIRECT=postgresql+psycopg://USER:PASSWORD@ep-xxx.REGION.aws.neon.tech/DBNAME?sslmode=require
```

The **pooled** hostname contains `-pooler` and is what the app uses. The **direct** one is
used only by Alembic, because Neon's pooler runs PgBouncer in transaction mode and
Alembic's DDL and `alembic_version` bookkeeping do not tolerate that reliably. Neon's
connection widget includes `?sslmode=require` — if your copy somehow does not, add it, since
Neon refuses a non-SSL connection. Otherwise **paste both strings exactly as given**: the app
rewrites a bare `postgresql://` onto `postgresql+psycopg://` itself, because SQLAlchemy would
otherwise look for `psycopg2`, which this project does not install. Free tier: 0.5 GB storage,
100 CU-hours/month, and compute that **scales to zero after 5 idle minutes**, so the first
request after a quiet period takes a few seconds. `/health` reports the database state so a
cold start is distinguishable from an outage.

**2 · Render (API).** `render.yaml` is committed at the repository root and provisions the
backend with variables pre-declared.

1. Render dashboard → **New → Blueprint** → connect the repository.
2. Fill in the variables marked `sync: false`. The two that must be right for the service to
   boot are `DATABASE_URL` and `DATABASE_URL_DIRECT`; the four that must be right for
   invitation links to work are `BACKEND_URL`, `FRONTEND_URL`, `PUBLIC_FORM_URL` and
   `ALLOWED_ORIGINS`.
3. **Decide on email and attachments before you deploy.** `render.yaml` turns both on —
   `EMAIL_PROVIDER=resend` and `STORAGE_BACKEND=s3` — because leaving them off is wrong in
   production. But `resend` needs `EMAIL_API_KEY` and a verified `MAIL_FROM`, and `s3` needs
   the `S3_*` credentials, and **neither fails at boot**: the service starts, `/health` reports
   `"configured": false` for each, and the first supplier invitation or file upload is what
   breaks. Either supply the credentials, or switch both off for a first run:
   `EMAIL_PROVIDER=console` (messages are logged, and you copy each supplier's link from the
   dashboard's suppliers tab) and `STORAGE_BACKEND=local` (uploads work but do not survive a
   redeploy, and the app logs a warning saying so).
4. `LLM_API_KEY` is **optional** — see [Where the AI key goes](#where-the-ai-key-goes).
5. `SECRET_KEY` and `SCHEDULER_SECRET` are **auto-generated** — read them from the
   dashboard afterwards. You need `SCHEDULER_SECRET` for the external cron.
6. Deploy.

If you would rather not use the blueprint, the manual Web Service settings are: root
directory `backend`, runtime Python 3, build command
`pip install --upgrade pip && pip install -r requirements.txt`, start command
`uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health check path `/health`, plan
free. `requirements.txt` is **generated from `uv.lock`**, and CI fails if the two drift.

**3 · Run the migrations against the direct string**, once, from your machine. Set only
`DATABASE_URL_DIRECT` — `alembic/env.py` reads it first:

```powershell
cd backend
$env:DATABASE_URL_DIRECT = "postgresql://…@ep-xxx.REGION.aws.neon.tech/DBNAME?sslmode=require"
.\.venv\Scripts\python.exe -m alembic upgrade head     # or: uv run alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current          # -> f1de0d1828be (head)
```

That is the Windows form of the same two commands. In bash or zsh it is
`DATABASE_URL_DIRECT="…" uv run alembic upgrade head`.

The app also runs `Base.metadata.create_all` at startup, so a first boot works with no manual
step — that is a convenience, not the source of truth: `create_all` only ever *adds* missing
tables and never alters or drops, so it cannot conflict with Alembic. Once migrations
exist, Alembic is the authority.

**4 · Vercel (both frontends).** Two separate projects, because suppliers must reach a
different origin from buyers.

- Buyer dashboard: **Root Directory** `frontend`, framework preset Vite, environment
  variable `VITE_API_URL` = your Render URL.
- Supplier form: repeat with **Root Directory** `public_form`, its own project name, and
  the same `VITE_API_URL`.

Each app's `vercel.json` handles SPA routing so a deep link like `/rfqs/12` does not 404 on
refresh.

**5 · Point everything at everything.** Back on Render, set and redeploy:

```env
BACKEND_URL=https://your-api.onrender.com
FRONTEND_URL=https://your-dashboard.vercel.app
PUBLIC_FORM_URL=https://your-supplier-form.vercel.app
ALLOWED_ORIGINS=https://your-dashboard.vercel.app,https://your-supplier-form.vercel.app
```

### The gotchas

| Gotcha | Why it matters |
| --- | --- |
| **Pooled vs direct Neon string** | The app needs the pooled (`-pooler`) string; Alembic needs the direct one. Using pooled for migrations hangs or errors. |
| **Confirm the currency and the tax rate** | `BASE_CURRENCY` and `DEFAULT_GST_RATE` decide what every comparison is built on. This checkout ships **SGD and 9% GST** in the application defaults, `.env.example` and `render.yaml` alike — change all three if you buy in another market, or a Singapore workspace ends up comparing in the wrong currency. |
| **No persistent disk on Render** | `STORAGE_BACKEND=local` in production loses every upload on the next deploy. `render.yaml` sets `s3`; the app logs a loud warning if it is left on `local` with `ENV=production`. |
| **No SMTP on Render's free tier** | Outbound ports 25/465/587 are blocked, so there is no SMTP code path at all. Set `EMAIL_PROVIDER` to `resend`, `sendgrid`, `mailgun` or `brevo` with `EMAIL_API_KEY`, and make sure `MAIL_FROM` is on a domain **verified** with that provider. |
| **`PUBLIC_FORM_URL` must be the deployed supplier form** | It is the base of every invitation link. Get it wrong and every supplier link 404s — and the buyer finds out when a supplier tells them. |
| **Vercel env vars are baked in at build time** | Vite inlines `import.meta.env.*`, so changing `VITE_API_URL` requires a **redeploy**, not just an env-var edit. |
| **Vercel Hobby forbids commercial use** | Running a business on the free Hobby plan violates Vercel's terms. Upgrade to Pro before commercial use, or host the two static SPAs anywhere that serves files. Neon and Render's free tiers do not carry this restriction. |
| **CORS must list exact origins** | Scheme included, no trailing slash. `*` works but is not appropriate in production, and the app warns when `ENV=production` and `ALLOWED_ORIGINS` contains one. Redeploy after changing it. |
| **The free service sleeps** | Render spins down after 15 idle minutes. Point a free uptime monitor at `/health` every 14 minutes to keep it warm. `/health` returns 200 even when a dependency is unhealthy — the body says `"status": "degraded"` — so a monitor never reports a cold database as an outage. |
| **The in-process scheduler sleeps too** | Set `SCHEDULER_SECRET` and point a free cron (cron-job.org, or a GitHub Actions schedule) at `POST /internal/scheduler/tick` with header `X-Scheduler-Secret`. The endpoint returns **403 while the secret is unset** — an unauthenticated endpoint that sends email is not an acceptable default. Running the tick twice is safe; a second run will not duplicate a pending draft. |

The full API — every endpoint, request body, response shape, status code and guardrail — is
in **[docs/API.md](docs/API.md)**, and the app serves interactive documentation at `/docs`
and `/redoc`.

### Where the AI key goes

Get a free key at <https://console.groq.com/keys> → **Create API Key**. It starts with `gsk_`.
It belongs in **two** of the four places below, and never in the third:

| Where | How | Why |
| --- | --- | --- |
| **This machine** (dev) | `.\set-llm-key.cmd` from the repository root, or set `LLM_API_KEY=` in `backend/.env` | `set-llm-key.cmd` prompts for the key and writes it for you. Never paste a key into a shell command you might save in your history, and never into a chat window. |
| **Render** (production) | Dashboard → your service → **Environment** → `LLM_API_KEY` → paste → **Save** (it redeploys) | The API server is the only thing that calls the model. With the Blueprint, Render asks for it on the creation form. |
| **Vercel** | **Nowhere.** | The two SPAs never talk to Groq. A key in a Vercel environment variable would be inlined into a JavaScript bundle that any visitor can download and read. |
| **Neon** | **Nowhere.** | It is a database. |

Three settings travel together and are already correct in `render.yaml` and `.env.example`:
`LLM_BASE_URL=https://api.groq.com/openai/v1`, `LLM_MODEL=openai/gpt-oss-120b`, and
`LLM_REASONING_EFFORT=low`. **Change the model only if you change all three.** The reasoning
setting is not cosmetic: `gpt-oss-120b` writes a reasoning trace before its JSON answer, and
at the provider's default trace length Groq rejects the call with `HTTP 400
json_validate_failed` — which does not surface as an error, it silently drops quote parsing,
follow-up drafting and comparison summaries onto their deterministic fallbacks.

**The key is genuinely optional.** With `LLM_API_KEY` empty the app works end to end: quote
parsing uses labelled-line extraction, follow-up drafting uses templates that follow the same
writing rules, and the comparison rationale is generated from the scoring run. `/health`
reports `"llm": {"configured": false}`, which is honest degradation rather than a broken
state. To check a key without deploying anything, run `dev.cmd llm` — it sends one real
request and tells you whether a failure is a bad key or a retired model id.

---

## 9. Configuration reference

Every variable, its default and why it exists is documented in **[.env.example](.env.example)**
— that file is the annotated source of truth, and `backend/.env.example` is the same list
tuned for native development. The variables that decide whether a deployment works are
these.

| Variable | Default | Notes |
| --- | --- | --- |
| `ENV` | `development` | `production` hides exception details from 500 responses and enables startup safety warnings. |
| `DATABASE_URL` | local Postgres | The app's connection. **Neon pooled** string in production. |
| `DATABASE_URL_DIRECT` | falls back to `DATABASE_URL` | Alembic only. **Neon direct** string. |
| `SECRET_KEY` | dev placeholder | **Required in production.** Signs the buyer JWTs. Rotating it signs everyone out. |
| `BACKEND_URL` | `http://localhost:8000` | Used to build storage URLs and the OpenRouter referer header. |
| `FRONTEND_URL` | `http://localhost:5173` | |
| `PUBLIC_FORM_URL` | `http://localhost:5174` | **The base of every supplier link.** Wrong value = every invitation 404s. |
| `ALLOWED_ORIGINS` | `*` | Comma-separated. Set explicitly in production. |
| `BASE_CURRENCY` | `SGD` | The currency the comparison falls back to when an RFQ does not name one. Ships as `SGD` in the application defaults, `.env.example` and `render.yaml`. |
| `DEFAULT_GST_RATE` | `9.0` | GST (or the equivalent consumption tax), as a percentage. It becomes the `gst_rate` on a new **SGD** RFQ, and it is applied to a quote that states no tax rate of its own, so every quote in one RFQ is ranked on the same tax basis. 9% is the current Singapore rate. Set `0` if you are not GST-registered, or for a market with no such tax; a non-SGD RFQ starts with no rate set. |
| `DEFAULT_PROCUREMENT_TYPE` | `service` | `service` or `goods`. Selects the required-field contract, the default scoring weights, and the vocabulary the UI and the follow-up emails use. `service` is the default because building maintenance and minor works are what this is for. |
| `FX_RATES_JSON` | built-in dated table | Partial override, e.g. `{"EUR": 0.93}`. Every result carries the rate and its as-of date. |
| `DEFAULT_SCORING_WEIGHTS_JSON` | built-in weights | Overridable per RFQ from the UI. |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | Any OpenAI-compatible endpoint. |
| `LLM_API_KEY` | *(empty)* | **Empty ⇒ deterministic fallbacks everywhere.** The app works with no key. |
| `LLM_MODEL` | `openai/gpt-oss-120b` | Check the provider's current model list; retired ids fail every request. |
| `LLM_REQUESTS_PER_MINUTE` | `30` | Matches Groq's free tier. Lower it, never raise it above what your tier allows. |
| `LLM_REASONING_EFFORT` | `low` | `low` \| `medium` \| `high`, or empty to send nothing. Sent only for models recognised as reasoning models. Leave it at `low`: on `openai/gpt-oss-120b` the provider's default trace length was long enough that Groq rejected the call with HTTP 400 `json_validate_failed`, and every LLM feature quietly fell back to its deterministic path. Set it empty only when your model's endpoint rejects the field. |
| `EMAIL_PROVIDER` | `console` | `console` \| `resend` \| `sendgrid` \| `mailgun` \| `brevo`. `console` logs and sends nothing. |
| `MAIL_FROM` | Resend test sender | Must be on a domain verified with your provider. |
| `STORAGE_BACKEND` | `local` | **Must be `s3` on Render.** |
| `S3_*` | *(empty)* | Endpoint, bucket, region, keys, optional public base URL. |
| `AUTO_SEND_FOLLOWUPS` | `false` | `false` queues every reminder as a draft for approval. **Does not affect awarding** — that always needs a human. |
| `FOLLOWUP_INTERVALS_HOURS` | `72,168` | Chase after 3 days, then after 7. |
| `FOLLOWUP_BEFORE_DEADLINE_HOURS` | `48` | Also remind this close to the deadline, overriding the interval. |
| `SCHEDULER_SECRET` | *(empty)* | Required to enable `POST /internal/scheduler/tick`. |
| `INVITATION_TTL_DAYS` | `30` | Link lifetime, bounded by the RFQ deadline plus a week when one is set. |
| `PUBLIC_RATE_LIMIT_PER_MINUTE` / `_PER_HOUR` | `20` / `60` | Per IP, and per token for the hourly window. |
| `CAPTCHA_PROVIDER` | `none` | `none` \| `turnstile` \| `hcaptcha`. Honeypot and rate limiting are always on. |

---

## 10. Architecture

```
Supplier Quote Autopilot
│
├── frontend/            buyer dashboard SPA   (Vercel project 1)
├── public_form/         supplier form SPA     (Vercel project 2, no login)
│
├── backend/             FastAPI application   (Render)
│   ├── app/
│   │   ├── core/        config · database · security · llm_client · email ·
│   │   │                storage · rate limiting · exceptions
│   │   ├── features/    one slice per domain, each model · schema · service · router
│   │   │                auth · rfq · supplier · invitation · quote · attachment ·
│   │   │                public_form · followup · comparison · dashboard · chat
│   │   ├── ai/          LLM factory, agent registry, completer bridge
│   │   └── main.py
│   ├── alembic/         migrations (env.py reads DATABASE_URL_DIRECT)
│   ├── scripts/         seed_demo.py · list_routes.py
│   └── tests/           424 tests, offline and deterministic
│
├── agents/              PURE domain logic — no web, no database, no I/O
│   ├── quote_parser/    submission -> typed quote (+ completeness)
│   └── followup/        invitation snapshot -> chase / ask / escalate decision
│
├── comparison/          PURE domain logic — landed cost and scoring
│   ├── fx.py · incoterms.py · units.py · cost.py · score.py
│   └── recommend.py · engine.py · exporters.py
│
└── docker-compose.yml · render.yaml · .env.example · NOTICE · LICENSE
```

**The procurement taxonomy lives in one place.** `backend/app/features/rfq/taxonomy.py` owns
the domain vocabulary — the 19 service categories, the 7 goods categories, the 10 service
rate bases and the 8 goods units, the required-field contract for each procurement type, the
13 common Singapore accreditations, and the supplier-facing `describe_tax()` sentence. It
deliberately owns nothing else: the scoring vocabulary (which criteria exist, and their
default weights) belongs to `comparison/schemas.py` because the engine is what scores, and
the supplier-facing field labels belong to `agents/quote_parser/completeness.py` because
those are the words the follow-up emails already use. Both are re-exported from the taxonomy
so callers have one import for everything domain-shaped, `GET /meta/options` serves the
whole set to the buyer dashboard, and the supplier form is handed what it needs on its
invitation preview — which is why adding a service category is a backend-only change.

**The layering rule.** `agents/` and `comparison/` contain **no I/O**: no FastAPI, no
SQLAlchemy, no HTTP, no filesystem, no environment reads. An LLM is injected as a plain
`async` callable, and every path has a deterministic fallback. The consequences are worth
the discipline: the whole comparison engine and the entire follow-up policy are
unit-testable without a database, a server or a network; the test suite runs with no LLM
key configured, so the fallback paths are what is exercised rather than an afterthought;
and a provider outage or an exhausted free tier degrades quality, never availability.

**The follow-up decision order** — inherited in spirit from ForgeFlow, and the ordering is
the point:

```
1. nothing to do          -> skip   (already complete, cancelled, declined, expired)
2. deadline passed        -> skip   (the window is closed)
3. supplier blocked on us -> skip,  escalate to the buyer
4. quote is incomplete    -> ask for exactly the missing fields
5. not submitted          -> remind
6. not due yet            -> skip
```

Step 3 before steps 4–5 is deliberate: a supplier waiting on the buyer for a specification
or a volume cannot be reminded into answering. Chasing them asks for something they have
already said they cannot give — it produces nothing, damages the relationship, and hides
the fact that the buyer is the blocker.

**The award guardrail is structural.** The comparison endpoint *recommends*;
`POST /rfqs/{id}/comparison/approve` is the only path to an award, and the call graph
enforces it — nothing in the scheduler, the parser or the LLM can reach the approval
service. That is a code property, not a prompt instruction.

**Sync SQLAlchemy, deliberately.** The workload is small request-scoped CRUD, `psycopg` 3
speaks to Neon's pooled endpoint natively, and keeping sessions sync lets them be used from
both `def` and `async def` endpoints. The genuinely latency-bound work — LLM, email,
storage — **is** async. See assumption A1 in [INTEGRATION_PLAN.md](INTEGRATION_PLAN.md).

---

## 11. Testing

```bash
cd backend
uv run pytest -q                                  # the whole suite: 424 tests, ~40s
uv run pytest tests/test_acceptance.py -q          # one file
uv run pytest --cov=app --cov-report=term-missing  # coverage
uv run ruff check . ../agents ../comparison        # lint (correctness rules only)
```

The suite is **fast, offline and deterministic**. It runs against a temporary SQLite
database with `EMAIL_PROVIDER=console` and **no LLM key**, so it needs no services, costs
nothing, and exercises the deterministic fallback paths by default. LLM paths are tested by
injecting a fake completer, never a real provider.

| File | Covers |
| --- | --- |
| `test_acceptance.py` | The whole product through the public HTTP API: create an RFQ → three suppliers → three unique links → submit (one complete, one partial, one silent) → statuses → scheduler chases both → approve reminders → compare → CSV export → human award → dashboard roll-up. The RFQ is an explicit **goods** RFQ, so this is the landed-cost path (MOQ, lead time, Incoterms) end to end. |
| `test_postgres_compat.py` | Compiles every representative query and the whole schema against the **PostgreSQL** dialect. Needs no database. |
| `test_public_form.py` | The unauthenticated surface, adversarially: unknown, expired, withdrawn and mismatched links, the honeypot, both rate-limit windows, oversized and disallowed uploads, claiming another supplier's attachment, resubmission amending rather than duplicating, and a supplier's question being escalated rather than chased. |
| `test_regressions.py` | Bugs found during development, with the failure mode recorded in each docstring. |
| `test_comparison_engine.py` | FX, term rebasing, rate-basis conversion, landed/works cost arithmetic, scoring, weighting, ranking, determinism, CSV export. |
| `test_quote_parser.py` | Verbatim-or-null grounding, layer precedence, normalization, and every completeness rule — including "explicitly none is an answer" and "TBD is not". |
| `test_followup_policy.py` | Each branch of the decision order, reminder caps, and the escalate-don't-chase rule. |
| `test_transports.py` | The HTTP email providers, the LLM client's retry/backoff/rate-limit behaviour, and an assertion that **no SMTP code exists anywhere**. |
| `test_services_comparison.py` | The services domain as pure logic: the nine criteria, the per-type weight sets, the response-time curve, accreditation coverage and the **25.0 cap**, GST resolution across all six rate/amount combinations, the callout in the landed cost, the rate bases (including that "per job" and "lump sum" are one basis while "per sq m" is not a metre), complete-quote-first ranking, and the parser's SLA/percentage/accreditation normalizers. |
| `test_services_api.py` | The services path end to end through the public HTTP API: `/meta/options` with no credentials, a services RFQ defaulting to SGD and 9% GST, the supplier preview's service fields and server-owned labels, a complete submission round-tripping the SLA and licences, **both accepted spellings** of the three ambiguous field names, an incomplete quote chased for exactly the two fields it is missing, the missing-licence cap reaching the dashboard through `missing_accreditations`, derived GST disclosed in the cost breakdown, and a manual entry assessed against the services contract. |
| `test_rfq.py` · `test_quote.py` · `test_chat.py` · `test_csv_import.py` | Kept from the base codebase, unmodified. |

**Both procurement paths are covered.** The acceptance, public-form and regression suites pin
`procurement_type: "goods"` explicitly and exercise the landed-cost path (MOQ, lead time,
Incoterms, freight, duties). The two `test_services_*` modules cover the services path, which
is the product's default: the SLA and accreditation criteria, the cap on a missing required
licence, GST derived from a stated rate, the service rate bases, and `GET /meta/options`.

That split is deliberate rather than accidental, and it is what closed the honest gap that
existed before it. The services path was implemented and demoed but untested for a while,
because every end-to-end suite had been written against a goods RFQ. It is now covered from
both ends: the engine arithmetic as pure functions, and the whole submission-to-comparison
flow through HTTP.

**Why SQLite in the tests and PostgreSQL in production matters.** The suite runs on SQLite;
production runs on Neon's PostgreSQL. That gap hides a whole class of defect that only
appears after deployment, and it has already produced two real ones: four boolean flag
columns were declared `Integer` while the application filtered them with `.is_(True)`,
which SQLAlchemy compiles to `col IS true` — PostgreSQL rejects that outright
(`argument of IS must be boolean, not type integer`) while SQLite accepts `IS 1` without
complaint, so a fully green suite concealed a bug that would have taken down the
entire comparison feature. `test_postgres_compat.py` exists so that class of bug fails in
CI instead, and it was verified by reintroducing the bug and watching the guard catch it.

**CI** (`.github/workflows/ci-cd.yml`) runs the backend suite on Python 3.13, `ruff` with
the correctness rules `F` and `E9`, `alembic check` (which fails when the models and the
migration disagree), a `requirements.txt` versus `uv.lock` drift check, an assertion that
no `smtplib` import exists, validation of `docker-compose.yml`, `render.yaml` and both
`vercel.json` files, and lint plus build of both frontends. Deploys are triggered by
optional `RENDER_DEPLOY_HOOK` and `VERCEL_DEPLOY_HOOK` secrets.

Every defect found during the build — including the ones above — is recorded with its cause
in §9 of [INTEGRATION_PLAN.md](INTEGRATION_PLAN.md). How to contribute, including the
conventions that hold in this repository, is in [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 12. FAQ

**Is it free?**
The software is MIT-licensed, and the documented deployment runs entirely on free tiers:
Neon for PostgreSQL, Render for the API, Vercel for the two static frontends, and a free
Groq key (or no key at all) for the AI layer. No credit card is required for any of them.
Two honest caveats: Vercel's Hobby plan forbids commercial use, so a business should
upgrade to Pro or host the static SPAs elsewhere; and the free tiers impose the limits
listed in [§8](#8-deployment-neon--render--vercel) — a service that sleeps when idle, no
persistent disk, and no SMTP.

**Do suppliers need an account?**
No. Each invited supplier gets a unique tokenized link. The token authorises answering one
RFQ and nothing else — it cannot read any part of the buyer's workspace, and it does not
require a password, an email confirmation or an app install. The form is mobile-first
because that is where a contractor will open it.

**Does it need an AI key?**
No, and this is a design rule rather than a fallback of last resort. With `LLM_API_KEY`
empty, quote parsing uses deterministic labelled-line extraction, follow-up drafting uses
deterministic templates that follow the same writing rules, and the comparison rationale is
generated from the scoring run. The product works end to end, including the acceptance
test, with no key at all. A key makes the copy more fluent and the parsing more tolerant of
oddly written notes.

**Which LLM providers work?**
Anything OpenAI-compatible. Groq is the default because it is fast and its free tier is
generous; OpenRouter (with `:free` model suffixes) and Google Gemini's OpenAI-compatible
endpoint are documented alternatives, and switching means changing `LLM_BASE_URL`,
`LLM_MODEL` and `LLM_API_KEY` — nothing else. `dev.cmd llm` sends a real request and tells
you whether a failure is a key problem or a retired model id. Note that Gemini's free tier
is not available in the EU, UK or Switzerland, and Google may use free-tier prompts to
improve its products.

**Can I use it outside Singapore?**
Yes. **SGD and GST are defaults, not requirements.** Set `BASE_CURRENCY` and
`DEFAULT_GST_RATE` (set the rate to `0` if you are not GST-registered, or your market has no
such tax), add or override the FX rates you need in `FX_RATES_JSON`, and use free text for
accreditations if the ones shipped (LEW, PUB, BCA, bizSAFE, ISO, SCDF, WSH) are not the
credentials that matter in your market. The FX table is a documented, dated baseline rather
than a live feed — every comparison reports the rate it used and its as-of date, so a stale
rate is visible rather than silently wrong.

**Does it send email?**
Only if you configure it to. The default `EMAIL_PROVIDER=console` prints each message to
the log and sends nothing, which is why a development run cannot contact a real supplier.
In production it sends over an **HTTPS API** — Resend, SendGrid, Mailgun or Brevo — because
Render's free tier blocks outbound SMTP ports 25, 465 and 587. There is no SMTP code path
in the project at all, and a test plus a CI step enforce that. Follow-up messages are
queued as drafts for your approval unless you set `AUTO_SEND_FOLLOWUPS=true`.

**Can it award a supplier automatically?**
No, by design. `POST /rfqs/{id}/comparison/approve` is the only path to an award and it
requires an authenticated buyer and a written reason. The comparison recommends; the
decision and its justification are recorded against the RFQ. Nothing in the scheduler, the
quote parser or the AI layer can reach the approval service — that is enforced by the call
graph, not by a prompt.

**How many suppliers can I invite?**
There is no limit imposed by the application — the free-tier limits that matter are Render's
512 MB of RAM and Neon's 0.5 GB of storage, not a supplier count. Practically, a quote round
of three to ten suppliers is the designed case, each with its own link and its own status.
Every supplier's AI cost is at most one call per submission, one per follow-up and one per
comparison, and the client spaces requests to stay inside a free tier's rate limit.

**What about file uploads on the free tier?**
Render's free tier has no persistent disk, so anything written locally is lost on the next
deploy. Set `STORAGE_BACKEND=s3` with any S3-compatible store — Cloudflare R2, Backblaze B2,
Neon Object Storage, MinIO or AWS — and configure the `S3_*` variables. In development the
local filesystem is used, and `docker compose --profile s3 up` runs MinIO so the production
path can be exercised locally. Uploads are validated by size, extension and content type,
HTML is always rejected, and attachment links are capability-based on an unguessable key.

**Is the AI allowed to make things up?**
It is instructed not to, and the design assumes it might. Quote extraction is
verbatim-or-null: a value is recorded only if it appears in the supplier's own words, and
each extracted value stores the phrase it came from so you can check it. A non-answer is
never turned into a value. The comparison narrative receives an already-computed scoring
run and is told not to introduce figures of its own; the deterministic rationale is always
available and always present. And a follow-up that volunteers a commercial opinion ("your
quote is competitive") has its output rejected in favour of the template.

**What happens if a quote cannot be compared?**
It is shown, not dropped. A quote in an unknown currency or on an incompatible rate basis
stays in the comparison marked not comparable with the reason, because omitting a supplier
is the failure mode that costs money. Add the currency to `FX_RATES_JSON`, or ask the
supplier to re-quote on the same basis, and it becomes comparable. The same applies to an
incomplete quote: it is scored, listed immediately below the complete ones, and its missing
fields are named.

---

## 13. Roadmap: what is not built yet

An honest list. These are known and deliberate boundaries of the current version, not
oversights. It is an MVP with 424 offline tests, a CI pipeline and a free-tier deployment
that has been walked through end to end — it has not been through a security audit, and it
is a solid small-team tool rather than an enterprise system of record.

- **Multi-user team accounts and roles.** One buyer account owns its suppliers and RFQs.
  There is no organisation, team or role model — no half-built permissions to
  misconfigure, but also no way to share a workspace with a colleague.
- **Multi-line-item RFQs.** One scope per RFQ. A package with five distinct line items is
  currently five things to compare, or one scope you describe in prose.
- **Live FX rates.** The FX table is a documented, dated, environment-overridable baseline.
  A live feed is another dependency, another key and another failure mode, and a feed that
  dies mid-comparison is worse than a slightly stale rate — but a stale rate is still a
  limitation.
- **A Redis-backed rate limiter.** The public form's sliding window is in-process, keyed by
  IP and token. Correct for the single instance the free tier runs; a multi-instance
  deployment would need shared state.
- **Scheduled and recurring works.** No contract schedules, no recurring PPM job
  generation, no annual rate agreements. Every RFQ is a one-off round.
- **Supplier-side accounts.** Suppliers have links, not logins. There is no portal where a
  contractor can see history, manage their own details, or hold their own rate card.
- **Approval workflows beyond the award.** Only the award requires an explicit approval, and
  only one is needed. There is no multi-step sign-off, budget threshold or delegated
  authority model.
- **Catalogue, contract and spend analytics.** No punchout, no price lists, no contract
  register, no spend dashboard. See [§4](#4-why-it-exists-and-how-it-differs) for where
  that leaves this project relative to a commercial suite.
- **The chat assistant is heavier than the rest of the AI layer.** It is inherited from the
  base codebase and still uses LangChain/LangGraph rather than the small shared client used
  by the new features. It works, but it is the one inconsistency.

---

## 14. GitHub topics

Paste these into the repository's **Topics** field (repository page → ⚙ next to *About*),
ordered by importance. They are the strongest signal GitHub search has for a project like
this, and they cost nothing.

```
rfq
request-for-quotation
procurement
facilities-management
building-maintenance
quote-comparison
supplier-management
fastapi
react
postgresql
neon
render
vercel
groq
llm
openai-compatible
sgd
gst
singapore
minor-works
```

Twenty topics, which is GitHub's limit. If you want to trade one out for `electrical`,
`plumbing`, `hvac`, `tailwindcss` or `docker`, drop the last entry — the more specific a
topic is, the fewer people search for it. [docs/SEO.md](docs/SEO.md) explains the reasoning
and includes a suggested repository description.

---

## 15. License

**MIT.** See [LICENSE](LICENSE). Copyright (c) 2026 Supplier Quote Autopilot contributors.
Use it, modify it, sell it — the only condition is that the copyright notice and permission
notice travel with it.

MIT was chosen because it matches the license of the work this project builds on, it is
what most people look for in a repository like this, and it creates no friction for
commercial use by a facilities team or a contractor that wants to run it internally.

Two things worth stating plainly:

- **ForgeFlow is MIT** (Copyright (c) 2026 JayleeBot) and is attributed in
  [NOTICE](NOTICE). ForgeFlow is not vendored into this tree; selected concepts and prompt
  patterns were adapted, and each adapted file carries an attribution header listing it.
  Its license is satisfied by that notice.
- **The base repository this project extends (`rfq-comparison-tool`) shipped no license
  file at all** — no `LICENSE`, `COPYING` or `NOTICE` anywhere in its tree. It has been
  treated throughout as first-party code supplied by the project owner, which is the
  assumption [INTEGRATION_PLAN.md](INTEGRATION_PLAN.md) §1 records. **If you are the
  owner and you did not write that codebase yourself, confirm you hold the rights to
  publish it under MIT before making this repository public.** This is a note-to-self in
  the README, not a legal opinion, and no lawyer has reviewed it.

If you are reusing this project and the provenance question matters to you, read §1 of
[INTEGRATION_PLAN.md](INTEGRATION_PLAN.md) — it sets out exactly what was reused,
adapted and reimplemented, and where each piece came from.

---

## 16. Credits

- **[ForgeFlow](https://github.com/JayleeBot/ForgeFlow)** (MIT, Copyright (c) 2026
  JayleeBot) — the reasoning design this project's pure agent packages adapt: verbatim-or-null
  grounding for extracted commercial values, the missing-field taxonomy, the
  escalate-don't-chase decision ordering, the supplier-facing writing rules, and the
  human-in-the-loop discipline before an irreversible action. No ForgeFlow file was copied
  byte-for-byte; [NOTICE](NOTICE) lists every file containing adapted material.
- **`rfq-comparison-tool`** — the FastAPI + SQLAlchemy + React base this project extends in
  place. Its feature-slice convention, domain exception hierarchy, settings pattern, sync
  SQLAlchemy engine and shared UI kit are reused largely as they were.
- **[INTEGRATION_PLAN.md](INTEGRATION_PLAN.md)** — the full record of what was reused,
  adapted or reimplemented from each source repository, the license position for each, the
  documented assumptions and deviations, and §9's list of the 22 defects found during the
  build with the reason each one existed. If you want to understand why a piece of this
  codebase is shaped the way it is, that is the document to read.

> **Why this document is committed here.** It was written in the build workspace, one
> directory *above* the repository, which is why older commits and the `backend/` source
> notes cite it without a path. It now lives in the repository so the design record travels
> with the code — it is the only place the license position for the source repositories and
> the full defect log are written down. GitHub cannot follow a relative link out of a
> repository root, so the file had to be copied in rather than linked.

Further reading:

| Document | Contents |
| --- | --- |
| [docs/API.md](docs/API.md) | Full API reference: every endpoint, request body, response shape and status code. |
| [docs/SEO.md](docs/SEO.md) | Repository description options, topics, keyword map and announcement drafts. |
| [GITHUB_SETUP.md](GITHUB_SETUP.md) | Pushing to GitHub, secrets, branch protection, and wiring up the free-tier services. |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Running the stack, tests and lint, code conventions, and what a good pull request looks like. |
| [backend/README.md](backend/README.md) | Backend layout, layering rules, data model, email, storage, scheduler, scripts. |
| [frontend/README.md](frontend/README.md) | Buyer dashboard structure, routing and theming. |
| [public_form/README.md](public_form/README.md) | Supplier form and its tokenized URL scheme. |
| [NOTICE](NOTICE) | Third-party attribution, including the ForgeFlow MIT notice. |
| [.env.example](.env.example) | Every environment variable, annotated, with working defaults. |
