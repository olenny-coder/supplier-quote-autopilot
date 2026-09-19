import { useState } from "react";

import { toast } from "sonner";

import EmptyState from "@/shared/components/EmptyState";
import Loading from "@/shared/components/Loading";
import { Badge, Button, Card } from "@/shared/components/ui";
import { formatDateTime, formatNumber } from "@/shared/lib/format";

import { downloadComparisonCsv } from "../api";
import { useApprovals, useComparison } from "../hooks";
import ApprovalPanel from "./ApprovalPanel";
import ComparisonTable from "./ComparisonTable";
import RecommendationPanel from "./RecommendationPanel";
import WeightEditor from "./WeightEditor";

/**
 * Tab 3 — Comparison: the ranking, the reasoning, the weights and the award.
 *
 * The snapshot itself arrives with the RFQ overview, so opening this tab costs
 * no request. Requests happen only on demand: re-running the engine with new
 * weights, exporting the CSV, or recording a decision. Exports are fetched as
 * blobs through the authenticated axios client because a plain link would not
 * carry the bearer token.
 */
function ComparisonTab({ rfqId, comparison: initialComparison, quoteCount = 0, onChanged }) {
  const { comparison, busy, compute, error } = useComparison(rfqId, initialComparison);
  const { approvals, refresh: refreshApprovals } = useApprovals(rfqId, {
    // Only worth a request once a decision exists to show a trail for.
    enabled: Boolean(initialComparison?.approval),
  });

  const [exporting, setExporting] = useState(false);

  const handleRun = async (weights) => {
    const snapshot = await compute({ weights, useLlm: false });

    if (snapshot) {
      toast.success(
        snapshot.recommended_supplier
          ? `Comparison updated — ${snapshot.recommended_supplier} leads the ranking.`
          : "Comparison updated, but no supplier could be ranked."
      );

      await onChanged?.();
    }
  };

  const handleExportCsv = async () => {
    try {
      setExporting(true);

      await downloadComparisonCsv(rfqId);

      toast.success("Comparison CSV downloaded.");
    } catch (err) {
      toast.error(err.message);
    } finally {
      setExporting(false);
    }
  };

  const handlePrint = () => {
    // The print stylesheet in index.css hides the chrome, buttons and the chat
    // widget, leaving the table and the recommendation on the page.
    window.print();
  };

  if (!comparison) {
    return (
      <EmptyState
        title="No comparison yet"
        description={
          quoteCount > 0
            ? "Score the quotes you have received to get a ranked, normalised table and a recommendation."
            : "Once a supplier submits a quote, you can score and compare them here."
        }
        action={
          <Button
            onClick={() => handleRun(undefined)}
            loading={busy}
            loadingText="Scoring quotes…"
            disabled={quoteCount === 0}
          >
            Run comparison
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-5">
      <Card
        data-print="hide"
        className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-content">
              Quote comparison
            </h2>
            {comparison.is_current ? (
              <Badge variant="primary">Current</Badge>
            ) : (
              <Badge variant="warning">Superseded</Badge>
            )}
            {comparison.awaiting_approval && (
              <Badge variant="warning">Awaiting approval</Badge>
            )}
            {/* Which field set is being scored: a service snapshot weights the
                SLA and accreditations, a goods one weights lead time and MOQ. */}
            <Badge variant="neutral">
              {comparison.procurement_type === "goods" ? "Goods" : "Service"}
            </Badge>
          </div>

          <p className="mt-1 text-xs text-muted">
            {formatNumber(comparison.results?.length || 0)} quote
            {comparison.results?.length === 1 ? "" : "s"} scored ·{" "}
            {formatDateTime(comparison.created_at)}
            {comparison.llm_model ? ` · narrative by ${comparison.llm_model}` : ""}
          </p>

          {comparison.required_accreditations?.length > 0 && (
            <p className="mt-1 text-xs text-danger">
              Required licences: {comparison.required_accreditations.join(", ")}
            </p>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => handleRun(comparison.weights)}
            loading={busy}
            loadingText="Scoring…"
          >
            Re-run
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={handleExportCsv}
            loading={exporting}
            loadingText="Exporting…"
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
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
            Export CSV
          </Button>

          <Button size="sm" variant="outline" onClick={handlePrint}>
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
                d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4H7v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"
              />
            </svg>
            Print / save as PDF
          </Button>
        </div>
      </Card>

      {error && (
        <Card className="px-5 py-4">
          <p className="text-sm text-danger">{error}</p>
        </Card>
      )}

      <ComparisonTable comparison={comparison} />

      <div className="grid gap-5 lg:grid-cols-2">
        <RecommendationPanel comparison={comparison} />

        <WeightEditor
          weights={comparison.weights}
          procurementType={comparison.procurement_type || ""}
          busy={busy}
          onApply={(weights) => handleRun(weights)}
        />
      </div>

      <ApprovalPanel
        rfqId={rfqId}
        comparison={comparison}
        approvals={approvals}
        onApproved={async () => {
          await refreshApprovals();
          await onChanged?.();
        }}
      />

      {busy && (
        <Loading message="Re-scoring the quotes…" />
      )}
    </div>
  );
}

export default ComparisonTab;
