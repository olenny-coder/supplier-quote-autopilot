import { useEffect, useMemo, useState } from "react";

import { Button, Card } from "@/shared/components/ui";
import { formatFieldKey, formatNumber, formatPercent } from "@/shared/lib/format";

import { useMetaOptions } from "@/features/meta/hooks";

/**
 * Weights editor for the scoring engine.
 *
 * The nine criteria come from `GET /meta/options`, each with the buyer-facing
 * description the API writes for it — nothing here is a hard-coded list.
 * `response_time` and `compliance` are the two that exist because this is a
 * services product: a maintenance quote is differentiated less by a few dollars
 * than by how fast someone attends site and whether they are licensed to do the
 * work at all. If the engine ever grows a tenth criterion, this editor grows it.
 *
 * Defaults are per procurement type (`meta.default_weights[type]`, the RFQ's own
 * type), so "Reset to defaults" on a maintenance RFQ restores service weighting
 * — response time and accreditation at real weight, MOQ at zero — rather than the
 * goods weighting.
 *
 * The criteria are edited on a 0–100 scale (what a buyer reasons about), then
 * normalised to fractions summing to 1.0 before they are POSTed, which is exactly
 * what `comparison.weights` returns, so the sliders can be re-seeded from the
 * server's own normalised values after a re-run.
 */
function WeightEditor({ weights, procurementType = "", busy = false, onApply }) {
  const { options: meta, error: metaError } = useMetaOptions();

  // Identity is stable across renders (`meta` is the cached payload and
  // `comparison.weights` only changes when a new snapshot arrives), which keeps
  // the re-seed effect below from firing spuriously.
  const criteriaFromMeta = meta?.criteria;

  const criteria = useMemo(() => {
    if (criteriaFromMeta?.length) return criteriaFromMeta;

    // `/meta/options` failed. Rather than refuse to open, fall back to the keys
    // the stored snapshot actually carries — the buyer can still re-weight and
    // re-run, which is the whole point of the panel.
    return Object.keys(weights || {}).map((key) => ({
      key,
      label: formatFieldKey(key),
      description: "",
    }));
  }, [criteriaFromMeta, weights]);

  const defaults = useMemo(
    () =>
      meta?.default_weights?.[procurementType] ||
      // No meta: the snapshot's own weights are the only defensible fallback.
      weights ||
      {},
    [meta, procurementType, weights]
  );

  const [draft, setDraft] = useState(() => toDraft(weights, criteria, defaults));
  const [syncedWeights, setSyncedWeights] = useState(() => JSON.stringify(weights || {}));
  const [syncedCriteria, setSyncedCriteria] = useState(() =>
    criteria.map((criterion) => criterion.key).join("|")
  );

  // Re-seed the sliders when the *server's* weights change (a re-run normalises
  // them) or when the criteria list finally arrives, but never while the buyer is
  // mid-edit on an unrelated re-render.
  useEffect(() => {
    const incoming = JSON.stringify(weights || {});
    const criteriaKey = criteria.map((criterion) => criterion.key).join("|");

    if (incoming === syncedWeights && criteriaKey === syncedCriteria) return;

    setDraft(toDraft(weights, criteria, defaults));
    setSyncedWeights(incoming);
    setSyncedCriteria(criteriaKey);
  }, [weights, criteria, defaults, syncedWeights, syncedCriteria]);

  const total = criteria.reduce(
    (sum, criterion) => sum + (draft[criterion.key] ?? 0),
    0
  );

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
    setDraft(toDraft(null, criteria, defaults));
  };

  const handleApply = () => {
    if (total <= 0) return;

    const fractions = criteria.reduce((payload, criterion) => {
      // Normalise here so the numbers the buyer sees are the numbers that score.
      payload[criterion.key] = (draft[criterion.key] ?? 0) / total;

      return payload;
    }, {});

    onApply?.(fractions);
  };

  return (
    <Card className="flex flex-col gap-5 p-5">
      <div>
        <h3 className="text-sm font-semibold text-content">Scoring weights</h3>
        <p className="mt-1 text-xs leading-relaxed text-muted">
          Percentages show the normalised share each criterion carries. Change
          them and re-run to see how the recommendation moves. Defaults follow the
          RFQ&apos;s procurement type
          {procurementType ? ` (${procurementType})` : ""}.
        </p>
      </div>

      {metaError && (
        <p className="rounded-xl border border-warning-soft-fg/25 bg-warning-soft px-3 py-2 text-xs leading-relaxed text-warning-soft-fg">
          The criterion list could not be loaded ({metaError}), so the sliders fall
          back to the criteria in the current snapshot.
        </p>
      )}

      <div className="space-y-4">
        {criteria.map((criterion) => {
          const value = draft[criterion.key] ?? 0;
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

              {/* The engine's own explanation of what this criterion means, in the
                  buyer's words — the reason the list is served by the API rather
                  than mirrored here. */}
              {criterion.description && (
                <p className="mt-1 text-[11px] leading-relaxed text-subtle">
                  {criterion.description}
                </p>
              )}
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
        disabled={total <= 0 || criteria.length === 0}
      >
        Re-run comparison with these weights
      </Button>
    </Card>
  );
}

/**
 * Fractions → a 0–100 draft over the given criteria.
 *
 * `weights` is the server's normalised snapshot; `defaults` is the per-type
 * default set. Passing `weights: null` therefore reads as "reset to defaults".
 */
function toDraft(weights, criteria, defaults) {
  const source = weights && Object.keys(weights).length ? weights : defaults || {};

  return criteria.reduce((draft, criterion) => {
    const value = source[criterion.key] ?? defaults?.[criterion.key] ?? 0;

    draft[criterion.key] = Math.round(Number(value) * 100);

    return draft;
  }, {});
}

export default WeightEditor;
