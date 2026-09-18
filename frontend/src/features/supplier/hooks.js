import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { toNumber } from "@/shared/lib/format";

import { getSuppliers } from "./api";

/**
 * Load the supplier directory. Encapsulates the fetch + loading + error-toast
 * pattern so the page doesn't re-implement it.
 *
 * The failure message is kept in state as well as toasted: the list can be
 * empty *because* the request failed, and the page renders `error` as an inline
 * panel with a retry button rather than showing a misleading empty directory.
 */
export function useSuppliers() {
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);

      const data = await getSuppliers();

      setSuppliers(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err) {
      const message = err?.message || "Unable to load suppliers";

      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { suppliers, loading, error, refresh };
}

/**
 * Roll the per-supplier counters up into directory totals.
 *
 * A plain function rather than a hook so the page can wrap it in `useMemo`.
 * Counts arrive as JSON numbers *or* strings (Python serialises some numeric
 * fields as strings), so each one goes through `toNumber()` before arithmetic —
 * summing raw values would silently concatenate strings. Missing counters are
 * treated as zero so an incomplete row never poisons the totals with NaN.
 */
export function summariseSuppliers(suppliers) {
  const list = Array.isArray(suppliers) ? suppliers : [];

  return list.reduce(
    (totals, supplier) => ({
      total: totals.total + 1,
      invited: totals.invited + (toNumber(supplier.invitations_total) ?? 0),
      responded: totals.responded + (toNumber(supplier.invitations_responded) ?? 0),
      quotesReceived: totals.quotesReceived + (toNumber(supplier.quotes_total) ?? 0),
    }),
    { total: 0, invited: 0, responded: 0, quotesReceived: 0 }
  );
}
