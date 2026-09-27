# Supplier directory slice

Owns the buyer's vendor directory: list suppliers with their performance counters, create/edit one,
delete one, and bulk-import many from a spreadsheet. Import the page from
`@/features/supplier/pages/SupplierListPage`; routing lives outside this slice.

## Layout
- `api.js` — the endpoint wrappers, each returning `response.data`: `getSuppliers`,
  `getSupplierById(id)`, `createSupplier(payload)`, `updateSupplier(id, payload)` (PATCH),
  `deleteSupplier(id)` (204, no body), `importSuppliersCsv(file, { onDuplicate })`,
  `importSuppliersJson(suppliers, { onDuplicate })`.
- `hooks.js` — `useSuppliers()` -> `{ suppliers, loading, error, refresh }`; it toasts on failure and
  keeps the message in `error` so the page can show an inline retry panel. `summariseSuppliers()`
  is a pure roll-up returning `{ total, invited, responded, quotesReceived }`.
- `csv.js` — the header-only download template (`buildTemplateCsv`, `downloadTextFile`) and
  `parsePastedRows(text)` -> `{ suppliers, rows, problems }`.
- `importResult.js` — `mergeRowProblems(result, problems)` folds client-side row problems into the
  API's `SupplierImportResponse` and recomputes counts and message; `emptyImportResult()`.
- `components/SupplierForm.jsx` — the field contract: name and contact_email required,
  `risk_rating` from `RISK_RATING_OPTIONS` defaulting to `low`, inline `errorClass` /
  `<FormField error>` validation, trimmed string values.
- `components/BulkSupplierImport.jsx` — the modal body: duplicate policy radios, CSV upload with a
  template download, paste box, and the result panel (message, four counters, failed-row table).
  Input state only — no requests, no toasts — so it renders from a `result` prop.
- `components/SupplierImportModal.jsx` — the `Modal` wrapper: calls the API, toasts a failed
  *request*, refreshes the directory through `onImported` when rows were created or updated.
- `pages/SupplierListPage.jsx` — header ("Bulk upload", "Add supplier"), search, summary chips and
  table, plus the create/edit `Modal`, the bulk-import `Modal` and the delete `ConfirmModal`.

## Bulk import
Two endpoints, one response shape (`SupplierImportResponse`: `created`, `updated`, `skipped`,
`failed`, `total`, `errors[]`, `imported[]`, `message`).

| Path | Request |
| --- | --- |
| CSV upload | `POST /suppliers/import/csv?on_duplicate=<skip\|update>`, `multipart/form-data`, one part named `file` |
| Pasted rows | `POST /suppliers/import`, `{ suppliers: SupplierCreate[], on_duplicate }` |

- `on_duplicate` defaults to `skip`: re-importing a spreadsheet must not overwrite the notes, risk
  rating or reference code the buyer curated by hand.
- The CSV `Content-Type` is set per request in `api.js`. The shared client defaults to
  `application/json`, and axios serialises a `FormData` body to JSON when the request carries a JSON
  content type — without the override the `file` part never leaves the browser.
- CSV errors are row-independent: the backend imports what parsed and reports the rest. The paste
  path is not — `POST /suppliers/import` validates the whole list in one pass — so `parsePastedRows`
  rejects a row it knows would 422 the batch and `mergeRowProblems` shows it beside the server's own
  failures. Row numbers are spreadsheet rows (header is row 1), surfaced verbatim.
- A CSV with no name or email column is a 400 whose `detail` says which column to rename; the shared
  client flattens it into `error.message`, so it is shown verbatim by `toast.error`.
- The paste parser is the convenience path: a plain tab (then comma) split of the first line as
  header. A value containing the delimiter or quoting does not survive it, which is why the upload
  is the robust path and is described that way in the UI.

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
