# Contributing to Supplier Quote Autopilot

Thanks for considering a contribution. This document is deliberately short and
concrete: it describes the conventions this repository actually follows, so a change
that fits them is reviewable in one pass.

If you are reporting a bug rather than fixing one, please use the
[bug report form](.github/ISSUE_TEMPLATE/bug_report.yml) — the important field is **the
failing command and its real output**. "Comparison gives the wrong answer" cannot be
reproduced; `cd backend && uv run pytest tests/test_comparison_engine.py -q` plus the
traceback can. Feature ideas go through the
[feature request form](.github/ISSUE_TEMPLATE/feature_request.yml).

By contributing you agree that your contribution is licensed under the
[MIT License](LICENSE), the same terms as the rest of the project.

---

## Ways to contribute that are genuinely useful

- **A reproducible bug report.** Especially anything that works on SQLite and fails on
  PostgreSQL — that class of defect is invisible to the test suite's default database.
- **A test that fails for a real reason.** A failing test with a clear docstring is a
  complete contribution on its own; a maintainer can fix the code around it.
- **Documentation corrections.** If a command in the README does not work on your
  machine, that is a bug. Say which command, on which OS, and what it printed.
- **Provider coverage** — another HTTPS email provider, another S3-compatible store, a
  connector you actually use.
- **Translation of the supplier-facing form.** The supplier form is the one surface
  reached by people who did not choose to use this software.

Not useful: reformatting the tree, dependency churn with no behavioural reason, and
prompt-tuning that cannot be demonstrated against the deterministic fallback path.

---

## Getting the stack running

You need one of the two paths below. Both run the same three services: the API on
`:8000`, the buyer dashboard on `:5173`, and the supplier form on `:5174`.

### Windows — one command (SQLite, no accounts, nothing to install but uv and Node)

From a **Command Prompt**, in the repository root:

```cmd
dev.cmd
```

It checks your toolchain, creates `backend\.env` from `backend\.env.dev`, installs
dependencies on first run, seeds the demo workspace, starts all three services in their
own windows, and prints the buyer login plus every supplier's tokenized form link.

| Command | What it does |
| --- | --- |
| `dev.cmd` | Start everything (installs and seeds on the first run) |
| `dev.cmd key` | Paste your LLM API key — prompts, writes it, restarts, verifies |
| `dev.cmd llm` | Check whether the configured LLM key works |
| `dev.cmd open` | Re-open the UI in your browser without restarting anything |
| `dev.cmd reset` | Wipe the database, re-seed the demo, then start |
| `dev.cmd seed` | Load the demo workspace without starting anything |
| `dev.cmd links` | Re-print the links for an already-running instance |
| `dev.cmd stop` | Stop everything, including leftover windows from earlier runs |

No LLM key is required. Email is logged to the console and never sent, so you cannot
accidentally contact a real supplier from a development machine.

### Any platform — Docker Compose (PostgreSQL)

Requires Docker and Docker Compose.

```bash
cp .env.example .env          # then set SECRET_KEY (see the file's comments)
docker compose up --build
```

A `migrate` service runs `alembic upgrade head` once and exits; `backend` waits for it
to succeed, so a fresh clone comes up with a correct schema. Service names, should you
need them directly: `postgres`, `backend`, `frontend`, `public_form`, plus `minio` and
`minio-init` behind the optional `s3` profile.

```bash
docker compose exec backend uv run alembic upgrade head   # apply migrations in the container
docker compose --profile s3 up                   # exercise the S3 storage path
docker compose down -v                           # stop and delete the database volume
```

> The backend image is built with `uv sync --no-dev`, so the test dependencies are not in it.
> `docker compose exec backend uv run pytest -q` works, but uv fetches the dev group first.
> Running the suite on the host (`cd backend && uv run pytest -q`) is the documented path and
> is much faster.

### Running the pieces by hand

```bash
# backend
cd backend
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

The repository keeps three importable top-level packages — `backend/`, `agents/`,
`comparison/` — and `backend/app/__init__.py` puts the repository root on `sys.path`, so
`uv run …` from `backend/` needs no `PYTHONPATH`. Run Python from elsewhere and you must
set it yourself.

```bash
# buyer dashboard                    # supplier form
cd frontend                          cd public_form
npm install                          npm install
echo "VITE_API_URL=http://localhost:8000" > .env
npm run dev                          npm run dev
```

### Demo data

```bash
cd backend
uv run python -m scripts.seed_demo --reset --run-scheduler
```

`seed_demo` drives the real service layer, including the public-form ingestion pipeline,
so the seeded quotes carry genuine normalized costs, completeness assessments and risk
flags rather than values a fixture invented. It prints a working supplier link and the
demo login.

---

## Tests and lint

```bash
cd backend
uv run pytest -q                                   # the whole suite
uv run pytest tests/test_acceptance.py -q           # one file
uv run pytest -q --collect-only                     # what will run
uv run pytest --cov=app --cov-report=term-missing   # coverage
```

```bash
cd backend
uv run ruff check . ../agents ../comparison         # lint (this is the CI command)
```

**Ruff is configured for correctness only: `F` (pyflakes) and `E9` (syntax/runtime
errors).** The stylistic families — `I`, `UP`, `FURB`, `RUF`, `B`, `SIM`, `E501` — are
deliberately off. This codebase uses one-import-per-line isort style and is not run
through a formatter; enabling those rules would demand a repo-wide reformat that has
nothing to do with correctness and would bury real changes in noise. Do not add a
formatter or a style rule set as a drive-by change. The narrow rule set is not a
formality, though: it caught a sweep of unused imports and a test file that had been
written in the wrong encoding.

### The test suite's contract

Every test must be **offline and deterministic**:

- **No network.** No real LLM provider, no real email send, no live FX or storage
  service. `backend/tests/conftest.py` pins `EMAIL_PROVIDER=console` and
  `LLM_API_KEY=""` before `app.core.config` is imported, precisely so a test that forgets
  its fixtures still cannot make a call that costs money or sends mail. LLM paths are
  exercised by injecting a fake completer.
- **No services.** The suite runs against a temporary file-backed SQLite database. It is
  a file rather than `:memory:` because FastAPI runs sync endpoints in a worker thread
  and an in-memory database is not shared across connections.
- **No time or ordering dependence.** Drive the scheduler explicitly via
  `run_scheduler` rather than waiting on a background timer.
- **A regression test names its failure mode** in the docstring. The *reason* a defect
  existed is more useful to the next reader than the fix.

```bash
uv run pytest -q    # must pass with no database, no API key, and no network
```

### The one test that guards production

`backend/tests/test_postgres_compat.py` compiles every representative query and the whole
schema against the **PostgreSQL** dialect. The suite runs on SQLite while production is
PostgreSQL, so without it a whole class of "green locally, 500s in production" bug is
invisible. It once would have caught `IS true` written against an integer column, which
PostgreSQL rejects and SQLite accepts — a defect that would have taken down the entire
comparison feature while the rest of the suite stayed green. It needs no database, so
there is no excuse for not extending it when you add a query.

---

## Code conventions

These are the conventions that actually hold in this repository. They are few, and each
one exists because something went wrong.

**One import per line.**

```python
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
```

Not `from pydantic import BaseModel, ConfigDict, Field`. Consistent with the rest of the
backend, and it keeps import-line diffs readable.

**Feature slices.** The backend is organised by domain, not by layer. Every feature lives
in `backend/app/features/<name>/` with up to four files: `model.py`, `schema.py`,
`service.py`, `router.py`. Routers parse and validate, then delegate — they never touch
the session and never hold business logic. Services own database access and business
rules.

**`agents/` and `comparison/` do no I/O.** No FastAPI, no SQLAlchemy, no HTTP, no
filesystem, no environment reads. An LLM is injected as a plain `async` callable, and
every call site has a deterministic fallback. This is what makes the landed-cost engine
and the whole follow-up policy unit-testable without a database, a server, or a network —
and it is why a provider outage degrades quality instead of availability. If you find
yourself wanting a session or an HTTP client inside those packages, the logic belongs in
a service instead.

**Services raise domain errors, never `HTTPException`.** Use the hierarchy in
`backend/app/core/exceptions.py` (`NotFoundError`, `BadRequestError`, `ConflictError`,
`ForbiddenError`, `InvitationExpiredError`, `ExternalServiceError`, …). A registered
handler translates them to HTTP at the edge, which keeps the domain framework-agnostic.

**Tenancy is enforced in the service, not the router.** Every lookup takes `user_id` and
returns **404** — never 403 — for another tenant's row. The API does not confirm that a
resource it will not show you exists.

**Never invent a value.** Quote parsing is verbatim-or-null: a field is recorded only
when it appears in the supplier's own words, and it cites the phrase it came from. A
confidently wrong landed cost is worse than a missing one. If you extend the parser,
preserve that rule and extend its tests.

**Never chase a blocked supplier, and never re-ask an answered question.** An explicit
"none" is an answer; "TBD" is not. The follow-up decision order in
`agents/followup/policy.py` encodes this and the ordering is the point — a supplier
waiting on the buyer is escalated to the buyer, not reminded.

**Nothing is auto-awarded.** `POST /rfqs/{id}/comparison/approve` is the only path to an
award, and it requires an authenticated buyer and a written reason. Do not add another
one, and do not let a scheduler, a parser or an LLM reach that service.

**Comments explain why.** The codebase is comment-dense on purpose, and the comments that
earn their place explain the failure mode being avoided rather than restating the line.
Match that; do not add narration of the obvious.

**Decimals, not floats, for money.** Money is `Decimal` in the domain and serialised as
a string over the API.

---

## Adding a feature slice

The whole recipe, in order:

1. **Create the slice.** `backend/app/features/<name>/` with:

   ```
   model.py     SQLAlchemy models (inherit the timestamp mixin in app/core/mixins.py)
   schema.py    Pydantic request/response models
   service.py   business rules and database access; raises domain errors
   router.py    HTTP surface; validation and delegation only
   ```

2. **Register the model** in `backend/app/models.py`, so `create_all` and Alembic both
   see it. A model that is never imported is invisible to both, which produces an
   empty migration and a boot-time crash.

3. **Generate the migration:**

   ```bash
   cd backend
   uv run alembic revision --autogenerate -m "add <name>"
   uv run alembic check      # models and migration now agree
   ```

   Review the generated file. Autogenerate run against SQLite has previously written
   SQLite-flavoured `server_default`s (for example `sa.text('0')` for a boolean, which
   PostgreSQL rejects as "default expression is of type integer"). Boolean defaults must
   be real boolean literals.

4. **Register the router** in `backend/app/main.py`, under the right prefix and with the
   right dependency. Buyer-scoped routes take the current-user dependency; anything
   under `/public/*` is authenticated by an invitation token instead.

5. **Add tests.** A slice without a test is not finished — and a bug fix without a test
   that fails first is not finished either.

6. **Update the docs that would otherwise become wrong.** `docs/API.md` for a new
   endpoint, the README for a user-visible behaviour, `.env.example` for a new setting,
   `docs/` for anything an operator has to do.

If the logic is pure — no database, no HTTP — put it in `agents/<name>/` or
`comparison/` instead, with a deterministic fallback, and have the slice's service call
it. That is the preferred shape, not a special case.

---

## What a good pull request looks like

- **One thing.** A fix plus an unrelated refactor is two pull requests, because they can
  only be reviewed or reverted together otherwise.
- **A reason, not a diff.** Say what the failure mode was and who it hurt. That is the
  part a future reader cannot reconstruct from the code.
- **Real output.** Paste the commands you ran and what they printed. "Tested locally" is
  not verifiable; `317 passed` is.
- **A test that fails before the change.** For a bug fix, this is the whole proof.
- **Documentation kept true.** If your change makes a sentence in the README wrong, fix
  the sentence in the same pull request.
- **Notes on what you could not verify.** "I could not test this against PostgreSQL" is
  more useful than silence, and a reviewer will help.

The [pull request template](.github/pull_request_template.md) lists this as a checklist.
CI runs the backend suite, `ruff` (F and E9), `alembic check`, a `requirements.txt`
versus `uv.lock` drift check, a no-SMTP assertion, both frontend builds, and validation of
`docker-compose.yml`, `render.yaml` and both `vercel.json` files. If a check fails and you
believe the check is wrong, say so in the pull request — do not weaken it silently.

---

## Things that will be declined

- A change that makes the AI layer mandatory. Every AI call site must keep a
  deterministic fallback; the product works with no API key at all, and that is a
  feature.
- SMTP. Email is HTTPS-only because Render's free tier blocks ports 25, 465 and 587. A
  test and a CI step assert that `smtplib` never appears in the source.
- Anything that lets a machine award a supplier.
- Silent omission of a supplier from a comparison. A quote that cannot be normalized must
  appear with a reason — dropping it is the failure mode that costs money.
- A dependency added for something the standard library does at this scale.
- A repo-wide reformat, or a lint rule set widened without a specific defect to justify
  it.
- Committing a secret. If you think you have, say so immediately in the pull request
  rather than rewriting history quietly.

---

## Questions

Open a discussion or an issue — there is no separate channel. Questions about running the
stack are welcome; if the README did not answer one, that is a documentation bug worth
reporting.
