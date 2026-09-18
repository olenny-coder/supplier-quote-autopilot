import { Link } from "react-router-dom";

import { Badge } from "@/shared/components/ui";
import { formatDate } from "@/shared/lib/format";

function RFQCard({ rfq, onDelete }) {
  const formattedDate = rfq.delivery_expectation
    ? formatDate(rfq.delivery_expectation)
    : null;

  return (
    <div className="group relative overflow-hidden rounded-2xl border border-border-default bg-surface p-5 shadow-card transition duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-elevated sm:p-6">
      {/* Accent rail */}
      <span className="absolute inset-y-0 left-0 w-1 bg-linear-to-b from-primary to-violet-500 opacity-0 transition group-hover:opacity-100" />

      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="truncate text-base font-semibold text-content">
              {rfq.item_name}
            </h2>
            {rfq.specification && (
              <Badge variant="primary">{rfq.specification}</Badge>
            )}
          </div>

          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
            <MetaItem
              icon={
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
                    d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
                  />
                </svg>
              }
              label="Qty"
              value={rfq.quantity.toLocaleString()}
            />
            {formattedDate && (
              <MetaItem
                icon={
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
                      d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                    />
                  </svg>
                }
                label="Delivery"
                value={formattedDate}
              />
            )}
            {rfq.notes && (
              <MetaItem
                icon={
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
                      d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                    />
                  </svg>
                }
                label="Notes"
                value={rfq.notes}
                truncate
              />
            )}
          </div>
        </div>

        <div className="flex shrink-0 gap-2">
          <Link
            to={`/rfqs/${rfq.id}`}
            className="inline-flex items-center justify-center rounded-lg bg-primary-soft px-4 py-2 text-sm font-medium text-primary-soft-fg transition hover:brightness-105"
          >
            View
          </Link>

          <button
            type="button"
            onClick={() => onDelete(rfq)}
            aria-label={`Delete ${rfq.item_name}`}
            className="inline-flex items-center justify-center rounded-lg bg-surface-2 px-3 py-2 text-subtle transition hover:bg-danger-soft hover:text-danger-soft-fg"
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
      </div>
    </div>
  );
}

function MetaItem({ icon, label, value, truncate = false }) {
  return (
    <div className="flex items-center gap-1.5 text-sm">
      <span className="text-subtle">{icon}</span>
      <span className="text-xs text-subtle">{label}:</span>
      <span
        className={`font-medium text-muted ${truncate ? "max-w-xs truncate" : ""}`}
      >
        {value}
      </span>
    </div>
  );
}

export default RFQCard;
