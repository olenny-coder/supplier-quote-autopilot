import { useCallback, useEffect, useRef, useState } from "react";

import { toast } from "sonner";

import { getAuditLog } from "./api";

/**
 * Audit log data hook.
 *
 * Same shape as every other hook in the app: it owns `loading`, surfaces the
 * failure as a string *and* as a toast, and guards every `setState` with a
 * mounted ref so a slow response landing after navigation cannot update an
 * unmounted component.
 *
 * Paging is "load more" rather than numbered pages, because the useful question
 * is almost always "what happened recently?" — and the server returns the total,
 * so the page can say how much is left without guessing.
 */
export function useAuditLog(filters, pageSize = 50) {
  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [availableActions, setAvailableActions] = useState([]);
  const [availableRfqs, setAvailableRfqs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);

  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
    };
  }, []);

  // The filter object is rebuilt on every render by the page, so it is compared by
  // value here. Without this the effect would re-run on every keystroke in an
  // unrelated input and refetch the log.
  const filterKey = JSON.stringify(filters);

  const load = useCallback(
    async ({ offset = 0, append = false } = {}) => {
      if (!mountedRef.current) return;

      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }

      setError(null);

      try {
        const data = await getAuditLog({
          ...JSON.parse(filterKey),
          limit: pageSize,
          offset,
        });

        if (!mountedRef.current) return;

        setEntries((previous) =>
          append ? [...previous, ...data.entries] : data.entries
        );
        setTotal(data.total);
        setAvailableActions(data.available_actions || []);
        setAvailableRfqs(data.available_rfqs || []);
      } catch (failure) {
        if (!mountedRef.current) return;

        setError(failure.message);
        toast.error(failure.message);
      } finally {
        if (mountedRef.current) {
          setLoading(false);
          setLoadingMore(false);
        }
      }
    },
    [filterKey, pageSize]
  );

  useEffect(() => {
    load({ offset: 0, append: false });
  }, [load]);

  const loadMore = useCallback(() => {
    load({ offset: entries.length, append: true });
  }, [entries.length, load]);

  const refresh = useCallback(() => {
    load({ offset: 0, append: false });
  }, [load]);

  return {
    entries,
    total,
    availableActions,
    availableRfqs,
    loading,
    loadingMore,
    error,
    hasMore: entries.length < total,
    loadMore,
    refresh,
  };
}
