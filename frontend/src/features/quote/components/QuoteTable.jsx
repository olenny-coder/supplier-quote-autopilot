import EmptyState from "@/shared/components/EmptyState";
import { Badge } from "@/shared/components/ui";
import {
  formatDate,
  formatFieldKey,
  formatLeadTime,
  formatNumber,
  formatPrice,
  toNumber,
} from "@/shared/lib/format";
import { StatusBadge } from "@/shared/components/StatusBadge";

import { landedCostOf, useQuoteTable } from "../hooks";
import QuoteTableToolbar from "./QuoteTableToolbar";

/**
 * Side-by-side quote table.
 *
 * Columns are one flat list because the buyer scans it horizontally: the quoted
 * numbers first (as the supplier wrote them), then the normalised landed cost
 * the comparison engine actually scores, then the commercial terms, then the
 * caveats (completeness, risk flags, attachments).
 *
 * Money arrives as JSON strings from Python `Decimal`, so every value goes
 * through `toNumber()` before it is formatted or compared — otherwise
 * `formatPrice("1200.00")` would print NaN.
 */
const COLUMNS = [
  { key: "supplier_name", label: "Supplier", sortable: true },
  { key: "unit_price", label: "Quoted price", sortable: true },
  { key: null, label: "Unit", sortable: false },
  { key: "normalized_unit_price", label: "Normalised unit", sortable: true },
  { key: "normalized_total_cost", label: "Landed cost", sortable: true },
  { key: "lead_time", label: "Lead time", sortable: true },
  { key: "moq", label: "MOQ", sortable: true },
  { key: null, label: "Payment terms", sortable: false },
  { key: null, label: "Incoterms", sortable: false },
  { key: null, label: "Validity", sortable: false },
  { key: null, label: "Warranty", sortable: false },
  { key: "composite_score", label: "Score", sortable: true },
  { key: null, label: "Completeness", sortable: false },
  { key: null, label: "Risk flags", sortable: false },
  { key: null, label: "Attachments", sortable: false },
  { key: null, label: "", sortable: false },
];

function QuoteTable({ quotes = [], onEdit, onDelete }) {
  const { rows, query, setQuery, sort, toggleSort, bestId, total, visible } =
    useQuoteTable(quotes);

  if (total === 0) {
    return (
      <EmptyState
        title="No quotes yet"
        description="Suppliers submit through their private links, or add one here manually or by importing a CSV / PDF."
      />
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

      {/* Wide by design: the buyer scans money, terms and caveats side by side,
          so the table scrolls on phones instead of squashing into unreadable
          columns. */}
      <div className="overflow-x-auto">
        <table className="min-w-[1600px] w-full text-sm">
          <thead>
            <tr className="border-b border-border-default bg-surface-2">
              {COLUMNS.map((column, index) => (
                <SortableHeader
                  key={column.label || `column-${index}`}
                  column={column}
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

                // Prefer the API's human labels; fall back to mapping the keys
                // so an incomplete quote is never an unlabelled chip.
                const missingLabels =
                  quote.missing_field_labels?.length > 0
                    ? quote.missing_field_labels
                    : (quote.missing_fields || []).map((field) =>
                        formatFieldKey(field)
                      );

                return (
                  <tr
                    key={quote.id}
                    className={`align-top transition ${
                      isBest ? "bg-success-soft/40" : "hover:bg-surface-hover"
                    }`}
                  >
                    <td className="px-5 py-4">
                      <div className="flex items-start gap-2.5">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-xs font-semibold text-primary-soft-fg">
                          {(quote.supplier_name || "?").charAt(0).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="truncate font-medium text-content">
                              {quote.supplier_name}
                            </span>
                            {isBest && <Badge variant="success">Lowest landed</Badge>}
                          </div>
                          <p className="mt-0.5 truncate text-xs text-subtle">
                            {quote.reference_number ? `${quote.reference_number} · ` : ""}
                            {quote.source || "manual"}
                          </p>
                        </div>
                      </div>
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 font-medium text-muted">
                      {formatPrice(toNumber(quote.unit_price) ?? 0, quote.currency)}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-muted">
                      {quote.unit || "—"}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-muted">
                      {quote.normalized_unit_price == null ? (
                        <span className="text-subtle">—</span>
                      ) : (
                        formatPrice(
                          toNumber(quote.normalized_unit_price),
                          quote.normalized_currency || quote.currency
                        )
                      )}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4">
                      <span
                        className={`font-semibold ${
                          isBest ? "text-success-soft-fg" : "text-content"
                        }`}
                      >
                        {Number.isFinite(landedCostOf(quote))
                          ? formatPrice(
                              landedCostOf(quote),
                              quote.normalized_currency || quote.currency
                            )
                          : "—"}
                      </span>
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-muted">
                      {formatLeadTime(quote.lead_time)}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-muted">
                      {formatNumber(quote.moq)}
                    </td>

                    <td className="max-w-[12rem] px-5 py-4 text-muted">
                      {quote.payment_terms || <span className="text-subtle">—</span>}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-muted">
                      {quote.incoterms || <span className="text-subtle">—</span>}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-muted">
                      {quote.validity_date ? (
                        formatDate(quote.validity_date)
                      ) : (
                        <span className="text-subtle">—</span>
                      )}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-muted">
                      {quote.warranty_months == null ? (
                        <span className="text-subtle">—</span>
                      ) : (
                        `${formatNumber(quote.warranty_months)} months`
                      )}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4">
                      {quote.composite_score == null ? (
                        <span className="text-subtle">—</span>
                      ) : (
                        <span className="font-semibold text-content">
                          {formatNumber(quote.composite_score, {
                            maximumFractionDigits: 1,
                          })}
                        </span>
                      )}
                    </td>

                    <td className="px-5 py-4">
                      <StatusBadge status={quote.completeness} domain="quote" />

                      {missingLabels.length > 0 && (
                        <div className="mt-2 flex max-w-[14rem] flex-wrap gap-1.5">
                          {missingLabels.map((label) => (
                            <span
                              key={label}
                              className="rounded-full bg-warning-soft px-2 py-0.5 text-[11px] font-medium text-warning-soft-fg"
                            >
                              {label}
                            </span>
                          ))}
                        </div>
                      )}

                      {quote.blocking_question && (
                        <p className="mt-2 max-w-[14rem] text-xs leading-relaxed text-subtle">
                          {quote.blocking_question}
                        </p>
                      )}
                    </td>

                    <td className="px-5 py-4">
                      {quote.risk_flags?.length ? (
                        <div className="flex max-w-[16rem] flex-wrap gap-1.5">
                          {quote.risk_flags.slice(0, 2).map((flag) => (
                            <span
                              key={flag}
                              title={flag}
                              className="rounded-full bg-danger-soft px-2 py-0.5 text-[11px] font-medium text-danger-soft-fg"
                            >
                              {flag.length > 34 ? `${flag.slice(0, 34)}…` : flag}
                            </span>
                          ))}

                          {quote.risk_flags.length > 2 && (
                            <span
                              title={quote.risk_flags.slice(2).join("\n")}
                              className="rounded-full bg-surface-2 px-2 py-0.5 text-[11px] font-medium text-muted"
                            >
                              +{quote.risk_flags.length - 2} more
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-subtle">—</span>
                      )}
                    </td>

                    <td className="px-5 py-4">
                      {quote.attachments?.length ? (
                        <ul className="space-y-1">
                          {quote.attachments.map((attachment) => (
                            <li key={attachment.key || attachment.url}>
                              <a
                                href={attachment.url}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-1.5 text-xs font-medium text-primary transition hover:underline"
                              >
                                <svg
                                  className="h-3.5 w-3.5"
                                  fill="none"
                                  viewBox="0 0 24 24"
                                  stroke="currentColor"
                                  strokeWidth={2}
                                >
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
                                  />
                                </svg>
                                <span className="max-w-[10rem] truncate">
                                  {attachment.filename || "Attachment"}
                                </span>
                              </a>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <span className="text-subtle">—</span>
                      )}
                    </td>

                    <td className="px-5 py-4">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => onEdit?.(quote)}
                          className="rounded-lg p-1.5 text-subtle transition hover:bg-primary-soft hover:text-primary-soft-fg"
                          title="Edit quote"
                          aria-label={`Edit quote from ${quote.supplier_name}`}
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
                          type="button"
                          onClick={() => onDelete?.(quote)}
                          className="rounded-lg p-1.5 text-subtle transition hover:bg-danger-soft hover:text-danger-soft-fg"
                          title="Delete quote"
                          aria-label={`Delete quote from ${quote.supplier_name}`}
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
            Highlighted row has the lowest landed cost after currency, unit and
            Incoterms normalisation.
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
