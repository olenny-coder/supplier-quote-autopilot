import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { getQuotesByRFQ } from "./api";

/**
 * Load supplier quotes for an RFQ.
 */
export function useQuotes(rfqId) {
  const [quotes, setQuotes] = useState([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!rfqId) return;

    try {
      setLoading(true);
      const data = await getQuotesByRFQ(rfqId);
      setQuotes(data);
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

  return { quotes, loading, refresh };
}

// Field accessors for client-side sorting. Keeping this map here makes adding
// a new sortable column a one-line change.
const SORT_ACCESSORS = {
  supplier_name: (q) => (q.supplier_name || "").toLowerCase(),
  unit_price: (q) => Number(q.unit_price),
  lead_time: (q) => Number(q.lead_time),
  total_price: (q) => Number(q.total_price),
};

/**
 * Client-side view-model for the quote table: search filtering, column
 * sorting, and best-quote detection. Pure derivation over `quotes` — the
 * table component stays presentational.
 */
export function useQuoteTable(quotes) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState({ key: "total_price", direction: "asc" });

  const bestId = useMemo(() => {
    if (!quotes.length) return null;
    return quotes.reduce((best, cur) =>
      Number(cur.total_price) < Number(best.total_price) ? cur : best
    ).id;
  }, [quotes]);

  const rows = useMemo(() => {
    const term = query.trim().toLowerCase();

    const filtered = term
      ? quotes.filter((q) =>
          [q.supplier_name, q.payment_terms, q.remarks]
            .filter(Boolean)
            .some((field) => field.toLowerCase().includes(term))
        )
      : quotes;

    const accessor = SORT_ACCESSORS[sort.key] ?? SORT_ACCESSORS.total_price;

    return [...filtered].sort((a, b) => {
      const av = accessor(a);
      const bv = accessor(b);
      if (av < bv) return sort.direction === "asc" ? -1 : 1;
      if (av > bv) return sort.direction === "asc" ? 1 : -1;
      return 0;
    });
  }, [quotes, query, sort]);

  const toggleSort = useCallback((key) => {
    setSort((prev) =>
      prev.key === key
        ? { key, direction: prev.direction === "asc" ? "desc" : "asc" }
        : { key, direction: "asc" }
    );
  }, []);

  return {
    rows,
    query,
    setQuery,
    sort,
    toggleSort,
    bestId,
    total: quotes.length,
    visible: rows.length,
  };
}
