import { useState } from "react";

import EmptyState from "@/shared/components/EmptyState";
import { Badge } from "@/shared/components/ui";
import {
  formatDate,
  formatFieldKey,
  formatHours,
  formatLeadTime,
  formatNumber,
  formatPercentValue,
  formatPrice,
  formatRateBasis,
  toNumber,
} from "@/shared/lib/format";
import { StatusBadge } from "@/shared/components/StatusBadge";

import { landedCostOf, useQuoteTable } from "../hooks";
import QuoteTableToolbar from "./QuoteTableToolbar";

/**
 * Side-by-side quote table.
 *
 * Columns are one ordered list, built from the RFQ's procurement type, because
 * the buyer scans it horizontally and the *order* is the argument: a service
 * quote leads with the rate, the basis it is quoted against and the response time
 * (the SLA is what most often decides which contractor wins), then the callout
 * charge, then GST. That is the invoice, in the order it arrives.
 *
 * The goods-only columns (MOQ, Incoterms, freight, duties) are hidden behind a
 * toggle for a service RFQ rather than deleted: they are neither asked for nor
 * normalised on a maintenance job, but a buyer checking a quote that volunteered
 * a freight figure must still be able to see it.
 *
 * Money, rates and scores arrive as JSON strings from Python `Decimal`, so every
 * value goes through `toNumber()` before it is formatted or compared — otherwise
 * `formatPrice("1200.00")` would print NaN.
 */
function QuoteTable({
  quotes = [],
  procurementType = "",
  requiredAccreditations = [],
  onEdit,
  onDelete,
}) {
  const { rows, query, setQuery, sort, toggleSort, bestId, total, visible } =
    useQuoteTable(quotes);

  const isGoods = procurementType === "goods";
  const [showGoodsColumns, setShowGoodsColumns] = useState(isGoods);

  if (total === 0) {
    return (
      <EmptyState
        title="No quotes yet"
        description="Suppliers submit through their private links, or add one here manually or by importing a CSV / PDF."
      />
    );
  }

  const isBest = (quote) => quote.id === bestId;

  const columns = [
    {
      key: "supplier_name",
      label: "Supplier",
      sortable: true,
      cell: (quote) => (
        <div className="flex items-start gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-xs font-semibold text-primary-soft-fg">
            {(quote.supplier_name || "?").charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="truncate font-medium text-content">
                {quote.supplier_name}
              </span>
              {isBest(quote) && (
                <Badge variant="success">
                  {isGoods ? "Lowest landed" : "Lowest total"}
                </Badge>
              )}
            </div>
            <p className="mt-0.5 truncate text-xs text-subtle">
              {quote.reference_number ? `${quote.reference_number} · ` : ""}
              {quote.source || "manual"}
            </p>
          </div>
        </div>
      ),
    },
    {
      key: "unit_price",
      label: isGoods ? "Quoted price" : "Rate",
      sortable: true,
      cell: (quote) => (
        <span className="font-medium text-muted">
          {formatPrice(toNumber(quote.unit_price), quote.currency)}
        </span>
      ),
    },
    {
      key: null,
      label: isGoods ? "Unit" : "Rate basis",
      cell: (quote) =>
        quote.unit ? (
          <span className="text-muted">
            {isGoods ? quote.unit : formatRateBasis(quote.unit)}
          </span>
        ) : (
          <span className="text-subtle">—</span>
        ),
    },
    ...(isGoods
      ? []
      : [
          {
            key: "response_time_hours",
            label: "Response (SLA)",
            sortable: true,
            cell: (quote) => {
              const hours = toNumber(quote.response_time_hours);

              return hours === null ? (
                <span className="text-subtle">not stated</span>
              ) : (
                <span
                  className={`font-medium ${
                    hours > 24 ? "text-warning-soft-fg" : "text-content"
                  }`}
                  title={
                    hours > 24
                      ? "Over one business day — the engine flags this as a risk."
                      : undefined
                  }
                >
                  {formatHours(hours)}
                </span>
              );
            },
          },
          {
            key: "callout_charge",
            label: "Callout / attendance",
            sortable: true,
            cell: (quote) => {
              const callout = toNumber(quote.callout_charge);
              const labour = toNumber(quote.labour_rate);
              const markup = toNumber(quote.materials_markup_pct);

              return (
                <div className="space-y-0.5">
                  {callout === null ? (
                    <span className="text-subtle">not stated</span>
                  ) : (
                    <span className="text-content">
                      {formatPrice(callout, quote.currency)}
                    </span>
                  )}

                  {labour !== null && (
                    <span className="block text-[11px] text-subtle">
                      labour {formatPrice(labour, quote.currency)}/h
                    </span>
                  )}

                  {markup !== null && (
                    <span
                      className={`block text-[11px] ${
                        markup > 20 ? "text-warning-soft-fg" : "text-subtle"
                      }`}
                    >
                      materials +{formatPercentValue(markup)}
                    </span>
                  )}
                </div>
              );
            },
          },
          {
            key: "gst_rate",
            label: "GST",
            sortable: true,
            cell: (quote) => {
              const gst = toNumber(quote.gst_rate);

              return gst === null ? (
                <span className="text-subtle">—</span>
              ) : (
                <span className="text-muted">{formatPercentValue(gst)}</span>
              );
            },
          },
        ]),
    ...(isGoods || showGoodsColumns
      ? [
          {
            key: "moq",
            label: isGoods ? "MOQ" : "Min callout / order",
            sortable: true,
            cell: (quote) => (
              <span className="text-muted">{formatNumber(quote.moq)}</span>
            ),
          },
          {
            key: null,
            label: "Incoterms",
            cell: (quote) => (
              <span className="text-muted">
                {quote.incoterms || <span className="text-subtle">—</span>}
              </span>
            ),
          },
          {
            key: "shipping_cost",
            label: "Shipping",
            sortable: true,
            cell: (quote) => (
              <span className="text-muted">
                {formatPrice(toNumber(quote.shipping_cost), quote.currency)}
              </span>
            ),
          },
          {
            key: "duties",
            label: "Duties",
            sortable: true,
            cell: (quote) => (
              <span className="text-muted">
                {formatPrice(toNumber(quote.duties), quote.currency)}
              </span>
            ),
          },
        ]
      : []),
    {
      key: "normalized_unit_price",
      label: isGoods ? "Normalised unit" : "Normalised rate",
      sortable: true,
      cell: (quote) =>
        quote.normalized_unit_price == null ? (
          <span className="text-subtle">—</span>
        ) : (
          <span className="text-muted">
            {formatPrice(
              toNumber(quote.normalized_unit_price),
              quote.normalized_currency || quote.currency
            )}
          </span>
        ),
    },
    {
      key: "normalized_total_cost",
      label: isGoods ? "Landed cost" : "Total cost",
      sortable: true,
      cell: (quote) => (
        <span
          className={`font-semibold ${
            isBest(quote) ? "text-success-soft-fg" : "text-content"
          }`}
        >
          {Number.isFinite(landedCostOf(quote))
            ? formatPrice(
                landedCostOf(quote),
                quote.normalized_currency || quote.currency
              )
            : "—"}
        </span>
      ),
    },
    {
      key: "lead_time",
      label: isGoods ? "Lead time" : "Mobilisation",
      sortable: true,
      cell: (quote) => (
        <span className="text-muted">{formatLeadTime(quote.lead_time)}</span>
      ),
    },
    {
      key: null,
      label: "Payment terms",
      cell: (quote) => (
        <span className="text-muted">
          {quote.payment_terms || <span className="text-subtle">—</span>}
        </span>
      ),
    },
    {
      key: null,
      label: isGoods ? "Validity" : "Rates valid until",
      cell: (quote) =>
        quote.validity_date ? (
          <span className="text-muted">{formatDate(quote.validity_date)}</span>
        ) : (
          <span className="text-subtle">—</span>
        ),
    },
    {
      key: null,
      label: isGoods ? "Warranty" : "Defect liability",
      cell: (quote) =>
        quote.warranty_months == null ? (
          <span className="text-subtle">—</span>
        ) : (
          <span className="text-muted">
            {formatNumber(quote.warranty_months)} months
          </span>
        ),
    },
    {
      key: "composite_score",
      label: "Score",
      sortable: true,
      cell: (quote) =>
        quote.composite_score == null ? (
          <span className="text-subtle">—</span>
        ) : (
          <span className="font-semibold text-content">
            {formatNumber(quote.composite_score, { maximumFractionDigits: 1 })}
          </span>
        ),
    },
    {
      key: null,
      label: "Completeness",
      cell: (quote, { missingLabels }) => (
        <div>
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
        </div>
      ),
    },
    {
      key: null,
      label: "Accreditations & licences",
      cell: (quote) => (
        <AccreditationCell quote={quote} required={requiredAccreditations} />
      ),
    },
    {
      key: null,
      label: "Risk flags",
      cell: (quote) =>
        quote.risk_flags?.length ? (
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
        ),
    },
    {
      key: null,
      label: "Attachments",
      cell: (quote) =>
        quote.attachments?.length ? (
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
        ),
    },
    {
      key: null,
      label: "",
      cell: (quote) => (
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
      ),
    },
  ];

  return (
    <div className="overflow-hidden rounded-2xl border border-border-default bg-surface shadow-card">
      <QuoteTableToolbar
        query={query}
        setQuery={setQuery}
        total={total}
        visible={visible}
      />

      {!isGoods && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-default bg-surface-2/60 px-4 py-2">
          <p className="text-xs text-muted">
            Rates, response times and accreditations first — the goods-only
            columns are tucked away because nothing is shipped on a service job.
          </p>

          <button
            type="button"
            onClick={() => setShowGoodsColumns((prev) => !prev)}
            aria-expanded={showGoodsColumns}
            className="rounded-full bg-surface px-3 py-1 text-xs font-medium text-muted transition hover:text-content"
          >
            {showGoodsColumns
              ? "Hide additional (goods) columns"
              : "Show additional (goods) columns"}
          </button>
        </div>
      )}

      {/* Wide by design: the buyer scans money, terms and caveats side by side,
          so the table scrolls on phones instead of squashing into unreadable
          columns. */}
      <div className="overflow-x-auto">
        <table className="min-w-[1850px] w-full text-sm">
          <thead>
            <tr className="border-b border-border-default bg-surface-2">
              {columns.map((column, index) => (
                <SortableHeader
                  key={column.label || `column-${index}`}
                  column={column}
                  sort={sort}
                  onSort={toggleSort}
                  sticky={index === 0}
                />
              ))}
            </tr>
          </thead>

          <tbody className="divide-y divide-border-default">
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-5 py-10 text-center text-sm text-muted"
                >
                  No quotes match “{query}”.
                </td>
              </tr>
            ) : (
              rows.map((quote) => {
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
                    className={`group align-top transition ${
                      isBest(quote) ? "bg-success-soft/40" : "hover:bg-surface-hover"
                    }`}
                  >
                    {columns.map((column, index) => (
                      <td
                        key={column.label || `column-${index}`}
                        className={`px-5 py-4 ${
                          column.key ? "whitespace-nowrap" : ""
                        } ${
                          index === 0 ? STICKY_FIRST_CELL(isBest(quote)) : ""
                        }`}
                      >
                        {column.cell(quote, { missingLabels })}
                      </td>
                    ))}
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
            {isGoods
              ? "Highlighted row has the lowest landed cost after currency, unit and Incoterms normalisation."
              : "Highlighted row has the lowest total after converting every rate into one currency and one rate basis — callout charges and derived GST included."}
          </p>
        </div>
      )}
    </div>
  );
}

/**
 * What the supplier holds, and what they do not.
 *
 * The missing chips are the "cannot lawfully do the work" signal, so they are
 * danger-coloured and named rather than counted; a held licence is a quiet chip
 * so the eye lands on the gap.
 *
 * `missing_accreditations` is computed by the API on a comparison result, but the
 * quote projection (`QuoteSummary`) carries only what the supplier claims, so
 * while the RFQ's required list is in hand the gap is derived here as the same
 * set difference the scoring engine applies. The API's own field wins whenever it
 * is present, so this can never disagree with the recorded score.
 */
function AccreditationCell({ quote, required = [] }) {
  const held = quote.compliance_accreditations || [];
  const missing =
    quote.missing_accreditations ||
    required.filter((accreditation) => !held.includes(accreditation));

  if (!held.length && !missing.length) {
    return <span className="text-subtle">—</span>;
  }

  return (
    <div className="max-w-[16rem] space-y-1.5">
      {missing.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {missing.map((accreditation) => (
            <span
              key={accreditation}
              title={`This RFQ requires ${accreditation}; the quote does not show it. The compliance score is capped because the work may not lawfully proceed without it.`}
              className="rounded-full bg-danger-soft px-2 py-0.5 text-[11px] font-medium text-danger-soft-fg"
            >
              ✕ {accreditation}
            </span>
          ))}
        </div>
      )}

      {held.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {held.map((accreditation) => (
            <span
              key={accreditation}
              className="rounded-full bg-success-soft px-2 py-0.5 text-[11px] font-medium text-success-soft-fg"
            >
              {accreditation}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Classes for the pinned first column.
 *
 * This table is 1850px wide and scrolls. On a 1440px screen the visible window is
 * about 1230px, so scrolling right to reach the money columns pushed the supplier
 * cell off-screen and every row read as anonymous — the buyer could see a price
 * but not whose price it was. The first column now stays put.
 *
 * The background must be **opaque**. A sticky cell paints above the cells sliding
 * under it, so a translucent tint — the row's `bg-success-soft/40` for the leading
 * quote — would let the moving content show through the pinned cell and defeat the
 * whole point. `bg-success-soft` is the opaque token, so the leading row's pinned
 * cell is a slightly stronger tint than the rest of that row: a deliberate
 * compromise, and far better than an unreadable column.
 */
const STICKY_FIRST_CELL = (isBest) =>
  `sticky left-0 z-10 ${
    isBest ? "bg-success-soft" : "bg-surface group-hover:bg-surface-hover"
  }`;

function SortableHeader({ column, sort, onSort, sticky = false }) {
  const base =
    "whitespace-nowrap px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-subtle";

  // z-20 so the pinned header stays above the pinned body cells.
  const className = sticky
    ? `${base} sticky left-0 z-20 bg-surface-2`
    : base;

  if (!column.sortable) {
    return <th className={className}>{column.label}</th>;
  }

  const isActive = sort.key === column.key;

  return (
    <th className={className}>
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
