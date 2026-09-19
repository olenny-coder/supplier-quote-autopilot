import { Link } from "react-router-dom";

import EmptyState from "@/shared/components/EmptyState";
import { Badge, Card } from "@/shared/components/ui";
import { buttonClass } from "@/shared/lib/button";
import {
  formatFieldKey,
  formatNumber,
  formatRelativeTime,
} from "@/shared/lib/format";
import { StatusBadge } from "@/shared/components/StatusBadge";

/**
 * "Needs attention" — the suppliers the buyer should chase: no response yet, or
 * a quote that is missing something the RFQ's own required-field contract asked
 * for (which the comparison engine cannot normalise fairly, and which the
 * follow-up engine is already drafting an email about). Each row deep-links into
 * the RFQ's Suppliers tab, where the reminder and chase actions live.
 *
 * The missing chips carry the API's supplier-facing labels when it sends them
 * (`missing_field_labels`) — for a maintenance RFQ that reads "response time
 * (SLA)", not "lead time".
 */
function NeedsAttentionPanel({ items = [] }) {
  return (
    <Card className="flex flex-col overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-border-default bg-surface-2/50 px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold text-content">Needs attention</h2>
          <p className="mt-0.5 text-xs text-muted">
            Contractors to chase before the deadline
          </p>
        </div>

        {items.length > 0 && (
          <span className="rounded-full bg-warning-soft px-2.5 py-0.5 text-xs font-semibold text-warning-soft-fg">
            {formatNumber(items.length)}
          </span>
        )}
      </div>

      {items.length === 0 ? (
        <div className="p-5">
          <EmptyState
            title="Everyone has responded"
            description="No contractor is silent and no quote is missing a required detail right now. Nicely done."
          />
        </div>
      ) : (
        <ul className="divide-y divide-border-default">
          {items.map((item) => {
            // The API sends supplier-facing labels on some projections and bare
            // keys on others; prefer the labels, map the keys as a fallback.
            const missingLabels = item.missing_field_labels?.length
              ? item.missing_field_labels
              : (item.missing_fields || []).map((field) => formatFieldKey(field));

            return (
              <li
                key={item.invitation_id}
                className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-start sm:justify-between"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="truncate text-sm font-semibold text-content">
                      {item.supplier_name}
                    </span>
                    <StatusBadge status={item.status} domain="invitation" />
                    <Badge variant="neutral">{item.rfq_number}</Badge>
                  </div>

                  <p className="mt-1.5 text-xs text-muted">{item.reason}</p>

                  {missingLabels.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
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

                  <p className="mt-2 text-[11px] text-subtle">
                    {formatNumber(item.reminder_count)} reminder
                    {item.reminder_count === 1 ? "" : "s"} sent
                    {item.next_reminder_at
                      ? ` · next ${formatRelativeTime(item.next_reminder_at)}`
                      : ""}
                  </p>
                </div>

                <Link
                  to={`/rfqs/${item.rfq_id}?tab=suppliers&invitation=${item.invitation_id}`}
                  className={`${buttonClass("soft", "sm")} shrink-0`}
                >
                  Chase now
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

export default NeedsAttentionPanel;
