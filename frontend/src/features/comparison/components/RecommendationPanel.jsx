import { Fragment } from "react";

import { Badge, Card } from "@/shared/components/ui";
import { formatDateTime } from "@/shared/lib/format";

/**
 * The recommendation headline, the reasoning behind it, and the caveats.
 *
 * `rationale` is plain text that may contain `**bold**` markers and newlines.
 * Rather than pull in a markdown renderer for two features, `RichText` below
 * splits on newlines into paragraphs and turns `**…**` into `<strong>` — enough
 * for the copy the engine and the LLM produce, with no new dependency.
 */

/** Split a line on `**bold**` markers and wrap the emphasised runs. */
function renderEmphasis(line, lineIndex) {
  const parts = String(line).split(/(\*\*[^*]+\*\*)/g);

  return parts.map((part, index) => {
    const isBold = part.startsWith("**") && part.endsWith("**") && part.length > 4;

    return isBold ? (
      <strong
        key={`${lineIndex}-${index}`}
        className="font-semibold text-content"
      >
        {part.slice(2, -2)}
      </strong>
    ) : (
      <Fragment key={`${lineIndex}-${index}`}>{part}</Fragment>
    );
  });
}

function RichText({ text }) {
  if (!text) return null;

  const paragraphs = String(text)
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean);

  return (
    <div className="space-y-2.5">
      {paragraphs.map((paragraph, index) => (
        <p key={index} className="text-sm leading-relaxed text-muted">
          {renderEmphasis(paragraph, index)}
        </p>
      ))}
    </div>
  );
}

function RecommendationPanel({ comparison }) {
  if (!comparison) return null;

  const hasRecommendation = Boolean(comparison.recommended_quote_id);
  const aiGenerated = Boolean(comparison.llm_model);

  return (
    <Card className="flex flex-col gap-5 p-5">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={comparison.is_conclusive ? "success" : "warning"}>
            {comparison.is_conclusive ? "Ranking conclusive" : "Ranking inconclusive"}
          </Badge>
          {comparison.is_current && <Badge variant="primary">Current snapshot</Badge>}
          {comparison.awaiting_approval && (
            <Badge variant="warning">Awaiting your decision</Badge>
          )}
        </div>

        <h3 className="mt-3 text-lg font-semibold tracking-tight text-content">
          {hasRecommendation
            ? `Recommended: ${comparison.recommended_supplier}`
            : "No recommendation yet"}
        </h3>

        <p className="mt-1 text-xs text-subtle">
          Scored by {comparison.computed_by || "the comparison engine"} ·{" "}
          {formatDateTime(comparison.created_at)}
          {aiGenerated ? ` · narrative by ${comparison.llm_model}` : ""}
        </p>
      </div>

      {comparison.summary && (
        <div className="rounded-xl border border-border-default bg-surface-2/60 p-4">
          <div className="mb-2 flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-subtle">
              Summary
            </span>
            {aiGenerated && (
              <Badge variant="primary">
                <svg
                  className="h-3 w-3"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path d="M10 1l1.9 5.1L17 8l-5.1 1.9L10 15l-1.9-5.1L3 8l5.1-1.9L10 1z" />
                </svg>
                AI-generated
              </Badge>
            )}
          </div>

          <RichText text={comparison.summary} />
        </div>
      )}

      {comparison.rationale && (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-subtle">
            Why this ranking
          </h4>
          <RichText text={comparison.rationale} />
        </div>
      )}

      {comparison.warnings?.length > 0 && (
        <div className="rounded-xl border border-warning-soft-fg/25 bg-warning-soft p-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-warning-soft-fg">
            Warnings
          </h4>
          <ul className="mt-2 space-y-1.5">
            {comparison.warnings.map((warning) => (
              <li
                key={warning}
                className="text-sm leading-relaxed text-warning-soft-fg"
              >
                {warning}
              </li>
            ))}
          </ul>
        </div>
      )}

      {comparison.risks?.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-subtle">
            Risks to weigh
          </h4>
          <ul className="space-y-2">
            {comparison.risks.map((risk) => (
              <li key={risk} className="flex items-start gap-2.5">
                <span className="mt-1.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-danger-soft text-danger-soft-fg">
                  <svg
                    className="h-2.5 w-2.5"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v4a1 1 0 102 0V7zm-1 7a1 1 0 100 2 1 1 0 000-2z"
                      clipRule="evenodd"
                    />
                  </svg>
                </span>
                <span className="text-sm leading-relaxed text-muted">{risk}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!hasRecommendation && (
        <p className="text-sm leading-relaxed text-muted">
          The engine could not rank anyone — usually because no quote is complete
          enough to compare. Fill the gaps on the Suppliers tab and re-run.
        </p>
      )}
    </Card>
  );
}

export default RecommendationPanel;
