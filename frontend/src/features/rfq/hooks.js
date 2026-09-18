import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { getRFQById, getRFQs } from "./api";

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
      console.error(error);
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
 * Load a single RFQ by id.
 */
export function useRFQ(rfqId) {
  const [rfq, setRfq] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!rfqId) return;

    try {
      setLoading(true);
      const data = await getRFQById(rfqId);
      setRfq(data);
    } catch (error) {
      console.error(error);
      toast.error(error.message);
    } finally {
      setLoading(false);
    }
  }, [rfqId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { rfq, loading, refresh };
}
