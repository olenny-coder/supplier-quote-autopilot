import { useEffect, useState } from "react";

import { getMetaOptions } from "./api";

/**
 * The taxonomy cache.
 *
 * The options are static for the life of a deployment and nearly every screen
 * wants them: the RFQ form's category / rate-basis / accreditation pickers, the
 * quote form, the weight editor's criteria. Fetching per component would put a
 * dozen identical requests on the wire during the first paint of the RFQ page,
 * so the response is cached in a module-level variable and the in-flight promise
 * is shared, which means concurrent mounts produce exactly one request.
 */
let cachedOptions = null;
let inFlightRequest = null;

/** The cached taxonomy, or `null` before the first successful load. */
export function getCachedMetaOptions() {
  return cachedOptions;
}

/** One request at a time, for every caller. */
function loadMetaOptions() {
  if (cachedOptions) return Promise.resolve(cachedOptions);

  if (!inFlightRequest) {
    inFlightRequest = getMetaOptions()
      .then((options) => {
        cachedOptions = options;
        inFlightRequest = null;

        return options;
      })
      .catch((error) => {
        // Clear the slot so a later mount can retry: a transient network blip
        // must not permanently brick the taxonomy for the whole page session.
        inFlightRequest = null;

        throw error;
      });
  }

  return inFlightRequest;
}

/**
 * `GET /meta/options`, fetched once per page session.
 *
 * Returns `{ options, loading, error }`. `options` is `null` until the request
 * settles; every caller must therefore tolerate a null taxonomy (the pickers
 * degrade rather than blocking the form), and `error` is a string, not a thrown
 * error, so a failed meta call never blanks a page that has other data.
 */
export function useMetaOptions() {
  const [options, setOptions] = useState(cachedOptions);
  const [loading, setLoading] = useState(!cachedOptions);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (cachedOptions) return undefined;

    let active = true;

    loadMetaOptions()
      .then((loaded) => {
        if (!active) return;

        setOptions(loaded);
        setError(null);
      })
      .catch((err) => {
        if (!active) return;

        setError(err?.message || "Could not load the procurement options.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    // A component that unmounts mid-request (a closed modal) must not set state.
    return () => {
      active = false;
    };
  }, []);

  return { options, loading, error };
}
