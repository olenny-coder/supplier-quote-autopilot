import { useCallback, useEffect, useRef, useState } from "react";

import { toast } from "sonner";

import { getPendingFollowUps, getRFQFollowUps } from "./api";

/**
 * Follow-up data hooks.
 *
 * Every hook follows the same shape used across the app: it owns `loading`,
 * exposes the failure as a string so the page can render a panel instead of a
 * blank screen, and *also* toasts the failure so the buyer is never left
 * guessing. A `mountedRef` guards every `setState` so a slow response that
 * lands after navigation cannot update an unmounted component.
 */

function useMountedRef() {
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
    };
  }, []);

  return mountedRef;
}

/**
 * The workspace-wide approval queue — drafts waiting for a buyer's decision.
 *
 * @param {string} status  delivery status to queue on; drafts by default
 */
export function usePendingFollowUps(status = "draft") {
  const [followups, setFollowups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const mountedRef = useMountedRef();

  const refresh = useCallback(async () => {
    if (!mountedRef.current) return;

    setLoading(true);
    setError(null);

    try {
      const data = await getPendingFollowUps(status);

      if (!mountedRef.current) return;

      setFollowups(Array.isArray(data) ? data : []);
    } catch (failure) {
      if (!mountedRef.current) return;

      setError(failure.message);
      toast.error(failure.message);
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [mountedRef, status]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { followups, loading, error, refresh };
}

/**
 * Every follow-up for one RFQ — the communication log. Omit `status` to see
 * sent, failed and discarded messages alongside the drafts.
 *
 * @param {string|number} rfqId  the RFQ to load; falsy skips the request
 * @param {string} [status]      optional status filter
 */
export function useRFQFollowUps(rfqId, status) {
  const [followups, setFollowups] = useState([]);
  const [loading, setLoading] = useState(Boolean(rfqId));
  const [error, setError] = useState(null);

  const mountedRef = useMountedRef();

  const refresh = useCallback(async () => {
    if (!mountedRef.current) return;

    if (!rfqId) {
      setFollowups([]);
      setError(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await getRFQFollowUps(rfqId, status);

      if (!mountedRef.current) return;

      setFollowups(Array.isArray(data) ? data : []);
    } catch (failure) {
      if (!mountedRef.current) return;

      setError(failure.message);
      toast.error(failure.message);
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [mountedRef, rfqId, status]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { followups, loading, error, refresh };
}
