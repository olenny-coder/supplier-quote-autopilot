import { useState } from "react";

import { Card } from "@/shared/components/ui";
import { formatNumber } from "@/shared/lib/format";

import FollowUpList from "@/features/followup/components/FollowUpList";
import { useRFQFollowUps } from "@/features/followup/hooks";

const STATUS_FILTERS = [
  { value: "all", label: "All messages" },
  { value: "draft", label: "Awaiting approval" },
  { value: "sent", label: "Sent" },
  { value: "failed", label: "Failed" },
  { value: "rejected", label: "Discarded" },
];

/**
 * Tab 4 — Follow-ups: the RFQ's communication log.
 *
 * Reads every message for this RFQ (drafts, sent, failed, discarded) through
 * `useRFQFollowUps`, and filters client-side so switching the view never costs
 * a round trip. Approve/Discard live inside `FollowUpList`, which refreshes
 * this log through `onChanged`.
 */
function FollowUpsTab({ rfqId }) {
  const { followups, loading, error, refresh } = useRFQFollowUps(rfqId);
  const [statusFilter, setStatusFilter] = useState("all");

  const visible =
    statusFilter === "all"
      ? followups
      : followups.filter((followup) => followup.status === statusFilter);

  const awaiting = followups.filter((followup) =>
    ["draft", "queued"].includes(followup.status)
  ).length;

  return (
    <div className="space-y-5">
      <Card className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-content">
            Communication log
          </h2>
          <p className="mt-0.5 text-xs text-muted">
            {formatNumber(followups.length)} message
            {followups.length === 1 ? "" : "s"} for this RFQ
            {awaiting > 0 ? ` · ${formatNumber(awaiting)} awaiting your approval` : ""}
          </p>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {STATUS_FILTERS.map((filter) => (
            <button
              key={filter.value}
              type="button"
              onClick={() => setStatusFilter(filter.value)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                statusFilter === filter.value
                  ? "bg-primary-soft text-primary-soft-fg"
                  : "bg-surface-2 text-muted hover:text-content"
              }`}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </Card>

      {error && !followups.length ? (
        <Card className="p-6">
          <p className="text-sm text-danger">{error}</p>
        </Card>
      ) : (
        <FollowUpList
          followups={visible}
          loading={loading}
          onChanged={refresh}
          emptyTitle={
            statusFilter === "all"
              ? "No messages yet"
              : "Nothing with that status"
          }
          emptyDescription={
            statusFilter === "all"
              ? "Reminders and chase emails appear here as soon as the workspace drafts them — nothing is sent until you approve it."
              : "Try another filter to see the rest of the log."
          }
        />
      )}
    </div>
  );
}

export default FollowUpsTab;
