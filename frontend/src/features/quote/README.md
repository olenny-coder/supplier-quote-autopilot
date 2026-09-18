# Quote slice

Supplier quotes: how they are read, sorted and shown side by side, and the two
non-supplier ways one can appear (manual entry, bulk import).

## Files

| File | Purpose |
| --- | --- |
| `api.js` | `GET/POST /rfqs/{id}/quotes`, `GET/PUT/DELETE /quotes/{id}`, and the multipart CSV/PDF import. |
| `hooks.js` | `useQuoteTable(quotes)` — the pure client-side view-model (search, column sorting, lowest-landed-cost detection) and `landedCostOf(quote)`. `useQuotes(rfqId)` remains for pages that need quotes without the RFQ overview; the detail page reads them from `GET /rfqs/{id}/overview`. |
| `components/QuoteTable.jsx` | The side-by-side table. Presentational: it renders whatever `useQuoteTable` derives, and scrolls horizontally rather than squashing on phones. |
| `components/QuoteTableToolbar.jsx` | Search box plus the visible/total count. |
| `components/QuoteForm.jsx` | Manual entry / edit, including the landed-cost components (shipping, duties, taxes, discount) that make normalisation exact. |
| `components/FileImport.jsx` | Drag-and-drop CSV/PDF import with a 2 MB client-side guard. |

## Why the table is wide

The buyer's question is "which of these is actually cheapest to land, and what am
I giving up?" — so the quoted figures sit next to the normalised unit price and
the landed cost, followed by the commercial terms (lead time, MOQ, payment terms,
Incoterms, validity, warranty), the score, then the caveats (completeness with
missing-field chips, risk flags, attachments). Anything missing renders as an em
dash rather than a zero, so a gap is visible instead of looking like a bargain.

## Notes

- Money is serialised as a JSON string by the backend (`Decimal`). Every value is
  parsed with `toNumber()` before it is formatted, sorted or multiplied —
  `"1200.00" < "900.00"` is true for strings and would silently mis-sort a table
  of prices.
- The highlight marks the lowest landed cost *after* currency, unit and Incoterms
  normalisation, not the lowest raw unit price.
