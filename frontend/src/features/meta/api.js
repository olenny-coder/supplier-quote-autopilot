import client from "@/shared/api/client";

/**
 * Meta feature — the API's own vocabulary.
 *
 * `GET /meta/options` is unauthenticated and returns everything the dashboard
 * would otherwise have to guess: the service and goods categories, the rate
 * bases, the accreditation list, the required-field contract per procurement
 * type, the nine scoring criteria with their buyer-facing descriptions, and the
 * per-type default weights.
 *
 * Nothing about that taxonomy is repeated in the SPA. Adding a service category,
 * changing which fields make a quote "complete", or re-weighting a criterion is
 * a backend-only change, and the buyer dashboard cannot drift away from the
 * public supplier form.
 */

/** Taxonomy, defaults and scoring criteria. Cached by `useMetaOptions`. */
export const getMetaOptions = async () => {
  const response = await client.get("/meta/options");

  return response.data;
};
