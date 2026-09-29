# Audit slice

The buyer's view of the workspace audit log: everything that has happened, newest
first, and a CSV of the same list for filing.

## What it is for

Reconstructing a tender without reading six screens. "When did the RFQ go out,
when did each supplier actually answer, who did we chase and how often, what did
the engine recommend, and who approved the award and why?" is one list here, and
one download. The CSV exists because the second half of that question is usually
asked by somebody who was not in the tool — a manager, an auditor, a colleague
covering the decision.

## Read-only, and why that is structural

The API exposes exactly two endpoints, both `GET`:

- `GET /audit` — a page of entries, plus the action and RFQ options the filter
  controls render.
- `GET /audit/export.csv` — the whole filtered log as CSV.

There is no create, update or delete call anywhere in `api.js`, and the backend
has no such route: entries are written by the services at the moment an action
happens (see `backend/app/features/audit/`), and a SQLAlchemy listener raises if
anything ever tries to update one. That is asserted by tests in
`backend/tests/test_audit_log.py`, including one that reads the published OpenAPI
schema and fails if any verb other than `GET` appears under `/audit`.

So this slice has no mutations to offer, and a future contribution that adds one
should be treated as a bug in the audit trail rather than a feature of this page.

## Files

- `api.js` — `getAuditLog(filters)` and `downloadAuditCsv(filters)`. One filter
  object is shared by both so the page and the file can never disagree about what
  is being shown; the download goes through the authenticated client as a blob
  (a plain `<a href>` would 401) and uses the server's `Content-Disposition`
  filename.
- `hooks.js` — `useAuditLog(filters, pageSize)` returns
  `{ entries, total, availableActions, availableRfqs, loading, loadingMore, error,
  hasMore, loadMore, refresh }`. The filter object is compared by value, because
  the page rebuilds it on every render and a naive dependency would refetch the
  log on every keystroke elsewhere on the screen.
- `pages/AuditLogPage.jsx` — the screen: four filters, the table, "load more", and
  the download button.

## Design choices worth knowing

- **Four filters, no search box.** Action, who acted, what it was about, and which
  RFQ cover the questions actually asked. A free-text search was left out on
  purpose: the log is short enough to read, and a search that silently misses a
  row is worse than no search in a screen whose whole job is completeness.
- **"Load more" rather than numbered pages.** The useful question is "what happened
  recently", and the server returns the total, so the button can say how many rows
  are left instead of guessing.
- **Detail is collapsed.** Most entries carry one or two extra facts; a table of
  expanded JSON is unreadable, so each row offers a toggle.
- **The actor is shown as a person, not a code.** "You", the supplier's company, or
  "Scheduler" — with the recorded label underneath, because for a supplier action
  the two differ when a subcontractor answers on someone else's link.
