# Supplier directory slice

Owns the buyer's vendor directory: list suppliers with their performance counters, create/edit one,
delete one. Import the page from `@/features/supplier/pages/SupplierListPage`; routing lives outside
this slice.

## Layout
- `api.js` — the five endpoint wrappers, each returning `response.data`: `getSuppliers`,
  `getSupplierById(id)`, `createSupplier(payload)`, `updateSupplier(id, payload)` (PATCH),
  `deleteSupplier(id)` (204, no body).
- `hooks.js` — `useSuppliers()` -> `{ suppliers, loading, error, refresh }`; it toasts on failure and
  keeps the message in `error` so the page can show an inline retry panel. `summariseSuppliers()`
  is a pure roll-up returning `{ total, invited, responded, quotesReceived }`.
- `components/SupplierForm.jsx` — the field contract: name and contact_email required,
  `risk_rating` from `RISK_RATING_OPTIONS` defaulting to `low`, inline `errorClass` /
  `<FormField error>` validation, trimmed string values.
- `pages/SupplierListPage.jsx` — header, search, summary chips and table, plus the create/edit
  `Modal` and the delete `ConfirmModal`.

## Table columns
`GET /suppliers` returns `SupplierStats` — supplier fields plus `invitations_total`,
`invitations_responded`, `quotes_total` and `average_response_hours`. Python may serialise those as
JSON strings, so each one is parsed with `toNumber()`/`formatNumber()` before rendering.

- Response rate = `invitations_responded / invitations_total`, whole percent; em dash with no invitations.
- Invitations sent and Quotes received = `formatNumber(counter)`, em dash if null; Avg response =
  `average_response_hours` as `"18 h"`, em dash when null.
- `external_ref` sits muted under the name, `city` under the country, `contact_email` under the
  contact name as well as in its own Email cell; search filters name/contact/email/country
  case-insensitively, client-side.
