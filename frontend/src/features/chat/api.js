import client from "@/shared/api/client";

/**
 * Ask the site-wide procurement assistant. `history` is the prior conversation
 * (oldest first, excluding the current question) so the agent keeps context
 * across follow-up questions.
 *
 * Returns `{ answer, pending_email }` — `pending_email` is a drafted supplier
 * email ({ to_email, to_name, subject, body }) awaiting the buyer's confirmation,
 * or null for a plain answer.
 */
export const sendAssistantMessage = async (question, history = []) => {
  const response = await client.post("/chat", { question, history });
  return response.data;
};

/**
 * Send a supplier email the buyer reviewed and confirmed in the chat.
 * `draft` is { to_email, to_name, subject, body }. Returns { status, message }.
 */
export const sendSupplierEmail = async (draft) => {
  const response = await client.post("/chat/email/send", draft);
  return response.data;
};
