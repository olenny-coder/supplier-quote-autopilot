# Comparison slice

The scoring engine's front end: the ranked table, the weights that produced it,
the recommendation, and the award decision.

## Files

| File | Purpose |
| --- | --- |
| `api.js` | `GET/POST /rfqs/{id}/comparison`, the history, the CSV export (fetched as a blob so the bearer token is sent), `POST /rfqs/{id}/comparison/approve` and `GET /rfqs/{id}/approvals`. |
| `hooks.js` | `useComparison(rfqId, initialComparison)` — adopts the snapshot that arrives with the RFQ overview and only fetches when the buyer re-runs or reloads. `useApprovals(rfqId, { enabled })` loads the audit trail lazily. |
| `components/ComparisonTable.jsx` | One row per quote, sorted by rank, "Recommended" on the winner. |
| `components/WeightEditor.jsx` | The seven criteria on a 0–100 scale, always showing the normalised percentages, with "Reset to defaults". Re-running POSTs fractions summing to 1.0. |
| `components/RecommendationPanel.jsx` | Headline, summary (labelled AI-generated when an LLM wrote it), rationale, warnings and risks. |
| `components/ApprovalPanel.jsx` | The award form, the guardrail copy, and the signed audit entry once a decision exists. |
| `components/ComparisonTab.jsx` | Tab 3 of the RFQ detail page: toolbar (re-run, export CSV, print), table, recommendation, weights, approval. |

## Two decisions worth knowing

**Unranked quotes are never hidden.** A quote the engine could not rank is still
rendered — below the ranked ones, in a muted style, with its `exclusion_reason`.
Dropping it would leave the buyer unable to tell "excluded because the price is
missing" from "excluded because we forgot them", and the award guardrail only
means something if every candidate is visible.

**Awarding is a human act.** `ApprovalPanel` is the only caller of the approve
endpoint: a quote must be picked, a decision and a mandatory note given, and the
result is a signed entry (who, when, which quote, the note, whether it overrode
the recommendation). An award that ignores the recommendation is recorded as an
override, and a quote that is still missing required fields can only be awarded
with a note that begins with the word `override`.

## Notes

Numeric fields inside `results` and `breakdown` are `Decimal` strings; they are
parsed with `toNumber()` before formatting, comparing or sizing the score bar.
