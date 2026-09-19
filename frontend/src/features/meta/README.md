# meta — taxonomy, defaults and scoring criteria

One thin slice with no UI. It fetches the vocabulary the rest of the app runs on, so
the browser never owns a list that the backend also owns.

## Why it exists

Service categories, rate bases, accreditations, currencies, scoring criteria and
per-type required fields are all product decisions that change. Baking them into
JavaScript means every change is a frontend release, and — worse — that the buyer
dashboard, the supplier form and the API can disagree about what a valid rate basis
is. `GET /meta/options` is the single answer, and it is unauthenticated because it
carries no buyer data and the supplier form needs the same vocabulary.

## Files

| File | Contents |
| --- | --- |
| `api.js` | `getMetaOptions()` — one request to `/meta/options`. |
| `hooks.js` | `useMetaOptions()` → `{ options, loading, error }`, plus `getCachedMetaOptions()`. A module-level cache with a shared in-flight promise, so a page with several consumers issues **one** request; a failed request is not cached, so the next mount retries. |
| `currencies.js` | `currencyOptions(...codes)` — the base currency first, then a short convenience list. The API publishes its *base* currency, not an ISO-4217 roster, so the suggestion list lives here and the field accepts free text. |

## Consumers

`RFQForm`, `QuoteForm`, `WeightEditor` and the RFQ card/table components. Every one
of them degrades rather than blocking: `shared/components/ui`'s `Select` falls back
to a free-text input when its option list is empty, and `WeightEditor` falls back to
the weight keys on the stored comparison. A buyer can still create an RFQ and still
re-run a comparison with `/meta/options` unavailable.

## Two things worth knowing

**`required_field_labels` is keyed by procurement type.** `moq` is a *minimum order
quantity* for goods and a *minimum callout charge* for services, and `unit` is a
*unit of measure* or a *rate basis*. A flat map has to be wrong for one of them, so
the shape is `labels[procurement_type][field]` and callers must pass the type they
are rendering.

**The vocabulary is the engine's, not this slice's.** The criteria and their default
weights come from `comparison/schemas.py` via `rfq/taxonomy.py`, so a criterion can
never be scored by the engine and left out of the weight editor. If you add one,
add it there.
