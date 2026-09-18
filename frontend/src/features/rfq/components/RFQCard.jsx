import { Link } from "react-router-dom";

import { Badge, Card } from "@/shared/components/ui";
import { buttonClass } from "@/shared/lib/button";
import { formatNumber, formatRelativeTime, toNumber } from "@/shared/lib/format";
import { StatusBadge } from "@/shared/components/StatusBadge";

/**
 * One RFQ in the list.
 *
 * Shows the counters the buyer actually makes decisions with: who has answered
 * out of who was invited, who is still silent, whose quote is incomplete, and
 * whether there is enough complete data to run a comparison. The countdown
 * badge turns red past the deadline rather than just going quiet.
 */
function RFQCard({ rfq, onDelete }) {
  const invited = toNumber(rfq.invitation_count) || 0;
  const responded = toNumber(rfq.responded_count) || 0;
  const pending = toNumber(rfq.pending_count) || 0;
  const incomplete = toNumber(rfq.incomplete_count) || 0;
  const quotes = toNumber(rfq.quote_count) || 0;

  const progress = invited ? Math.round((responded / invited) * 100) : 0;

  const deadline = rfq.deadline ? new Date(rfq.deadline) : null;
  const overdue = deadline ? deadline.getTime() < Date.now() : false;

  return (
    <Card className="group relative overflow-hidden p-5 transition duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-elevated sm:p-6">
      {/* Accent rail */}
      <span className="absolute inset-y-0 left-0 w-1 bg-linear-to-b from-primary to-violet-500 opacity-0 transition group-hover:opacity-100" />

      <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-start">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="neutral">{rfq.rfq_number}</Badge>
            <StatusBadge status={rfq.status} domain="rfq" />
            {rfq.ready_to_compare && (
              <Badge variant="success">Ready to compare</Badge>
            )}
          </div>

          <h2 className="mt-3 truncate text-base font-semibold text-content">
            {rfq.item_name}
          </h2>

          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm">
            {rfq.specification && (
              <span className="text-muted">{rfq.specification}</span>
            )}
            <span className="text-muted">
              {formatNumber(rfq.quantity)} {rfq.unit || "pcs"}
            </span>
            <span className="text-subtle">
              Delivery {rfq.delivery_expectation || "—"}
            </span>
          </div>

          {/* Progress: responded / invited */}
          <div className="mt-4 max-w-md">
            <div className="flex items-center justify-between gap-3 text-xs">
              <span className="font-medium text-muted">
                {responded} of {invited} responded
              </span>
              <span className="text-subtle">{progress}%</span>
            </div>

            <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
              <span
                className="block h-full rounded-full bg-linear-to-r from-primary to-violet-500 transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>

            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {pending > 0 && (
                <span className="rounded-full bg-warning-soft px-2 py-0.5 text-[11px] font-medium text-warning-soft-fg">
                  {pending} pending
                </span>
              )}
              {incomplete > 0 && (
                <span className="rounded-full bg-danger-soft px-2 py-0.5 text-[11px] font-medium text-danger-soft-fg">
                  {incomplete} incomplete
                </span>
              )}
              {pending === 0 && incomplete === 0 && invited > 0 && (
                <span className="rounded-full bg-success-soft px-2 py-0.5 text-[11px] font-medium text-success-soft-fg">
                  All responses in
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex shrink-0 flex-col items-start gap-3 lg:items-end">
          <div className="text-left lg:text-right">
            <p className="text-xs font-medium uppercase tracking-wider text-subtle">
              Deadline
            </p>
            {deadline ? (
              <div className="mt-1 flex items-center gap-2">
                <span className="text-sm font-medium text-content">
                  {deadline.toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  })}
                </span>
                <Badge variant={overdue ? "danger" : "warning"}>
                  {overdue
                    ? `Overdue ${formatRelativeTime(rfq.deadline)}`
                    : formatRelativeTime(rfq.deadline)}
                </Badge>
              </div>
            ) : (
              <p className="mt-1 text-sm text-subtle">No deadline set</p>
            )}

            <p className="mt-1.5 text-xs text-subtle">
              {quotes} quote{quotes === 1 ? "" : "s"} received
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {rfq.ready_to_compare && (
              <Link
                to={`/rfqs/${rfq.id}?tab=comparison`}
                className={buttonClass("soft", "sm")}
              >
                Compare
              </Link>
            )}

            <Link
              to={`/rfqs/${rfq.id}`}
              className={buttonClass("outline", "sm")}
            >
              Open
            </Link>

            <button
              type="button"
              onClick={() => onDelete(rfq)}
              aria-label={`Delete ${rfq.item_name}`}
              className="inline-flex items-center justify-center rounded-xl bg-surface-2 px-3 py-2 text-subtle transition hover:bg-danger-soft hover:text-danger-soft-fg"
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
    </Card>
  );
}

export default RFQCard;
