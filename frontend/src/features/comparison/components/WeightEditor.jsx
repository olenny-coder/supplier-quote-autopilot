import { useEffect, useState } from "react";

import { Button, Card } from "@/shared/components/ui";
import { formatNumber, formatPercent } from "@/shared/lib/format";

/**
 * Weights editor for the scoring engine.
 *
 * The seven criteria are edited on a 0–100 scale (what a buyer reasons about),
 * then normalised to fractions summing to 1.0 before they are POSTed — which is
 * exactly what `comparison.weights` returns, so the sliders can be re-seeded
 * from the server's own normalised values after a re-run.
 */

//: Mirrors the backend's DEFAULT_WEIGHTS (comparison/schemas.py).
const DEFAULT_WEIGHTS = {
  price: 0.45,
  lead_time: 0.2,
  payment_terms: 0.1,
  moq: 0.05,
  validity: 0.05,
  warranty: 0.05,
  risk: 0.1,
};

const CRITERIA = [
  { key: "price", label: "Price", hint: "Landed cost after FX and Incoterms" },
  { key: "lead_time", label: "Lead time", hint: "Days to deliver" },
  { key: "payment_terms", label: "Payment terms", hint: "Credit granted to you" },
  { key: "moq", label: "MOQ", hint: "Fit against the requested quantity" },
  { key: "validity", label: "Validity", hint: "How long the price holds" },
  { key: "warranty", label: "Warranty", hint: "Months of coverage" },
  { key: "risk", label: "Supplier risk", hint: "Your rating of the supplier" },
];

/** Fractions -> a 0–100 draft. Missing criteria fall back to the defaults. */
function toDraft(weights) {
  const source = weights && Object.keys(weights).length ? weights : DEFAULT_WEIGHTS;

  return CRITERIA.reduce((draft, criterion) => {
    const value = source[criterion.key] ?? DEFAULT_WEIGHTS[criterion.key];

    draft[criterion.key] = Math.round(Number(value) * 100);

    return draft;
  }, {});
}

function WeightEditor({ weights, busy = false, onApply }) {
  const [draft, setDraft] = useState(() => toDraft(weights));
  const [syncedFrom, setSyncedFrom] = useState(() => JSON.stringify(weights || {}));

  // Re-seed the sliders when the *server's* weights change (a re-run normalises
  // them), but never while the buyer is mid-edit on an unrelated re-render.
  useEffect(() => {
    const incoming = JSON.stringify(weights || {});

    if (incoming !== syncedFrom) {
      setDraft(toDraft(weights));
      setSyncedFrom(incoming);
    }
  }, [weights, syncedFrom]);

  const total = CRITERIA.reduce((sum, criterion) => sum + draft[criterion.key], 0);

  const setWeight = (key, value) => {
    const parsed = Number(value);

    setDraft((prev) => ({
      ...prev,
      [key]: Number.isFinite(parsed) ? Math.max(0, Math.min(100, parsed)) : 0,
    }));
  };

  const handleReset = () => {
    // Only the sliders move — the buyer still has to press "Re-run" so that a
    // reset never silently re-scores and re-writes the stored recommendation.
    setDraft(toDraft(DEFAULT_WEIGHTS));
  };

  const handleApply = () => {
    if (total <= 0) return;

    const fractions = CRITERIA.reduce((payload, criterion) => {
      // Normalise here so the numbers the buyer sees are the numbers that score.
      payload[criterion.key] = draft[criterion.key] / total;

      return payload;
    }, {});

    onApply?.(fractions);
  };

  return (
    <Card className="flex flex-col gap-5 p-5">
      <div>
        <h3 className="text-sm font-semibold text-content">
          Scoring weights
        </h3>
        <p className="mt-1 text-xs leading-relaxed text-muted">
          Percentages show the normalised share each criterion carries. Change
          them and re-run to see how the recommendation moves.
        </p>
      </div>

      <div className="space-y-4">
        {CRITERIA.map((criterion) => {
          const value = draft[criterion.key];
          const share = total > 0 ? value / total : 0;

          return (
            <div key={criterion.key}>
              <div className="flex items-center justify-between gap-3">
                <label
                  htmlFor={`weight-${criterion.key}`}
                  className="text-sm font-medium text-content"
                >
                  {criterion.label}
                </label>

                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-primary-soft-fg">
                    {formatPercent(share)}
                  </span>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={value}
                    onChange={(event) => setWeight(criterion.key, event.target.value)}
                    aria-label={`${criterion.label} weight`}
                    className="w-16 rounded-lg border border-border-default bg-surface-inset px-2 py-1 text-right text-xs text-content focus:border-primary focus:outline-none focus:ring-2 focus:ring-ring/50"
                  />
                </div>
              </div>

              <input
                id={`weight-${criterion.key}`}
                type="range"
                min="0"
                max="100"
                step="5"
                value={value}
                onChange={(event) => setWeight(criterion.key, event.target.value)}
                className="mt-2 w-full accent-primary"
              />

              <p className="mt-1 text-[11px] text-subtle">{criterion.hint}</p>
            </div>
          );
        })}
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-border-default pt-4">
        <p className="text-xs text-muted">
          Raw total {formatNumber(total)} · normalised to 100%
        </p>

        <Button variant="ghost" size="sm" onClick={handleReset} disabled={busy}>
          Reset to defaults
        </Button>
      </div>

      {total <= 0 && (
        <p className="text-xs font-medium text-danger">
          Give at least one criterion a weight above zero before re-running.
        </p>
      )}

      <Button
        onClick={handleApply}
        loading={busy}
        loadingText="Scoring quotes…"
        disabled={total <= 0}
      >
        Re-run comparison with these weights
      </Button>
    </Card>
  );
}

export default WeightEditor;
