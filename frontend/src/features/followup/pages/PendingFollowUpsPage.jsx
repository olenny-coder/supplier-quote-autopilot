import { Button } from "@/shared/components/ui";

import FollowUpList from "../components/FollowUpList";
import { usePendingFollowUps } from "../hooks";

/**
 * The buyer's approval queue: every follow-up the backend drafted across the
 * workspace, waiting for a human decision before anything is emailed.
 */
function PendingFollowUpsPage() {
  const { followups, loading, error, refresh } = usePendingFollowUps();

  const aiDraftedCount = followups.filter((followup) => followup.llm_generated).length;

  return (
    <div className="space-y-8">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-content sm:text-3xl">
              Follow-ups awaiting approval
            </h1>
            {followups.length > 0 && (
              <span className="rounded-full bg-surface-2 px-2.5 py-0.5 text-sm font-semibold text-muted">
                {followups.length}
              </span>
            )}
          </div>

          <p className="mt-2 text-muted">
            These reminders were drafted automatically for suppliers who went
            quiet, left a quote incomplete, or are running out of time. Nothing
            is emailed until you approve it.
          </p>
        </div>

        <Button variant="outline" size="sm" loading={loading} onClick={refresh}>
          {!loading && (
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
                d="M4 4v6h6M20 20v-6h-6M20 9A8 8 0 006.3 5.7L4 8m16 8l-2.3 2.3A8 8 0 014 15"
              />
            </svg>
          )}
          Refresh
        </Button>
      </div>

      {aiDraftedCount > 0 && (
        <div className="flex gap-3 rounded-2xl bg-warning-soft px-5 py-4 text-warning-soft-fg">
          <svg
            className="mt-0.5 h-5 w-5 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m0 3.75h.008M12 3l9 16.5H3L12 3z"
            />
          </svg>
          <p className="text-sm leading-relaxed">
            {aiDraftedCount} of these drafts were written by the AI assistant —
            review before sending.
          </p>
        </div>
      )}

      {error && (
        <div className="flex flex-col justify-between gap-4 rounded-2xl bg-danger-soft px-5 py-4 sm:flex-row sm:items-center">
          <div>
            <p className="text-sm font-semibold text-danger-soft-fg">
              Could not load the approval queue
            </p>
            <p className="mt-0.5 text-sm text-danger-soft-fg">{error}</p>
          </div>

          <Button variant="outline" size="sm" onClick={refresh}>
            Try again
          </Button>
        </div>
      )}

      {(!error || followups.length > 0) && (
        <FollowUpList
          followups={followups}
          loading={loading}
          onChanged={refresh}
          emptyTitle="No follow-ups waiting"
          emptyDescription="Every reminder has been approved or discarded. New drafts appear here as soon as the assistant writes them."
        />
      )}
    </div>
  );
}

export default PendingFollowUpsPage;
