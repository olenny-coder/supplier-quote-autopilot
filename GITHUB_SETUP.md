# Publishing this repository on GitHub and wiring up the free-tier deployment

A complete, ordered walkthrough: push the code, confirm nothing secret went with it, turn on
the repository protections, paste the description and topics, add the optional deploy
secrets, create the three free services, and smoke-test the result.

Written for the state this repository is actually in: **it is already a git repository with
commits on `main` and no remote configured.** Nothing needs rewriting, squashing or
re-initialising.

Placeholders you will replace: `OWNER` (your GitHub user or organisation) and `REPO`
(suggested: `supplier-quote-autopilot`). The `git` commands below assume you are in the
repository root — the directory containing `README.md`, `NOTICE`, `backend/`, `frontend/`
and `public_form/`.

---

## 0 · Before anything else: confirm no secret will be pushed

This is the one step worth doing carefully, because a leaked API key in a public repository
is a real cost (someone else's free-tier quota, or your card) and it is not fixed by deleting
the commit — the data is already mirrored.

The repository's `.gitignore` already covers everything that matters. Verify it yourself
rather than trusting the file:

```bash
git check-ignore -v .env backend/.env frontend/.env public_form/.env backend/.env.bak backend/var/
```

Expected output — each path matched by a rule, with the file and line number of the rule:

```
.gitignore:5:.env	.env
.gitignore:8:backend/.env	backend/.env
.gitignore:9:frontend/.env	frontend/.env
public_form/.gitignore:4:.env	public_form/.env
.gitignore:19:*.bak	backend/.env.bak
.gitignore:52:var/	backend/var/
```

Note that `public_form/.env` is ignored by that package's own `.gitignore`, not the root one,
and that `backend/.env.bak` is caught by the broad `*.bak` rule — `dev.cmd key` writes that
backup file with your LLM key in plaintext before editing `.env`, which makes it the easiest
secret in this repository to leak with a careless `git add -A`.

**Files that must never be committed:**

| Path | Why |
| --- | --- |
| `.env` | Root environment file, read by `docker compose`. Contains `SECRET_KEY`, database credentials, `LLM_API_KEY`, `EMAIL_API_KEY`, `S3_*` keys. |
| `backend/.env` | Native-development environment: the same secrets, plus a database URL with a password. |
| `frontend/.env` | `VITE_API_URL`. Not secret, but per-machine — the templates are committed instead. |
| `public_form/.env` | Same as above for the supplier form. |
| `*.env.bak` | `dev.cmd key`'s plaintext backup of the previous `.env`, **including the API key**. |
| `backend/var/` | Local uploads and the scratch SQLite databases (`dev.db`, test databases). May contain real supplier documents if you tested with real ones. |
| `backend/.venv/`, `node_modules/`, `dist/` | Build artefacts. Large, machine-specific, reproducible. |

Then confirm what git is actually going to push:

```bash
git status --short
```

A clean tree, or a short list of files you recognise. If you see any `.env` file, a `.bak`
file, a database, or a directory under `var/`, **stop** and fix it before pushing:

```bash
# If a secret was already staged:
git restore --staged backend/.env

# If a secret is already committed, the file must be removed from tracking, and the key
# itself must be treated as compromised and rotated at the provider:
git rm --cached backend/.env
```

Finally, list every tracked file whose name even looks sensitive. Only the committed
*templates* should appear:

```bash
git ls-files | Select-String -Pattern "\.env|\.pem|\.key|\.db"
```

Expected: `.env.example`, `backend/.env.dev`, `backend/.env.example`,
`frontend/.env.example`, `public_form/.env.example` — and nothing else. If a `.pem`, a `.key`
or a `.db` shows up, investigate before you continue.

---

## 1 · Create the remote and push

There is no remote yet, and `main` already exists with history. So: create the GitHub
repository, add it as `origin`, push. **No history rewrite is needed** — the existing commits
are what you want published.

### 1a. Create an empty repository on GitHub

Either through the web UI — <https://github.com/new> — or with the GitHub CLI:

```bash
gh repo create OWNER/REPO --public --description "Open-source RFQ software for facilities management and building services procurement." --source=. --remote=origin
```

Through the web UI, **do not** initialise it with a README, a `.gitignore` or a license: this
repository already has all three, and an initialised remote creates a divergent first commit
you would then have to merge or force-push.

### 1b. Add the remote and push

SSH:

```bash
git remote add origin git@github.com:OWNER/REPO.git
git branch -M main
git push -u origin main
```

HTTPS (use a personal access token as the password when prompted):

```bash
git remote add origin https://github.com/OWNER/REPO.git
git branch -M main
git push -u origin main
```

`-u` sets the upstream, so every later `git push` and `git pull` works with no arguments.

If you already created the remote with `gh repo create --source=. --remote=origin` in step 1a,
skip the `git remote add` line — the remote exists — and just run the push.

Confirm:

```bash
git remote -v          # origin  git@github.com:OWNER/REPO.git (fetch and push)
git log --oneline -3   # your existing commits, unchanged
```

> **If the push is rejected** with `! [rejected] main -> main (fetch first)`, the remote has a
> commit you do not — almost always because it was initialised with a README. Either merge it
> (`git pull --rebase origin main` then push) or, if you are certain the remote content is
> worthless, delete and recreate the GitHub repository empty. Do **not** reach for
> `--force` on a first push unless you have checked what you would be discarding.

### 1c. About the `.git` directory

The repository root here is a normal git repository. If you are publishing from inside a
larger workspace, make sure you are pushing *this* directory and not its parent — the
`.github/`, `agents/` and `comparison/` directories must be at the top level of the
repository for CI to find them.

---

## 2 · Repository settings: description and topics

These two fields do more for discoverability than anything else on GitHub.

1. Open <https://github.com/OWNER/REPO>.
2. On the right, next to **About**, click the ⚙ gear.
3. **Description** — paste one of the options from [docs/SEO.md](docs/SEO.md) §1. The
   recommended one is:

   ```
   Open-source RFQ software for facilities management and building services procurement: tokenized supplier quote forms with no supplier login, automated follow-up, and landed/works-cost comparison with SGD and GST defaults. FastAPI + React + PostgreSQL. Deploys free on Neon, Render and Vercel.
   ```

   The field is capped at 350 characters, and it is indexed by GitHub search.
4. **Topics** — add, one at a time, in this order (GitHub allows 20):

   ```
   rfq · request-for-quotation · procurement · facilities-management · building-maintenance
   quote-comparison · supplier-management · fastapi · react · postgresql
   neon · render · vercel · groq · llm
   openai-compatible · sgd · gst · singapore · minor-works
   ```

   Rationale for the order, and which ones to drop if you want `docker` or `tailwindcss`
   instead, is in [docs/SEO.md](docs/SEO.md) §2.
5. **Website** — leave empty unless you have a real demo to point at. A link to a Render
   service that is asleep for 15 minutes at a time is worse than no link.
6. **Social preview** — upload an image (1280×640). Without one, every share of this
   repository renders as a grey placeholder box.

---

## 3 · Turn on the repository protections

All of the following are free on a public repository.

### Branch protection on `main`

Current GitHub:

1. **Settings → Rules → Rulesets → New branch ruleset**.
2. Name: `main`. **Enforcement status: Active**. **Target branches**: add `main` (or
   *Default branch*).
3. Enable:
   - **Restrict deletions** — stops an accidental `git push --delete`.
   - **Block force pushes** — the important one. Without it, published history can be
     rewritten, which breaks every clone and every fork.
   - **Require a pull request before merging**, with *Require approvals: 0* if you work
     alone. That still enforces the pull-request path, which is what makes CI run before
     `main` moves.
   - **Require status checks to pass**, and select the CI jobs: `Backend tests`,
     `Buyer dashboard build`, `Supplier form build`, `Compose config is valid`. They appear
     in this list only after the workflow has run at least once, so do this *after* your
     first push (step 6) rather than before.

Classic branch protection (`Settings → Branches → Add branch protection rule`) still works
and exposes the same options if you prefer it.

> **`Require approvals: 0` with "require a pull request"** is the right setting for a solo
> maintainer: it gives you a green CI gate on a pull request without requiring a second
> person.

### Secret scanning and push protection

**Settings → Code security** (older UI: *Security → Code security and analysis*).

- **Secret Protection / Secret scanning** — enable. On a public repository this is free, and
  it alerts you if a provider-recognised credential is ever committed.
- **Push protection** — enable. This is the one that actually prevents a leak: it rejects a
  push containing a recognised credential *before* it lands. Turning it on means a stray
  `gsk_…` in a commit is caught at `git push` rather than an hour later by email.
- **Dependabot alerts** — enable. Free, and it will tell you when one of the Python or npm
  dependencies in this project has a published advisory.
- **Dependabot security updates** — enable. It opens pull requests for those advisories
  automatically. This project's generated `requirements.txt` and `uv.lock` need to stay in
  sync, so review these rather than merging blind.

### Dependabot version updates (optional)

GitHub does not ship a default config for scheduled version bumps. If you want weekly update
pull requests, create `.github/dependabot.yml` with:

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/backend"
    schedule:
      interval: "weekly"
  - package-ecosystem: "npm"
    directory: "/frontend"
    schedule:
      interval: "weekly"
  - package-ecosystem: "npm"
    directory: "/public_form"
    schedule:
      interval: "weekly"
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "monthly"
```

Two cautions specific to this repository:

- A pip bump changes `uv.lock`, and CI fails if `requirements.txt` drifts from it. Regenerate
  with `uv export --format requirements-txt --no-dev --no-hashes --no-emit-project -o requirements.txt`
  from `backend/` in the same pull request.
- Dependabot does not update `uv.lock` for you. Expect to run `uv lock --upgrade-package <name>`
  locally and commit the result.

---

## 4 · Add the deploy secrets (optional)

CI triggers a Render and a Vercel deploy when the work lands on `main`. **Both are optional:**
Render and Vercel each deploy from their own GitHub integration as soon as they are
connected, so a repository with neither secret still deploys. Add them only if you want CI to
be the thing that kicks off a deploy — which is useful when you want the deploy to be
conditional on the tests passing.

1. Get the hook URLs first:
   - **Render:** your service → **Settings → Deploy Hook** → copy the URL.
   - **Vercel:** project → **Settings → Git → Deploy Hooks** → create one for `main` → copy
     the URL.
2. **Settings → Secrets and variables → Actions → New repository secret**, twice:

   ```
   RENDER_DEPLOY_HOOK = https://api.render.com/deploy/srv-…?key=…
   VERCEL_DEPLOY_HOOK = https://api.vercel.com/v1/integrations/deploy/prj_…/…
   ```

3. The deploy job in `.github/workflows/ci-cd.yml` reads both through `env` and skips a step
   whose secret is empty (`env.RENDER_DEPLOY_HOOK != ''`). That is deliberate: referencing the
   `secrets` context directly in a step-level `if` is not reliably permitted by GitHub, and it
   rejects the whole workflow rather than silently skipping the step.

**Never** put any other credential in the workflow file itself. The workflow's `env` block
deliberately pins `LLM_API_KEY: ""`, `LLM_ENABLED: "false"`, `EMAIL_PROVIDER: console` and
`STORAGE_BACKEND: local` so that a test which bypasses its fixtures still cannot make a
network call that costs money or sends mail. Keep it that way.

---

## 5 · Create the three free services

The full walkthrough — every variable, and the gotchas that actually bite — is [§8 of the
README](README.md#8-deployment-neon--render--vercel). This is the condensed order of
operations.

### 5a. Neon (database) — <https://neon.tech>

1. Sign up (no credit card), create a project.
2. Copy **both** connection strings:
   - **Pooled** — the hostname contains `-pooler`. This becomes `DATABASE_URL`.
   - **Direct** — no `-pooler`. This becomes `DATABASE_URL_DIRECT`, used only by Alembic.
3. **Paste them exactly as Neon gives them.** Neon's connection widget includes
   `?sslmode=require`; if your copy somehow does not, add it — Neon refuses a non-SSL
   connection. You do **not** need to touch the scheme: the app rewrites a bare
   `postgresql://` onto `postgresql+psycopg://` for you, because SQLAlchemy would otherwise
   reach for `psycopg2`, which is not installed, and the service would crash at boot with
   `ModuleNotFoundError: No module named 'psycopg2'`.

The two strings exist because Neon's pooler runs PgBouncer in transaction mode; the app is
happy with that, but Alembic's DDL and `alembic_version` bookkeeping are not. Run migrations
through the direct string.

### 5b. Render (API) — <https://render.com>

1. **New → Blueprint**, connect the repository. Render reads `render.yaml` from the root.
2. Fill in every variable marked `sync: false`. These must be right for the service to boot:
   `DATABASE_URL`, `DATABASE_URL_DIRECT`. These must be right for invitation links to work:
   `BACKEND_URL`, `FRONTEND_URL`, `PUBLIC_FORM_URL`, `ALLOWED_ORIGINS`.
3. **Decide about email and attachments now, not later.** `render.yaml` sets
   `EMAIL_PROVIDER=resend` and `STORAGE_BACKEND=s3`, because leaving them off is wrong in
   production — but neither is usable without credentials, and **neither fails at boot**. The
   service starts, `/health` reports `"configured": false` for each, and the first invitation
   email or file upload is what breaks:

   | If you have… | Set |
   | --- | --- |
   | A free [Resend](https://resend.com) key (3,000/month) and a verified sending domain | `EMAIL_API_KEY`, `MAIL_FROM` |
   | Nothing yet | `EMAIL_PROVIDER=console` — messages are logged instead of sent, and you copy each supplier's link from the dashboard's suppliers tab |
   | A [Cloudflare R2](https://developers.cloudflare.com/r2/) bucket (free) | `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_REGION=auto`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` |
   | Nothing yet | `STORAGE_BACKEND=local` — uploads work but do not survive a redeploy, and the app logs a warning saying so |

4. `LLM_API_KEY` is **optional**; step 5f says where it goes.
5. `SECRET_KEY` and `SCHEDULER_SECRET` are generated for you — read them from the dashboard
   afterwards. You need `SCHEDULER_SECRET` for the external cron in step 5e.
6. Deploy, then run the migrations from your machine (`$env:` is PowerShell; on macOS or Linux
   use `DATABASE_URL_DIRECT="…" uv run alembic upgrade head`):

   ```powershell
   cd backend
   $env:DATABASE_URL_DIRECT = "postgresql://…@ep-xxx.REGION.aws.neon.tech/DBNAME?sslmode=require"
   .\.venv\Scripts\python.exe -m alembic upgrade head   # or: uv run alembic upgrade head
   .\.venv\Scripts\python.exe -m alembic current        # -> f1de0d1828be (head)
   ```

   Setting only `DATABASE_URL_DIRECT` is enough: `alembic/env.py` reads it in preference to
   `DATABASE_URL`. A first boot also works with no manual step, because the app calls
   `Base.metadata.create_all` — but that only *adds* missing tables and never alters or drops,
   so it is a convenience rather than the source of truth.

The blueprint provisions **one** web service and nothing else, on purpose: a Render Cron Job
or Background Worker would be a second billable service and would break the 750 free instance
hours. The follow-up scheduler therefore runs inside the web process, with
`POST /internal/scheduler/tick` available for an external cron.

### 5c. Vercel (both frontends) — <https://vercel.com>

Two separate projects, because suppliers reach a different origin from buyers:

| Project | Root Directory | Environment variable |
| --- | --- | --- |
| Buyer dashboard | `frontend` | `VITE_API_URL` = your Render URL |
| Supplier form | `public_form` | `VITE_API_URL` = your Render URL |

Each app's `vercel.json` handles SPA rewrites so a deep link does not 404 on refresh.
**Vite bakes `VITE_API_URL` into the bundle at build time**, so changing it requires a
redeploy — an env-var edit alone does nothing. ⚠️ Vercel's **Hobby plan forbids commercial
use**; upgrade to Pro before using this for a business, or host the two static SPAs anywhere
that serves files.

### 5d. Point everything at everything

Back on Render, set and redeploy:

```env
BACKEND_URL=https://your-api.onrender.com
FRONTEND_URL=https://your-dashboard.vercel.app
PUBLIC_FORM_URL=https://your-supplier-form.vercel.app
ALLOWED_ORIGINS=https://your-dashboard.vercel.app,https://your-supplier-form.vercel.app
```

`PUBLIC_FORM_URL` is the base of every invitation link — get it wrong and every supplier link
404s, and you find out when a supplier tells you. `ALLOWED_ORIGINS` must list exact origins:
scheme included, no trailing slash, comma-separated.

### 5e. Keep the free tier awake and drive the scheduler

1. **Keep the API warm.** Point a free uptime monitor (UptimeRobot, cron-job.org,
   BetterStack) at `https://YOUR-API.onrender.com/health` every **14 minutes**. Render spins a
   free service down after 15 idle minutes. `/health` returns 200 even when a dependency is
   unhealthy — the body says `"status": "degraded"` — so a cold database is never reported as
   an outage.
2. **Drive the scheduler from outside.** Point a free cron at:

   ```
   POST https://YOUR-API.onrender.com/internal/scheduler/tick
   Header: X-Scheduler-Secret: <the SCHEDULER_SECRET from Render>
   ```

   Every 15 minutes is right. The endpoint returns **403 while `SCHEDULER_SECRET` is unset** —
   an unauthenticated endpoint that sends email is not an acceptable default. Running the tick
   twice in quick succession is safe: a second run will not create a duplicate draft for a
   supplier who already has one pending.

### 5f. The AI key (Groq) — optional, and one place only

The product is designed to run without an AI key: parsing, follow-up drafting and the
comparison rationale all have deterministic implementations, and `/health` reports
`"llm": {"configured": false}` rather than pretending otherwise. A key makes the copy more
fluent and the parsing more tolerant of loosely written notes.

1. **Get one** at <https://console.groq.com/keys> → *Create API Key*. It starts with `gsk_`.
2. **Put it in Render only** — Dashboard → your service → **Environment** → `LLM_API_KEY` →
   Save. Render asks for it on the Blueprint creation form too.
3. **Do not put it in Vercel.** The two SPAs never call the model, and Vite would inline it
   into a JavaScript bundle that any visitor can download and read. It does not belong in Neon
   either.
4. Locally, `.\set-llm-key.cmd` from the repository root prompts for it and writes
   `backend/.env`. `dev.cmd llm` then sends one real request to confirm the key and the model
   id both work.
5. `LLM_BASE_URL`, `LLM_MODEL=openai/gpt-oss-120b` and `LLM_REASONING_EFFORT=low` are already
   set correctly. **Change the model only if you change all three.** `openai/gpt-oss-120b` is a
   reasoning model: at the provider's default trace length Groq answers `HTTP 400
   json_validate_failed` and every AI feature silently reverts to its fallback, which looks
   like the key not working.

---

## 6 · Watch the first CI run

The workflow is `.github/workflows/ci-cd.yml` and it runs on every push to `main` and every
pull request. Its jobs:

| Job | What it proves |
| --- | --- |
| `Backend tests` | `ruff` (correctness rules `F` and `E9`), the full pytest suite on Python 3.13, `alembic check` (models versus migration), the **seed script** end to end with `--check`, `requirements.txt` versus `uv.lock` with no drift, and an assertion that no `smtplib` import exists anywhere. |
| `Buyer dashboard build` | `npm ci`, lint, and a production build of `frontend/`. |
| `Supplier form build` | The same for `public_form/`. |
| `Compose config is valid` | `docker compose config` parses `.env.example`, `render.yaml` is a valid free-plan web service blueprint, and both `vercel.json` files have SPA rewrites. |
| `Trigger deploys` | POSTs the two deploy hooks, if and only if those secrets exist. |

If it fails on the first run, the usual causes are a Node or Python version that differs from
CI (Node 22, Python 3.13) or a `requirements.txt` that was edited without regenerating it from
`uv.lock`.

Once the first run is green, go back to **Settings → Rules → Rulesets** and add those job
names as required status checks on `main`.

---

## 7 · Post-push smoke checklist

Ten minutes, in order. Each line is something that has genuinely broken in a deployment like
this one.

- [ ] `git status` is clean, and `git ls-files` shows no `.env`, no `.bak`, no `.db`.
- [ ] The repository page shows **MIT** as the license, and the README renders — headings,
      tables, and the ASCII architecture diagram.
- [ ] The description and 20 topics are saved and visible in the **About** panel.
- [ ] CI is green on `main`.
- [ ] The API answers: `curl -s https://YOUR-API.onrender.com/health` returns 200 with
      `"status": "ok"` and the `database`, `storage`, `llm`, `email` and `scheduler` blocks in
      the body.
- [ ] Register a buyer account in the deployed dashboard and sign in.
- [ ] Create an RFQ with three suppliers, and confirm **three distinct** tokenized links.
- [ ] Open a supplier link **on a phone**, submit a quote, and confirm the confirmation page
      shows a reference number (`SQ-<rfq number>-<invitation id>`).
- [ ] Back in the dashboard: the quote appears, its status is `Submitted` (or `Incomplete` if
      you deliberately left a required field blank), and the comparison renders.
- [ ] Export the comparison as CSV, then as PDF.
- [ ] Award a supplier through `POST /rfqs/{id}/comparison/approve` **with a written reason**,
      and confirm the award is refused without one.
- [ ] Trigger the cron path once by hand and read the response:
      `curl -X POST https://YOUR-API.onrender.com/internal/scheduler/tick -H "X-Scheduler-Secret: …"`
      — it should report what it scanned and drafted, and a repeat call should not duplicate a
      draft.
- [ ] Confirm email actually sends, if `EMAIL_PROVIDER` is set to a real provider — check
      `MAIL_FROM` is on a **verified** domain, or the provider will reject every send.
- [ ] Upload an attachment in development with `STORAGE_BACKEND=local`, then confirm the same
      flow in production writes to your S3 bucket rather than the ephemeral disk.
- [ ] Rotate anything you pasted anywhere by accident, immediately, and say so in the
      repository rather than quietly rewriting history.

When all of that is true, the repository is published and the deployment is real. The
description, topics and first honest announcement ([docs/SEO.md](docs/SEO.md) §4) are what
make it findable.
