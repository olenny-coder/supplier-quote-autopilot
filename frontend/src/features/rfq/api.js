import client from "@/shared/api/client";

/**
 * RFQ feature — requests for quotation, and the supplier invitations that hang
 * off them.
 *
 * Invitations live here rather than in their own slice because they are only
 * ever addressed *through* an RFQ (create them for an RFQ, act on them from the
 * RFQ's Suppliers tab). `GET /rfqs/{id}/overview` is the single call the detail
 * page makes: it returns the RFQ, its invitations, quotes, follow-ups and the
 * current comparison, so the page renders with one loading state.
 *
 * Note: numeric fields (quantities, counters, money) arrive from Python
 * `Decimal`/int as JSON numbers or strings — parse with `Number()` before
 * formatting.
 */

/** Fetch all RFQs, each with its invitation/quote counters. */
export const getRFQs = async () => {
  const response = await client.get("/rfqs");
  return response.data;
};

/** Fetch a single RFQ with its counters. */
export const getRFQById = async (rfqId) => {
  const response = await client.get(`/rfqs/${rfqId}`);
  return response.data;
};

/**
 * Everything the RFQ detail page needs, in one request:
 * `{ rfq, invitations, quotes, followups, comparison, capabilities }`.
 */
export const getRFQOverview = async (rfqId) => {
  const response = await client.get(`/rfqs/${rfqId}/overview`);
  return response.data;
};

/** Create an RFQ, optionally with inline suppliers and their invitations. */
export const createRFQ = async (payload) => {
  const response = await client.post("/rfqs", payload);
  return response.data;
};

/**
 * Update an RFQ. PATCH semantics: only the supplied fields change, so the edit
 * form can send a partial payload without clobbering the rest.
 */
export const updateRFQ = async (rfqId, payload) => {
  const response = await client.patch(`/rfqs/${rfqId}`, payload);
  return response.data;
};

export const deleteRFQ = async (rfqId) => {
  const response = await client.delete(`/rfqs/${rfqId}`);
  return response.data;
};

// ----------------------------------------------------------------- invitations

/** Invitations issued for an RFQ (one per supplier). */
export const getInvitations = async (rfqId) => {
  const response = await client.get(`/rfqs/${rfqId}/invitations`);
  return response.data;
};

/**
 * Invite suppliers to an existing RFQ.
 * `send_now: true` emails the private form links immediately.
 */
export const createInvitations = async (rfqId, { supplier_ids, send_now = true }) => {
  const response = await client.post(`/rfqs/${rfqId}/invitations`, {
    supplier_ids,
    send_now,
  });
  return response.data;
};

/** Re-send the invitation email (same token, so the original link still works). */
export const resendInvitation = async (invitationId) => {
  const response = await client.post(`/invitations/${invitationId}/resend`);
  return response.data;
};

/** Withdraw an invitation. Refused by the API once a quote exists. */
export const cancelInvitation = async (invitationId) => {
  const response = await client.post(`/invitations/${invitationId}/cancel`);
  return response.data;
};

/** Permanently delete an invitation row. */
export const deleteInvitation = async (invitationId) => {
  const response = await client.delete(`/invitations/${invitationId}`);
  return response.data;
};
