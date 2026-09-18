import { useCallback, useEffect, useState } from "react";

import { toast } from "sonner";

import { getSummary } from "./api";

/**
 * Load the dashboard summary.
 *
 * Exposes `error` as well as toasting it: the page renders the message inline
 * with a retry, so a failed load is never a blank screen.
 */
export function useDashboardSummary() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const data = await getSummary();

      setSummary(data);
    } catch (err) {
      setError(err.message);
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { summary, loading, error, refresh };
}
