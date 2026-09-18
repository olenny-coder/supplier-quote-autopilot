import client from "@/shared/api/client";

/**
 * Follow-up API.
 *
 * A follow-up is one message the buyer's workspace wants to send to a supplier.
 * The slice serves two related jobs:
 *
 *  1. **The approval queue** — `getPendingFollowUps()` lists every draft across
 *     the workspace. The backend drafts these automatically (no response,
 *     incomplete quote, deadline warning) but deliberately leaves them in
 *     `draft` status: nothing reaches a supplier until a buyer approves it.
 *  2. **The communication log** — `getRFQFollowUps(rfqId)` lists every message
 *     belonging to one RFQ, whatever its status, so the RFQ detail page can
 *     show what was actually sent, when, and why.
 *
 * Errors surface as plain `Error(message)` from the shared axios interceptor.
 */

/**
 * Drop empty query params so the backend keeps its own defaults (e.g. an
 * omitted `status` means "every status", which is what the log wants).
 */
function compact(params) {
  return Object.entries(params).reduce((accumulator, [key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      accumulator[key] = value;
    }

    return accumulator;
  }, {});
}

/**
 * Every follow-up for one RFQ. Omit `status` for the full communication log.
 */
export const getRFQFollowUps = async (rfqId, status) => {
  const response = await client.get(`/rfqs/${rfqId}/follow-ups`, {
    params: compact({ status }),
  });

  return response.data;
};

/**
 * The workspace-wide approval queue. Drafts only by default.
 */
export const getPendingFollowUps = async (status = "draft") => {
  const response = await client.get("/follow-ups", {
    params: compact({ status }),
  });

  return response.data;
};

/**
 * Fetch a single follow-up by id.
 */
export const getFollowUpById = async (followupId) => {
  const response = await client.get(`/follow-ups/${followupId}`);

  return response.data;
};

/**
 * Edit a draft's copy before it goes out.
 */
export const updateFollowUp = async (followupId, payload) => {
  const response = await client.patch(`/follow-ups/${followupId}`, payload);

  return response.data;
};

/**
 * Approve a draft and queue it for delivery. Returns `{ followup, message }` —
 * the `message` is the human-readable confirmation shown as a toast.
 */
export const approveFollowUp = async (followupId, payload = {}) => {
  const response = await client.post(`/follow-ups/${followupId}/approve`, payload);

  return response.data;
};

/**
 * Discard a draft so it is never sent. An optional reason is kept on the
 * record as `decision_reason`.
 */
export const rejectFollowUp = async (followupId, reason) => {
  const response = await client.post(
    `/follow-ups/${followupId}/reject`,
    compact({ reason })
  );

  return response.data;
};

/**
 * Compose a one-off message by hand for one invitation. `mode` is
 * `"reminder" | "incomplete" | "custom"`; `send_now` skips the approval queue.
 */
export const createManualFollowUp = async (payload) => {
  const response = await client.post("/follow-ups/manual", payload);

  return response.data;
};
