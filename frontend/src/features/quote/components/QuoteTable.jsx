import { Badge } from "@/shared/components/ui";
import { formatPrice } from "@/shared/lib/format";

import { useQuoteTable } from "../hooks";
import QuoteTableToolbar from "./QuoteTableToolbar";

const COLUMNS = [
  { key: "supplier_name", label: "Supplier", sortable: true },
  { key: "unit_price", label: "Unit Price", sortable: true },
  { key: "lead_time", label: "Lead Time", sortable: true },
  { key: null, label: "Payment Terms", sortable: false },
  { key: "total_price", label: "Total Price", sortable: true },
  { key: null, label: "Remarks", sortable: false },
  { key: "actions", label: "", sortable: false },
];

function QuoteTable({ quotes = [], onEdit, onDelete }) {
  const { rows, query, setQuery, sort, toggleSort, bestId, total, visible } =
    useQuoteTable(quotes);

  if (total === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border-strong bg-surface p-12 text-center">
        <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-surface-2 text-subtle">
          <svg
            className="h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12l-3-3m0 0l-3 3m3-3v6m-1.5-15H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
            />
          </svg>
        </div>
        <p className="text-sm font-medium text-content">No quotes yet</p>
        <p className="mt-1 text-xs text-subtle">
          Add a quote manually or import via CSV / PDF
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border-default bg-surface shadow-card">
      <QuoteTableToolbar
        query={query}
        setQuery={setQuery}
        total={total}
        visible={visible}
      />

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-border-default bg-surface-2">
              {COLUMNS.map((col, index) => (
                <SortableHeader
                  key={col.label || index}
                  column={col}
                  sort={sort}
                  onSort={toggleSort}
                />
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border-default">
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={COLUMNS.length}
                  className="px-5 py-10 text-center text-sm text-muted"
                >
                  No quotes match “{query}”.
                </td>
              </tr>
            ) : (
              rows.map((quote) => {
                const isBest = quote.id === bestId;
                return (
                  <tr
                    key={quote.id}
                    className={`transition ${
                      isBest ? "bg-success-soft/40" : "hover:bg-surface-hover"
                    }`}
                  >
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-xs font-semibold text-primary-soft-fg">
                          {quote.supplier_name.charAt(0).toUpperCase()}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-content">
                            {quote.supplier_name}
                          </span>
                          {isBest && (
                            <Badge variant="success">
                              <svg
                                className="h-2.5 w-2.5"
                                fill="currentColor"
                                viewBox="0 0 20 20"
                              >
                                <path
                                  fillRule="evenodd"
                                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                  clipRule="evenodd"
                                />
                              </svg>
                              Best
                            </Badge>
                          )}
                        </div>
                      </div>
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 font-medium text-muted">
                      {formatPrice(quote.unit_price, quote.currency)}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-muted">
                      {quote.lead_time} days
                    </td>

                    <td className="px-5 py-4 text-muted">
                      {quote.payment_terms || (
                        <span className="text-subtle">—</span>
                      )}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4">
                      <span
                        className={`font-semibold ${
                          isBest ? "text-success-soft-fg" : "text-content"
                        }`}
                      >
                        {formatPrice(quote.total_price, quote.currency)}
                      </span>
                    </td>

                    <td className="max-w-xs truncate px-5 py-4 text-muted">
                      {quote.remarks || <span className="text-subtle">—</span>}
                    </td>

                    <td className="px-5 py-4">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => onEdit?.(quote)}
                          className="rounded-lg p-1.5 text-subtle transition hover:bg-primary-soft hover:text-primary-soft-fg"
                          title="Edit quote"
                        >
                          <svg
                            className="h-4 w-4"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth={2}
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                            />
                          </svg>
                        </button>
                        <button
                          onClick={() => onDelete?.(quote)}
                          className="rounded-lg p-1.5 text-subtle transition hover:bg-danger-soft hover:text-danger-soft-fg"
                          title="Delete quote"
                        >
                          <svg
                            className="h-4 w-4"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth={2}
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                            />
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {visible > 1 && bestId != null && (
        <div className="flex items-center gap-2 border-t border-border-default bg-surface-2 px-5 py-3">
          <span className="inline-block h-2 w-2 rounded-full bg-success" />
          <p className="text-xs text-muted">
            Lowest total price is highlighted.
          </p>
        </div>
      )}
    </div>
  );
}

function SortableHeader({ column, sort, onSort }) {
  const base =
    "whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-subtle";

  if (!column.sortable) {
    return <th className={base}>{column.label}</th>;
  }

  const isActive = sort.key === column.key;

  return (
    <th className={base}>
      <button
        type="button"
        onClick={() => onSort(column.key)}
        className={`inline-flex items-center gap-1 transition hover:text-content ${
          isActive ? "text-content" : ""
        }`}
      >
        {column.label}
        <svg
          className={`h-3 w-3 transition ${
            isActive ? "opacity-100" : "opacity-30"
          } ${isActive && sort.direction === "desc" ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2.5}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
        </svg>
      </button>
    </th>
  );
}

export default QuoteTable;
