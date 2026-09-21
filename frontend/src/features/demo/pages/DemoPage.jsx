import { Link } from "react-router-dom";
import { toast } from "sonner";

import EmptyState from "@/shared/components/EmptyState";
import Loading from "@/shared/components/Loading";
import { Button } from "@/shared/components/ui";
import { buttonClass } from "@/shared/lib/button";
import { formatDateTime } from "@/shared/lib/format";

import ComparisonTable from "@/features/comparison/components/ComparisonTable";
import QuoteTable from "@/features/quote/components/QuoteTable";

import DemoBanner from "../components/DemoBanner";
import DemoFollowUpList from "../components/DemoFollowUpList";
import DemoInvitationList from "../components/DemoInvitationList";
import DemoSection from "../components/DemoSection";
import DemoSummaryStrip from "../components/DemoSummaryStrip";
import { useDemoWorkspace } from "../hooks";

/**
 * The public demo page — a guided tour of one complete tender, for a visitor with
 * no account.
 *
 * Three rules shape everything below.
 *
 * 1. **One request.** `useDemoWorkspace` calls `GET /demo/workspace` and nothing
 *    else. The payload carries the taxonomy, so the comparison table is handed
 *    its criteria through the `meta` prop instead of fetching `/meta/options` on
 *    its own. That matters beyond tidiness: the demo endpoint is the only route
 *    the backend exposes to an anonymous caller, and a signed-out visitor must
 *    never be the cause of a request to an authenticated one.
 *
 * 2. **Nothing looks clickable that is not.** The page composes the real
 *    presentational components — that is the point, a visitor should see the
 *    product rather than a screenshot of it — so the ones that normally carry
 *    actions are given their read-only mode: `QuoteTable` is rendered with
 *    `readOnly`, which drops its Edit/Delete column rather than leaving two dead
 *    buttons on the screen.
 *
 * 3. **It explains itself.** This is not a JSON dump. Each section says what it
 *    is and why it exists, in the order a buyer would meet it: what was asked
 *    for, what came back, how it was ranked, who was chased, and who was asked.
 *
 * `initialWorkspace` exists so the page can be rendered without the network (the
 * SSR render check); the `/demo` route never passes it.
 */

const DEMO_ACTION_MESSAGE =
  "This is a read-only demo — nothing was changed and no email was sent.";

/** The one line every visitor gets when they reach for a control that is off. */
const demoNotice = () => toast(DEMO_ACTION_MESSAGE);

/**
 * The taxonomy the comparison table is handed when the payload has none. An empty
 * object is passed rather than `undefined` on purpose: `ComparisonTable` reads a
 * falsy `meta` prop as "fetch it yourself", and a payload that arrived without its
 * `meta` block must not turn an anonymous page view into a request to
 * `/meta/options`. The table degrades — criteria fall back to their raw keys —
 * which is the right trade for a public page.
 */
const NO_TAXONOMY = Object.freeze({});

function DemoTopBar() {
  return (
    <header className="border-b border-border-default bg-surface">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4 sm:px-6">
        <Link to="/demo" className="flex min-w-0 items-center gap-2.5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-linear-to-br from-primary to-violet-500 shadow-lg shadow-primary/25">
            <svg
              className="h-5 w-5 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.2}
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
              />
            </svg>
          </span>
          <span className="flex min-w-0 flex-col leading-none">
            <span className="truncate text-sm font-semibold tracking-tight text-content">
              Supplier Quote Autopilot
            </span>
            <span className="mt-1 hidden text-[11px] font-medium text-subtle sm:block">
              Public demo workspace
            </span>
          </span>
        </Link>

        <div className="flex items-center gap-2">
          <Link
            to="/login"
            className={`${buttonClass("ghost", "lg")} hidden sm:inline-flex`}
          >
            Sign in
          </Link>

          <Link to="/register" className={buttonClass("primary", "lg")}>
            Create your workspace
          </Link>
        </div>
      </div>
    </header>
  );
}

function DemoHero({ payload }) {
  return (
    <div className="max-w-3xl">
      <span className="inline-flex items-center gap-1.5 rounded-full bg-primary-soft px-3 py-1 text-xs font-medium text-primary-soft-fg">
        <span className="h-1.5 w-1.5 rounded-full bg-primary" />
        Live sample workspace
      </span>

      <h1 className="mt-4 text-2xl font-bold tracking-tight text-content sm:text-3xl lg:text-4xl">
        One tender, scored end to end — no account required.
      </h1>

      <p className="mt-3 text-sm leading-relaxed text-muted sm:text-base">
        Below is a complete RFQ from{" "}
        <span className="font-medium text-content">
          {payload?.buyer_label || "a sample buyer"}
        </span>
        : the quotes that came back, the chasers the agent drafted, and the ranked
        comparison the scoring engine produced. The suppliers and the prices are
        invented; the engine that ranks them is the one you would be using.
      </p>

      <div className="mt-5 flex flex-col gap-3 rounded-2xl border border-warning-soft bg-warning-soft px-4 py-3.5 sm:flex-row sm:items-start">
        <svg
          className="mt-0.5 h-4 w-4 shrink-0 text-warning-soft-fg"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"
          />
        </svg>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-warning-soft-fg">
            Sample data
          </p>
          {/* Served by the API, never written here: the page and the endpoint
              cannot drift into disagreeing about what the demo does. */}
          <p className="mt-1 text-sm leading-relaxed text-warning-soft-fg">
            {payload?.disclaimer}
          </p>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Link to="/register" className={buttonClass("primary", "lg")}>
          Create your workspace
        </Link>

        <Link to="/login" className={`${buttonClass("outline", "lg")} sm:hidden`}>
          Sign in
        </Link>

        {payload?.generated_at && (
          <span className="text-xs text-subtle">
            Snapshotted {formatDateTime(payload.generated_at)}
          </span>
        )}
      </div>
    </div>
  );
}

function DemoErrorMessage({ message, onRetry }) {
  return (
    <div className="rounded-2xl border border-danger/30 bg-danger-soft px-5 py-4">
      <p className="text-sm font-semibold text-danger-soft-fg">
        The sample workspace could not be loaded.
      </p>
      <p className="mt-1 text-sm leading-relaxed text-danger-soft-fg">{message}</p>

      <div className="mt-4 flex flex-wrap gap-3">
        <Button variant="outline" onClick={onRetry}>
          Try again
        </Button>

        <Link to="/register" className={buttonClass("primary", "md")}>
          Create your workspace
        </Link>
      </div>
    </div>
  );
}

/** The closing call to action, repeated because the page is long. */
function DemoCallToAction({ buyerLabel }) {
  return (
    <div className="rounded-2xl border border-border-default bg-surface bg-linear-to-br from-primary/10 via-transparent to-violet-500/10 p-6 text-center sm:p-10">
      <h2 className="text-xl font-semibold tracking-tight text-content sm:text-2xl">
        Run this on your own RFQ
      </h2>

      <p className="mx-auto mt-2 max-w-xl text-sm leading-relaxed text-muted">
        Create a workspace, invite your contractors with a private form link, and
        let the engine do the arithmetic.{" "}
        {buyerLabel ? `${buyerLabel} is invented — yours would be private.` : ""}
      </p>

      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        <Link to="/register" className={buttonClass("primary", "lg")}>
          Create your workspace
        </Link>

        <Link to="/login" className={buttonClass("outline", "lg")}>
          Sign in
        </Link>
      </div>
    </div>
  );
}

/**
 * One sample RFQ and everything that hangs off it.
 *
 * `meta` is passed straight through to the comparison table so the criteria are
 * named from the payload rather than from a second request.
 */
function DemoWorkspace({ workspace, meta }) {
  const rfq = workspace.rfq;
  const comparison = workspace.comparison;
  const quotes = workspace.quotes || [];
  const invitations = workspace.invitations || [];
  const followups = workspace.followups || [];

  // The criteria count comes from the payload's taxonomy, like everything else on
  // this page: a tenth criterion added to the backend appears in the copy as well
  // as in the table.
  const criteriaCount = (meta?.criteria || []).length;

  return (
    <div className="space-y-12">
      <DemoSection
        step="1"
        title="What the buyer asked for"
        description="One RFQ, one rate basis, one SLA and a short list of licences the work legally needs. This is the contract the rest of the page is measured against."
      >
        <DemoSummaryStrip rfq={rfq} />
      </DemoSection>

      <DemoSection
        step="2"
        title={
          criteriaCount
            ? `The comparison — ${criteriaCount} criteria, one ranking`
            : "The comparison — one ranking, every criterion"
        }
        description="The centrepiece: weighted criteria, not one number. Price carries the most weight, but a quote missing a licence this RFQ requires is capped and its shortfall named rather than quietly dropped — which is why the ranking and the rate column do not have to agree. The callout charge is added separately from the rate, and a GST figure the engine had to derive from a stated rate is labelled as derived rather than quoted."
        aside={
          <span className="inline-flex shrink-0 items-center gap-1.5 self-start rounded-full bg-success-soft px-3 py-1 text-xs font-medium text-success-soft-fg">
            Recommended:{" "}
            {comparison?.recommended_supplier || "not decided yet"}
          </span>
        }
      >
        {comparison ? (
          <ComparisonTable comparison={comparison} meta={meta} />
        ) : (
          <EmptyState
            title="No comparison has been run"
            description="A ranking appears here once at least one complete, priced quote has been scored."
          />
        )}
      </DemoSection>

      <DemoSection
        step="3"
        title="Every quote, side by side"
        description={`${quotes.length} ${quotes.length === 1 ? "quote" : "quotes"} as the buyer sees them: rate, rate basis, response time, callout charge and the total normalised into one currency. Edit and delete are switched off on this page — the sample data is not yours to change, and nothing here is saved anyway.`}
      >
        <QuoteTable
          quotes={quotes}
          procurementType={rfq?.procurement_type}
          requiredAccreditations={rfq?.required_accreditations || []}
          readOnly
          // Handlers are still passed so that if a future change ever renders the
          // controls again, clicking one explains itself instead of silently
          // doing nothing. In `readOnly` mode neither control is rendered.
          onEdit={demoNotice}
          onDelete={demoNotice}
        />
      </DemoSection>

      <DemoSection
        step="4"
        title="It chases only what is missing"
        description="When a quote arrives incomplete, the agent does not send a generic reminder. It names the fields it still needs — in the supplier's own vocabulary — and stops there, and every draft waits for the buyer's approval before it goes anywhere."
      >
        <DemoFollowUpList followups={followups} />
      </DemoSection>

      <DemoSection
        step="5"
        title="Who was asked"
        description="Contractors never need an account: each one receives a private link, and the buyer can see whether it has been opened."
      >
        <DemoInvitationList invitations={invitations} />
      </DemoSection>
    </div>
  );
}

function DemoPage({ initialWorkspace = null }) {
  const { workspace, loading, error, reload } = useDemoWorkspace({
    initial: initialWorkspace,
  });

  // An entry without an RFQ is not a workspace; filtering it out keeps a malformed
  // payload from rendering an empty shell of headings.
  const workspaces = (workspace?.workspaces || []).filter((entry) => entry?.rfq);

  return (
    <div className="theme-transition flex min-h-screen flex-col text-content">
      <DemoTopBar />
      <DemoBanner />

      <main className="mx-auto w-full max-w-7xl flex-1 px-5 py-8 sm:px-6 lg:py-12">
        {loading && <Loading message="Loading the sample workspace…" />}

        {!loading && error && (
          <DemoErrorMessage message={error} onRetry={reload} />
        )}

        {!loading && !error && (
          <div className="space-y-12">
            <DemoHero payload={workspace} />

            {workspaces.length === 0 ? (
              <EmptyState
                title="No sample workspace is available"
                description="This deployment has no demo snapshot to show. You can still create a workspace of your own — it takes a minute."
                action={
                  <Link to="/register" className={buttonClass("primary", "lg")}>
                    Create your workspace
                  </Link>
                }
              />
            ) : (
              workspaces.map((entry, index) => (
                <DemoWorkspace
                  key={entry?.rfq?.id ?? index}
                  workspace={entry}
                  meta={workspace?.meta || NO_TAXONOMY}
                />
              ))
            )}

            <DemoCallToAction buyerLabel={workspace?.buyer_label} />
          </div>
        )}
      </main>

      <footer className="border-t border-border-default/70">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 px-6 py-5 text-xs text-subtle sm:flex-row">
          <span>Supplier Quote Autopilot</span>
          <span>Award decisions always stay with a human buyer.</span>
        </div>
      </footer>
    </div>
  );
}

export default DemoPage;
