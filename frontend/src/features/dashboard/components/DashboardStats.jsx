import { Link } from "react-router-dom";

import { Card } from "@/shared/components/ui";
import { formatNumber } from "@/shared/lib/format";

/**
 * The six headline counters from `GET /dashboard/summary`.
 *
 * Defined as data rather than six bespoke blocks: adding a counter is one entry
 * here, and every card keeps the same number/format/hint rhythm.
 */
const CARD_DEFINITIONS = [
  {
    key: "rfqs_open",
    label: "Open RFQs",
    hint: (summary) => `${formatNumber(summary.rfqs_total)} in total`,
    tone: "primary",
    action: { label: "View RFQs", to: "/rfqs" },
  },
  {
    key: "rfqs_awaiting_approval",
    label: "Awaiting your approval",
    hint: (summary) =>
      `${formatNumber(summary.followups_pending_approval)} follow-up draft${
        summary.followups_pending_approval === 1 ? "" : "s"
      } queued`,
    tone: "warning",
    // The queue is where the buyer clears everything that is waiting on them.
    action: { label: "Open approval queue", to: "/follow-ups" },
  },
  {
    key: "suppliers_total",
    label: "Suppliers",
    hint: () => "In your directory",
    tone: "neutral",
    action: { label: "Manage suppliers", to: "/suppliers" },
  },
  {
    key: "quotes_total",
    label: "Quotes received",
    hint: (summary) =>
      `${formatNumber(summary.quotes_complete)} complete`,
    tone: "success",
    action: { label: "Compare quotes", to: "/rfqs" },
  },
  {
    key: "invitations_pending",
    label: "Pending responses",
    hint: (summary) =>
      `of ${formatNumber(summary.invitations_total)} invitation${
        summary.invitations_total === 1 ? "" : "s"
      } sent`,
    tone: "neutral",
    action: { label: "Chase suppliers", to: "/rfqs" },
  },
  {
    key: "invitations_incomplete",
    label: "Incomplete quotes",
    hint: () => "Missing required fields",
    tone: "danger",
    action: { label: "Follow up", to: "/rfqs" },
  },
];

//: Accent per tone. Semantic tokens only, so light/dark both work.
const TONE_CLASSES = {
  primary: "bg-primary-soft text-primary-soft-fg",
  success: "bg-success-soft text-success-soft-fg",
  warning: "bg-warning-soft text-warning-soft-fg",
  danger: "bg-danger-soft text-danger-soft-fg",
  neutral: "bg-surface-2 text-muted",
};

function DashboardStats({ summary }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {CARD_DEFINITIONS.map((definition) => {
        const value = formatNumber(summary[definition.key] ?? 0);

        return (
          <Card key={definition.key} className="flex flex-col gap-4 p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-medium uppercase tracking-wider text-subtle">
                  {definition.label}
                </p>
                <p className="mt-2 text-3xl font-bold tracking-tight text-content">
                  {value}
                </p>
              </div>

              <span
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
                  TONE_CLASSES[definition.tone]
                }`}
                aria-hidden="true"
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
                    d="M3 13.5l4.5-4.5 3.75 3.75L21 6m0 0h-4.5M21 6v4.5"
                  />
                </svg>
              </span>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border-default pt-3">
              <p className="text-xs text-muted">{definition.hint(summary)}</p>

              {definition.action && (
                <Link
                  to={definition.action.to}
                  className="text-xs font-medium text-primary transition hover:underline"
                >
                  {definition.action.label} →
                </Link>
              )}
            </div>
          </Card>
        );
      })}
    </div>
  );
}

export default DashboardStats;
