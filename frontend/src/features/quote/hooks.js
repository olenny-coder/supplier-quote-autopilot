import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { toNumber } from "@/shared/lib/format";

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
//
// Money/int fields are parsed with `toNumber` because the API serialises Python
// `Decimal` as a string, and `"1200.00" < "900.00"` is true for strings.
const SORT_ACCESSORS = {
  supplier_name: (q) => (q.supplier_name || "").toLowerCase(),
  unit_price: (q) => toNumber(q.unit_price) ?? Number.POSITIVE_INFINITY,
  normalized_unit_price: (q) =>
    toNumber(q.normalized_unit_price) ?? Number.POSITIVE_INFINITY,
  normalized_total_cost: (q) =>
    toNumber(q.normalized_total_cost) ?? Number.POSITIVE_INFINITY,
  total_price: (q) => toNumber(q.total_price) ?? Number.POSITIVE_INFINITY,
  lead_time: (q) => toNumber(q.lead_time) ?? Number.POSITIVE_INFINITY,
  moq: (q) => toNumber(q.moq) ?? Number.POSITIVE_INFINITY,
  composite_score: (q) => toNumber(q.composite_score) ?? -1,
  // Services. A missing response time or callout sorts last, never first: an
  // absent SLA is not a fast one.
  response_time_hours: (q) =>
    toNumber(q.response_time_hours) ?? Number.POSITIVE_INFINITY,
  callout_charge: (q) => toNumber(q.callout_charge) ?? Number.POSITIVE_INFINITY,
  labour_rate: (q) => toNumber(q.labour_rate) ?? Number.POSITIVE_INFINITY,
  materials_markup_pct: (q) =>
    toNumber(q.materials_markup_pct) ?? Number.POSITIVE_INFINITY,
  gst_rate: (q) => toNumber(q.gst_rate) ?? Number.POSITIVE_INFINITY,
  shipping_cost: (q) => toNumber(q.shipping_cost) ?? Number.POSITIVE_INFINITY,
  duties: (q) => toNumber(q.duties) ?? Number.POSITIVE_INFINITY,
};

/**
 * The landed cost a quote is judged on: normalised total when the quote has
 * been normalised, otherwise the raw unit price x quantity. Used for sorting,
 * for the "lowest landed cost" highlight, and by every page that needs one
 * comparable number per quote.
 */
export function landedCostOf(quote) {
  return (
    toNumber(quote.normalized_total_cost) ??
    toNumber(quote.total_price) ??
    Number.POSITIVE_INFINITY
  );
}

/**
 * Client-side view-model for the quote table: search filtering, column
 * sorting, and best-quote detection. Pure derivation over `quotes` — the
 * table component stays presentational.
 */
export function useQuoteTable(quotes) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState({ key: "normalized_total_cost", direction: "asc" });

  // "Best" is the lowest landed cost among quotes that were normalised; a quote
  // with no price at all can never win.
  const bestId = useMemo(() => {
    const priced = quotes.filter(
      (quote) => Number.isFinite(landedCostOf(quote)) && landedCostOf(quote) !== Infinity
    );

    if (!priced.length) return null;

    return priced.reduce((best, current) =>
      landedCostOf(current) < landedCostOf(best) ? current : best
    ).id;
  }, [quotes]);

  const rows = useMemo(() => {
    const term = query.trim().toLowerCase();

    const filtered = term
      ? quotes.filter((q) =>
          [
            q.supplier_name,
            q.payment_terms,
            q.incoterms,
            q.remarks,
            q.reference_number,
            // Licences are part of how a services quote is shortlisted, so
            // "LEW" has to find the suppliers who hold it.
            (q.compliance_accreditations || []).join(" "),
          ]
            .filter(Boolean)
            .some((field) => String(field).toLowerCase().includes(term))
        )
      : quotes;

    const accessor =
      SORT_ACCESSORS[sort.key] ?? SORT_ACCESSORS.normalized_total_cost;

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
