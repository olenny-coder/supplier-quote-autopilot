<!--
  Pull request template.

  Deliberately short. The two checklist items that matter most in this repository are
  "tests run offline" and "no secrets committed", because both are cheap to get wrong
  and expensive to discover later.
-->

## What this changes

<!-- One or two sentences. What was wrong, or what is now possible? -->

## Why

<!--
  The reason, not the diff. If this fixes a defect, say what the failure mode was and
  who it hurt — that is the part a future reader cannot reconstruct from the code.
  Link the issue if there is one: Closes #123
-->

## How it was verified

<!--
  Real commands and real output, please. "Tested locally" is not verifiable.
  For example:
      cd backend && uv run pytest -q          → 313 passed
      uv run ruff check . ../agents ../comparison  → All checks passed!
      cd frontend && npm run build            → built in 6.4s
-->

```
paste the commands you ran and their result
```

## Type of change

- [ ] Bug fix (behaviour corrected to match the documentation)
- [ ] Feature (new capability)
- [ ] Refactor (no behaviour change)
- [ ] Documentation only
- [ ] Deployment / infrastructure
- [ ] Dependency update

## Checklist

- [ ] `cd backend && uv run pytest -q` passes, and any new test is **offline and deterministic** (no network, no real LLM provider, no real email send, no clock or ordering dependence).
- [ ] If this changes behaviour, a test covers it — ideally one that fails before the fix.
- [ ] `cd backend && uv run ruff check . ../agents ../comparison` is clean. (Ruff is configured for correctness rules only: `F` and `E9`. Style rules are deliberately off, so do not reformat unrelated code.)
- [ ] No `agents/` or `comparison/` code performs I/O — no HTTP, no database, no filesystem, no environment reads. An LLM is injected as an `async` callable and every path has a deterministic fallback.
- [ ] Services raise domain errors from `app/core/exceptions.py`, not `HTTPException`.
- [ ] If models changed, an Alembic migration is included and `uv run alembic check` is clean.
- [ ] If a dependency changed, `requirements.txt` was regenerated (`uv export --format requirements-txt --no-dev --no-hashes --no-emit-project -o requirements.txt` from `backend/`) and `uv.lock` is committed.
- [ ] No secrets, `.env` files, tokens, or real supplier data are committed.
- [ ] Documentation updated where it would otherwise become wrong — the README, `docs/API.md`, or `.env.example` for a new setting.

## Notes for the reviewer

<!--
  Trade-offs you considered, alternatives you rejected, or anything you are unsure
  about. Saying "I could not verify X against PostgreSQL" is more useful than silence.
-->
