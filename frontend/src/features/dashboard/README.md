# Dashboard slice

The buyer's landing page (`/`): the numbers that describe the whole workspace,
plus the two working lists that tell them what to do next.

## Files

| File | Purpose |
| --- | --- |
| `api.js` | `GET /dashboard/summary` — one call returning every counter and both lists. |
| `hooks.js` | `useDashboardSummary()` → `{ summary, loading, error, refresh }`. Toasts failures *and* exposes `error` so the page can render it with a retry. |
| `pages/DashboardPage.jsx` | Composes the page, and owns the two guardrail banners. |
| `components/DashboardStats.jsx` | The six stat cards, declared as data (open RFQs, awaiting approval, suppliers, quotes received, pending responses, incomplete quotes). |
| `components/ClosingSoonPanel.jsx` | RFQs whose deadline is inside the server's warning window, with hours remaining; overdue rows are red. |
| `components/NeedsAttentionPanel.jsx` | Suppliers to chase (silent, or with an incomplete quote), each deep-linking to `/rfqs/{id}?tab=suppliers&invitation={id}`. |

## Why the banners exist

- `auto_send_followups === false` renders an amber banner: reminders are drafted
  and queued for approval, nothing reaches a supplier without a human. The
  counter on the card links to the approval queue (`/follow-ups`).
- `ai_available === false` renders a subtle info line: reminder copy and
  summaries come from the deterministic templates, the feature is not broken.

## Notes

Everything numeric is parsed with `toNumber()` before formatting — the backend
serialises counters and money as JSON strings.
