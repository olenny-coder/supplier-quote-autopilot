import client from "@/shared/api/client";

/**
 * Demo feature — the one public, read-only endpoint the SPA may call anonymously.
 *
 * `GET /demo/workspace` is the whole surface. The backend serves a committed
 * snapshot of a sample tender and exposes **no** other demo verb: every route
 * that would write has no route to arrive at, so read-only is a property of the
 * API's route table rather than a promise this SPA is trusted to keep. That is
 * also why there is no guard logic here — the front end's job is simply not to
 * offer an action, and not to call anything else while a visitor is in the demo.
 *
 * Nothing else in the app may be called from the demo page: not `/meta/options`
 * (the payload carries its own `meta`), not the RFQ overview, not the chat. See
 * `features/demo/pages/DemoPage`.
 */

/**
 * The sample workspace: taxonomy, RFQs, invitations, quotes, follow-up drafts and
 * the scored comparison.
 *
 * `skipAuth` is read by the shared client's request interceptor, so this request
 * carries no `Authorization` header even when a stale token is still sitting in
 * `localStorage` from a previous session on the same browser. A signed-out
 * visitor has no token to begin with; the flag makes the anonymity explicit
 * rather than incidental.
 */
export const getDemoWorkspace = async () => {
  const response = await client.get("/demo/workspace", { skipAuth: true });

  return response.data;
};
