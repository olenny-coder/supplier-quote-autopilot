import { Link } from "react-router-dom";

import EmptyState from "@/shared/components/EmptyState";
import { SkeletonCard } from "@/shared/components/Loading";
import { Button } from "@/shared/components/ui";
import { buttonClass } from "@/shared/lib/button";
import { formatNumber } from "@/shared/lib/format";

import { useAuth } from "@/features/auth/useAuth";

import ClosingSoonPanel from "../components/ClosingSoonPanel";
import DashboardStats from "../components/DashboardStats";
import NeedsAttentionPanel from "../components/NeedsAttentionPanel";
import { useDashboardSummary } from "../hooks";

/**
 * The buyer's landing page.
 *
 * Everything on it comes from the single `GET /dashboard/summary` call, so the
 * page has exactly one loading state and one error state. The two banners make
 * the platform's guardrails visible rather than implicit: follow-ups are queued
 * for a human, and if AI drafting is unavailable the reminder copy is the
 * deterministic template instead.
 */
function DashboardPage() {
  const { user } = useAuth();
  const { summary, loading, error, refresh } = useDashboardSummary();

  if (loading && !summary) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-56 animate-pulse rounded-lg bg-surface-2" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <SkeletonCard key={index} />
          ))}
        </div>
      </div>
    );
  }

  if (error && !summary) {
    return (
      <EmptyState
        title="Could not load your dashboard"
        description={error}
        action={<Button onClick={refresh}>Try again</Button>}
      />
    );
  }

  if (!summary) {
    return null;
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-content sm:text-3xl">
            Dashboard
          </h1>
          <p className="mt-2 text-muted">
            {user?.company_name
              ? `${user.company_name} — RFQs, supplier responses and award decisions in one place.`
              : "RFQs, supplier responses and award decisions in one place."}
          </p>
        </div>

        <div className="flex shrink-0 gap-2">
          <Link to="/rfqs" className={buttonClass("outline", "sm")}>
            All RFQs
          </Link>

          <Link to="/rfqs/new" className={buttonClass("primary", "sm")}>
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14m-7-7h14" />
            </svg>
            Create RFQ
          </Link>
        </div>
      </header>

      {/* Guardrail: nothing is emailed to a supplier without a human approval. */}
      {summary.auto_send_followups === false && (
        <div className="flex flex-col gap-3 rounded-2xl border border-warning-soft-fg/25 bg-warning-soft px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <svg
              className="mt-0.5 h-5 w-5 shrink-0 text-warning-soft-fg"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m0 3.75h.008M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <div>
              <p className="text-sm font-semibold text-warning-soft-fg">
                Reminders are queued for your approval
              </p>
              <p className="mt-1 text-sm text-warning-soft-fg/90">
                Automatic sending is switched off. Every chase email is drafted
                for you and waits in the approval queue
                {summary.followups_pending_approval > 0
                  ? ` — ${formatNumber(summary.followups_pending_approval)} waiting now.`
                  : "."}
              </p>
            </div>
          </div>

          <Link to="/follow-ups" className={buttonClass("outline", "sm")}>
            Review queue
          </Link>
        </div>
      )}

      {/* Guardrail context: the fallback is deterministic, not broken. */}
      {summary.ai_available === false && (
        <p className="flex items-center gap-2 text-xs text-subtle">
          <svg
            className="h-3.5 w-3.5 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"
            />
          </svg>
          AI drafting is off — reminders and summaries use the built-in
          deterministic templates.
        </p>
      )}

      <DashboardStats summary={summary} />

      <div className="grid gap-5 lg:grid-cols-2">
        <ClosingSoonPanel deadlines={summary.deadlines_soon} />
        <NeedsAttentionPanel items={summary.needs_attention} />
      </div>
    </div>
  );
}

export default DashboardPage;
