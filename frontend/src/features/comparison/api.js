import client from "@/shared/api/client";

/**
 * Comparison feature — scoring, recommendation and award approval.
 *
 * Reading the comparison is part of the RFQ overview payload, so the detail page
 * only calls out to here when the buyer asks for something new: re-running the
 * engine with different weights, exporting, or recording a decision.
 *
 * Every numeric field inside the response (and inside each quote's `breakdown`)
 * arrives from Python `Decimal` as a JSON *string* — `"1200.0000"`. Callers must
 * run those through `Number()` / `toNumber()` before comparing or formatting
 * them, or the sort order and the printed money will be wrong.
 */

/** Current comparison snapshot. `recompute` re-runs the engine server-side. */
export const getComparison = async (rfqId, { recompute = false, useLlm = false } = {}) => {
  const response = await client.get(`/rfqs/${rfqId}/comparison`, {
    params: { recompute, use_llm: useLlm },
  });

  return response.data;
};

/**
 * Score the quotes again — optionally with ad-hoc weights — and store the new
 * snapshot. The previous ones stay in the history, because a recommendation is
 * only explainable alongside the weights that produced it.
 */
export const runComparison = async (rfqId, { weights, use_llm = false } = {}) => {
  const response = await client.post(`/rfqs/${rfqId}/comparison`, {
    weights,
    use_llm,
  });

  return response.data;
};

/** Past scoring runs for an RFQ. */
export const getComparisonHistory = async (rfqId) => {
  const response = await client.get(`/rfqs/${rfqId}/comparison/history`);
  return response.data;
};

/**
 * Download the comparison as CSV.
 *
 * The endpoint needs the bearer token, so a plain `<a href>` would fail — the
 * file is fetched through the authenticated axios client as a blob and handed
 * to the browser via a synthetic link.
 */
export const downloadComparisonCsv = async (rfqId, { filename } = {}) => {
  const response = await client.get(`/rfqs/${rfqId}/comparison/export.csv`, {
    responseType: "blob",
  });

  const objectUrl = window.URL.createObjectURL(response.data);
  const link = document.createElement("a");

  link.href = objectUrl;
  link.download =
    filename ||
    `rfq-${rfqId}-comparison-${new Date().toISOString().slice(0, 10)}.csv`;

  document.body.appendChild(link);
  link.click();
  link.remove();

  window.URL.revokeObjectURL(objectUrl);
};

/**
 * Record the award decision. This is the only endpoint that can award a
 * supplier, and it always requires a human note.
 */
export const approveComparison = async (rfqId, { quote_id, decision, note }) => {
  const response = await client.post(`/rfqs/${rfqId}/comparison/approve`, {
    quote_id,
    decision,
    note,
  });

  return response.data;
};

/** Every decision recorded for an RFQ, oldest first. */
export const getApprovals = async (rfqId) => {
  const response = await client.get(`/rfqs/${rfqId}/approvals`);
  return response.data;
};
