# Follow-up slice

The buyer's side of supplier follow-ups. Two jobs:
1. **Approval queue** — the backend drafts reminders automatically (no response,
   incomplete quote, deadline warning) and parks them in `draft`; a buyer reads,
   edits, approves or discards them here.
2. **Communication log** — for one RFQ, the history of what was sent to which
   supplier, when, and why.

## Why nothing is sent without approval

Drafted copy may be AI-written and can be wrong about quantities, deadlines or
specifications. Emailing a supplier is irreversible and costs the buyer
credibility, so the backend never sends a draft on its own: only
`POST /follow-ups/{id}/approve` moves a message towards delivery, and each
decision is stamped with `approved_at` and `decision_reason`.

## Endpoints and exports

- `GET /follow-ups?status=draft` (queue) and `GET /rfqs/{id}/follow-ups?status=`
  (log; omit `status` for every message) are the two reads the UI relies on.
- `GET|PATCH /follow-ups/{id}` reads and edits a draft's `subject` / `body`.
- `POST /follow-ups/{id}/approve` / `.../reject` decide; `POST /follow-ups/manual`
  composes a one-off message.
- `api.js` wraps them with axios and returns `response.data`; `hooks.js` exposes
  `usePendingFollowUps()` and `useRFQFollowUps(rfqId, status)` as
  `{ followups, loading, error, refresh }`.
- `components/FollowUpList.jsx` is the shared, fetch-free log — the parent owns
  the data and passes `onChanged` after a mutation — and
  `pages/PendingFollowUpsPage.jsx` is the queue screen.
