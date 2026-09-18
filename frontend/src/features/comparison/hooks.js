import { useCallback, useEffect, useState } from "react";

import { toast } from "sonner";

import { getApprovals, getComparison, runComparison } from "./api";

/**
 * Comparison state for one RFQ.
 *
 * The initial snapshot comes from the parent's `GET /rfqs/{id}/overview` call
 * (so opening the tab costs no request at all). This hook only fetches when the
 * buyer asks for something new, and adopts an updated snapshot from the parent
 * whenever the overview is refreshed after a mutation elsewhere.
 */
export function useComparison(rfqId, initialComparison = null) {
  const [comparison, setComparison] = useState(initialComparison);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setComparison(initialComparison);
  }, [initialComparison]);

  /** Re-run the engine. `weights` are fractions; omit to reuse the RFQ's. */
  const compute = useCallback(
    async ({ weights, useLlm = false } = {}) => {
      if (!rfqId) return null;

      try {
        setBusy(true);
        setError(null);

        const data = await runComparison(rfqId, { weights, use_llm: useLlm });

        setComparison(data);

        return data;
      } catch (err) {
        setError(err.message);
        toast.error(err.message);

        return null;
      } finally {
        setBusy(false);
      }
    },
    [rfqId]
  );

  /** Pull the authoritative current snapshot (no re-scoring unless asked). */
  const reload = useCallback(
    async ({ recompute = false } = {}) => {
      if (!rfqId) return null;

      try {
        setBusy(true);
        setError(null);

        const data = await getComparison(rfqId, { recompute });

        setComparison(data);

        return data;
      } catch (err) {
        setError(err.message);
        toast.error(err.message);

        return null;
      } finally {
        setBusy(false);
      }
    },
    [rfqId]
  );

  return { comparison, busy, error, compute, reload, setComparison };
}

/**
 * The approval audit trail.
 *
 * `enabled` keeps this lazy: the common case (no decision yet) shows nothing
 * extra and issues no request, because the latest decision already rides along
 * on the comparison snapshot as `comparison.approval`.
 */
export function useApprovals(rfqId, { enabled = true } = {}) {
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    if (!rfqId || !enabled) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const data = await getApprovals(rfqId);

      setApprovals(data);
    } catch (err) {
      setError(err.message);
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }, [rfqId, enabled]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { approvals, loading, error, refresh };
}
