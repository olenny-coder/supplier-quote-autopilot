import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { getRFQOverview, getRFQs } from "./api";

/**
 * Load the list of RFQs. Encapsulates the fetch + loading + error-toast
 * pattern so pages don't re-implement it.
 */
export function useRFQs() {
  const [rfqs, setRfqs] = useState([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getRFQs();
      setRfqs(data);
    } catch (error) {
      toast.error(error.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { rfqs, loading, refresh };
}

/**
 * Load the whole RFQ detail payload in one request.
 *
 * `setOverview` is exposed so callers that receive fresh data from a mutation
 * (e.g. the comparison endpoint returning a new snapshot) can patch the page
 * without a second round trip, and `refresh` pulls the authoritative version.
 */
export function useRFQOverview(rfqId) {
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    if (!rfqId) return;

    try {
      setLoading(true);
      setError(null);

      const data = await getRFQOverview(rfqId);

      setOverview(data);
    } catch (err) {
      setError(err.message);
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }, [rfqId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { overview, loading, error, refresh, setOverview };
}
