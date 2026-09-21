# Demo slice

The public, read-only tour of a complete sample tender: `/demo`, for a visitor with
no account.

## Files

| File | Purpose |
| --- | --- |
| `api.js` | `GET /demo/workspace` — the only endpoint an anonymous visitor may reach. Sent with `skipAuth`, so no `Authorization` header is attached even when a stale token is still in `localStorage`. |
| `hooks.js` | `useDemoWorkspace({ initial })` — one request, `loading`/`error` state, `toast.error` on failure. `initial` is the SSR render seam; the route never passes it. |
| `components/DemoBanner.jsx` | The sticky "read-only, nothing is saved, no email is sent" bar with the sign-up link. |
| `components/DemoSection.jsx` | A numbered step of the tour: badge, title, one line of explanation. |
| `components/DemoSummaryStrip.jsx` | The RFQ: item, category, rate basis, quantity, required SLA, required accreditations, and the required-field contract. |
| `components/DemoFollowUpList.jsx` | The drafts, read-only, with `requested_labels` as chips — the "it chases only what is missing" story. |
| `components/DemoInvitationList.jsx` | A small read-only table of who was invited, their status and their sent/opened counts. Not `InvitationsTab`, which owns its own requests and resend controls. |
| `pages/DemoPage.jsx` | Composition: top bar, banner, hero (buyer label, the payload's `disclaimer`, the sign-up CTA), the five steps, the closing CTA, footer. |

## Three decisions worth knowing

**One request, or none.** The payload carries the `/meta/options` taxonomy, so
`ComparisonTable` is handed it through its `meta` prop and never fetches it. That
prop is passed as `workspace?.meta || NO_TAXONOMY` — an empty object rather than
`undefined`, because a falsy `meta` is what tells `ComparisonTable` to fetch, and a
public page must not turn a visitor into a request. `NO_TAXONOMY` makes the table
degrade to raw criterion keys instead.

**Nothing looks clickable that is not.** `QuoteTable` is rendered with its
`readOnly` prop, which removes the Edit/Delete column and states the reason in a
footer note. A disabled button was rejected: it still invites a click, and a demo
whose buttons do nothing reads as a broken product. The handlers are passed anyway,
so that if a future change ever renders the controls again, clicking one explains
itself rather than failing silently.

**The demo shows what the product produces.** The components are the real ones —
`ComparisonTable`, `QuoteTable` — fed the payload the authenticated API would
return. Where the payload is thinner than a component's contract, the demo is thin
in the same way rather than papering over it. See the note below.

## Notes

`ComparisonResponse` (`backend/app/features/comparison/schema.py`) has no
`required_accreditations` or `procurement_type` field, but `ComparisonTable` reads
both: `required_accreditations` to render "N of M required — cannot lawfully
proceed" and the missing-licence chips, `procurement_type` to choose service or
goods columns. With the shipped payload the accreditation column therefore reads
"None required" **on the demo page and on the authenticated RFQ page alike**, and
the capped quote's shortfall is carried by its risk-flag chips instead. Fixing it
is a backend change (add the two fields to `ComparisonResponse`, or set them in
`ComparisonService.to_response`); the frontend-only alternative is to pass the
RFQ's list in from `ComparisonTab`/`RFQDetailsPage` the way `QuotesTab` already
does for `QuoteTable`.

A signed-out visitor triggers exactly one request on this page. A visitor with a
token still in storage also triggers the app-wide `GET /auth/me` session check that
`AuthProvider` performs on every route, `/login` and `/register` included — that is
shared boot behaviour, not something the demo adds.
