import { useEffect, useMemo, useRef } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import EmptyState from "@/shared/components/EmptyState";
import Loading from "@/shared/components/Loading";
import { Badge, Button } from "@/shared/components/ui";
import { buttonClass } from "@/shared/lib/button";
import {
  formatDateTime,
  formatHours,
  formatNumber,
  formatRateBasis,
  formatRelativeTime,
  toNumber,
} from "@/shared/lib/format";
import { StatusBadge } from "@/shared/components/StatusBadge";

import ComparisonTab from "@/features/comparison/components/ComparisonTab";

import FollowUpsTab from "../components/FollowUpsTab";
import InvitationsTab from "../components/InvitationsTab";
import QuotesTab from "../components/QuotesTab";
import RFQDetailsTab from "../components/RFQDetailsTab";
import { useRFQOverview } from "../hooks";

const TABS = [
  { key: "suppliers", label: "Suppliers & links" },
  { key: "quotes", label: "Quotes" },
  { key: "comparison", label: "Comparison" },
  { key: "followups", label: "Follow-ups" },
  { key: "details", label: "RFQ details" },
];

/**
 * The RFQ workbench.
 *
 * One `GET /rfqs/{id}/overview` call feeds all five tabs, so the page has a
 * single loading state and switching tabs never re-fetches. The active tab
 * lives in the URL (`?tab=quotes`) because the dashboard and the RFQ list
 * deep-link straight into a specific tab; `?invitation=` additionally
 * highlights the row a buyer came to chase.
 */
function RFQDetailsPage() {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const { overview, loading, error, refresh } = useRFQOverview(id);

  const tabParam = searchParams.get("tab");
  const activeTab = TABS.some((tab) => tab.key === tabParam) ? tabParam : "suppliers";
  const focusInvitationId = Number(searchParams.get("invitation")) || null;

  // Scroll the active tab into view whenever it changes. The strip is five tabs in
  // an `overflow-x-auto` row, so on a phone the third tab ("Comparison", where the
  // dashboard's "Compare quotes" button points) starts off-screen — the buyer
  // arrived at a panel with nothing indicating which section it was.
  const activeTabRef = useRef(null);

  useEffect(() => {
    activeTabRef.current?.scrollIntoView({
      inline: "center",
      block: "nearest",
      behavior: "smooth",
    });
  }, [activeTab]);

  const counts = useMemo(() => {
    if (!overview) return {};

    const awaiting = (overview.followups || []).filter((followup) =>
      ["draft", "queued"].includes(followup.status)
    ).length;

    return {
      suppliers: overview.invitations?.length || 0,
      quotes: overview.quotes?.length || 0,
      comparison: overview.comparison?.results?.length || 0,
      followups: awaiting,
    };
  }, [overview]);

  const selectTab = (key) => {
    const next = new URLSearchParams(searchParams);

    next.set("tab", key);
    // The invitation highlight only makes sense on the tab that lists them.
    if (key !== "suppliers") next.delete("invitation");

    setSearchParams(next, { replace: true });
  };

  if (loading && !overview) {
    return <Loading message="Loading RFQ…" />;
  }

  if (!overview) {
    return (
      <EmptyState
        title="RFQ not available"
        description={
          error || "This RFQ could not be loaded. It may have been deleted."
        }
        action={
          <div className="flex gap-3">
            <Button variant="outline" onClick={refresh}>
              Try again
            </Button>
            <Link to="/rfqs" className={buttonClass("primary", "md")}>
              Back to RFQs
            </Link>
          </div>
        }
      />
    );
  }

  const { rfq, invitations = [], quotes = [], followups = [], comparison } = overview;

  const deadline = rfq.deadline ? new Date(rfq.deadline) : null;
  const overdue = deadline ? deadline.getTime() < Date.now() : false;

  const isGoods = rfq.procurement_type === "goods";
  const responseHours = toNumber(rfq.required_response_hours);

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/rfqs"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-muted transition hover:text-content"
        >
          <svg
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Back to RFQs
        </Link>

        <div className="mt-4 flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="neutral">{rfq.rfq_number}</Badge>
              <StatusBadge status={rfq.status} domain="rfq" />
              <Badge variant={isGoods ? "neutral" : "primary"}>
                {isGoods ? "Goods" : "Service"}
              </Badge>
              {rfq.category && <Badge variant="neutral">{rfq.category}</Badge>}
              {!isGoods && responseHours !== null && (
                <Badge variant="warning">SLA {formatHours(responseHours)}</Badge>
              )}
              {rfq.ready_to_compare && (
                <Badge variant="success">Ready to compare</Badge>
              )}
              {deadline && (
                <Badge variant={overdue ? "danger" : "warning"}>
                  {overdue
                    ? `Deadline passed ${formatRelativeTime(rfq.deadline)}`
                    : `Closes ${formatRelativeTime(rfq.deadline)}`}
                </Badge>
              )}
            </div>

            <h1 className="mt-3 text-2xl font-bold tracking-tight text-content sm:text-3xl">
              {rfq.item_name}
            </h1>

            <p className="mt-2 text-sm text-muted">
              {rfq.specification} · {formatNumber(rfq.quantity)}{" "}
              {isGoods ? rfq.unit || "" : formatRateBasis(rfq.unit)} · quotes in{" "}
              {rfq.currency}
              {rfq.site_name ? ` · ${rfq.site_name}` : ""}
              {!isGoods ? ` · wanted by ${rfq.delivery_expectation}` : ""}
              {isGoods && rfq.incoterms ? ` · ${rfq.incoterms}` : ""}
              {rfq.deadline ? ` · deadline ${formatDateTime(rfq.deadline)}` : ""}
            </p>
          </div>

          <div className="flex shrink-0 flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={() => selectTab("suppliers")}>
              Invite suppliers
            </Button>
            <Button size="sm" variant="soft" onClick={() => selectTab("comparison")}>
              Compare
            </Button>
          </div>
        </div>

        {overview.capabilities?.auto_send_followups === false && (
          <p className="mt-3 text-xs text-subtle">
            Automatic sending is off — every reminder is drafted for you and waits
            in the approval queue.
          </p>
        )}
      </div>

      <div className="overflow-hidden rounded-2xl border border-border-default bg-surface shadow-card">
        <div
          data-print="hide"
          role="tablist"
          aria-label="RFQ sections"
          className="flex gap-1 overflow-x-auto border-b border-border-default bg-surface-2/60 p-2"
        >
          {TABS.map((tab) => {
            const isActive = tab.key === activeTab;
            const count = counts[tab.key];

            return (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => selectTab(tab.key)}
                // The active tab is scrolled into view on mount, because the row
                // is wider than a phone screen and the dashboard deep-links
                // straight to a middle tab. Landing on the comparison panel with
                // the highlighted tab off-screen left nothing on screen to say
                // which section was open.
                ref={isActive ? activeTabRef : undefined}
                className={`flex min-h-11 shrink-0 items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-medium transition ${
                  isActive
                    ? "bg-surface text-content shadow-sm"
                    : "text-muted hover:text-content"
                }`}
              >
                {tab.label}
                {count > 0 && (
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                      isActive
                        ? "bg-primary-soft text-primary-soft-fg"
                        : "bg-surface-2 text-subtle"
                    }`}
                  >
                    {formatNumber(count)}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <div className="p-5" role="tabpanel" aria-label={`${activeTab} section`}>
          {activeTab === "suppliers" && (
            <InvitationsTab
              rfqId={rfq.id}
              invitations={invitations}
              onChanged={refresh}
              focusInvitationId={focusInvitationId}
            />
          )}

          {activeTab === "quotes" && (
            <QuotesTab rfq={rfq} quotes={quotes} onChanged={refresh} />
          )}

          {activeTab === "comparison" && (
            <ComparisonTab
              rfqId={rfq.id}
              comparison={comparison}
              quoteCount={quotes.length}
              onChanged={refresh}
            />
          )}

          {activeTab === "followups" && <FollowUpsTab rfqId={rfq.id} />}

          {activeTab === "details" && (
            <RFQDetailsTab rfq={rfq} onChanged={refresh} />
          )}
        </div>
      </div>

      {followups.length > 0 && (
        <p className="text-xs text-subtle">
          {formatNumber(followups.length)} message
          {followups.length === 1 ? "" : "s"} logged against this RFQ — open the
          Follow-ups tab for the full trail.
        </p>
      )}
    </div>
  );
}

export default RFQDetailsPage;
