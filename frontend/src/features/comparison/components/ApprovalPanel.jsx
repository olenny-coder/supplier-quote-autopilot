import { useState } from "react";

import { toast } from "sonner";

import { Badge, Button, Card, FormField, inputClass } from "@/shared/components/ui";
import {
  formatDateTime,
  formatFieldKey,
  formatNumber,
  formatPrice,
  toNumber,
} from "@/shared/lib/format";
import { StatusBadge } from "@/shared/components/StatusBadge";

import { approveComparison } from "../api";

const DECISIONS = [
  { value: "approved", label: "Approve — award this supplier" },
  { value: "rejected", label: "Reject this quote" },
  { value: "deferred", label: "Defer — decide later" },
];

const errorClass = "border-danger/60 bg-danger-soft/40";

/**
 * Tab 3 — the award decision.
 *
 * The guardrail, in the UI as well as in the API: this panel is the *only* way
 * a supplier gets awarded, and it always requires a human note. Nothing the
 * scheduler, the importer or the LLM does can reach the approve endpoint — there
 * is no automatic caller — so an award is always attributable to a person and a
 * reason, and an award that ignores the recommendation is recorded as an
 * override.
 *
 * Once a decision exists the form is replaced by the signed audit entry and
 * disabled, because a second award would make the trail ambiguous.
 */
function ApprovalPanel({ rfqId, comparison, approvals = [], onApproved }) {
  const [quoteId, setQuoteId] = useState(() => comparison?.recommended_quote_id ?? "");
  const [decision, setDecision] = useState("approved");
  const [note, setNote] = useState("");
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  if (!comparison) return null;

  const existing = comparison.approval;

  // Ranked quotes first, so the default reading order is the engine's ranking.
  const results = [...(comparison.results || [])].sort((a, b) => {
    const rankA = a.rank ?? Number.MAX_SAFE_INTEGER;
    const rankB = b.rank ?? Number.MAX_SAFE_INTEGER;

    return rankA - rankB;
  });

  const selected = results.find((result) => Number(result.quote_id) === Number(quoteId));

  const selectedMissing = selected?.missing_fields || [];
  const selectedHasPrice = selected
    ? toNumber(selected.unit_price_original) !== null && toNumber(selected.unit_price_original) > 0
    : true;

  const overrideRequired =
    decision === "approved" && selectedMissing.length > 0 && selectedHasPrice;

  const handleSubmit = async (event) => {
    event.preventDefault();

    const errs = {};

    if (!quoteId) {
      errs.quote_id = "Pick the quote this decision is about";
    }

    if (!note.trim() || note.trim().length < 3) {
      errs.note = "A note of at least 3 characters is required for the audit trail";
    } else if (decision === "approved" && selected && !selectedHasPrice) {
      errs.note = "This quote has no unit price, so it cannot be awarded";
    } else if (overrideRequired && !note.trim().toLowerCase().startsWith("override")) {
      errs.note =
        "This quote is incomplete — start the note with “override” and explain why it is still acceptable";
    }

    setErrors(errs);

    if (Object.keys(errs).length) return;

    try {
      setSubmitting(true);

      const approval = await approveComparison(rfqId, {
        quote_id: Number(quoteId),
        decision,
        note: note.trim(),
      });

      toast.success(
        decision === "approved"
          ? `Award recorded for ${approval.supplier_name || "the supplier"}.`
          : `Decision recorded: ${decision}.`
      );

      setNote("");
      setErrors({});

      await onApproved?.();
    } catch (error) {
      // The API enforces the same rules (including the `override` prefix); show
      // its reason verbatim so the buyer can act on it.
      toast.error(error.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="flex flex-col gap-5 p-5" >
      <div>
        <h3 className="text-sm font-semibold text-content">Award approval</h3>
        <p className="mt-1 text-xs leading-relaxed text-muted">
          This is the only way a supplier is awarded, and it always requires your
          decision. The engine ranks and recommends; it never awards.
        </p>
      </div>

      {existing ? (
        <div className="space-y-4">
          <div className="rounded-xl border border-success-soft-fg/25 bg-success-soft p-4">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={existing.decision} domain="approval" />
              {existing.overrode_recommendation ? (
                <Badge variant="warning">Overrode the recommendation</Badge>
              ) : (
                <Badge variant="neutral">Followed the recommendation</Badge>
              )}
            </div>

            <dl className="mt-3 grid gap-3 sm:grid-cols-2">
              <Detail label="Supplier" value={existing.supplier_name || "—"} />
              <Detail
                label="Quote reference"
                value={existing.quote_reference || `#${existing.quote_id}`}
              />
              <Detail label="Decided by" value={existing.decided_by_email || "—"} />
              <Detail
                label="Decided at"
                value={formatDateTime(existing.decided_at || existing.created_at)}
              />
              {existing.awarded_total_cost != null && (
                <Detail
                  label="Awarded landed cost"
                  value={formatPrice(
                    toNumber(existing.awarded_total_cost) ?? 0,
                    existing.awarded_currency || comparison.base_currency
                  )}
                />
              )}
            </dl>

            <div className="mt-3 border-t border-success-soft-fg/20 pt-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-success-soft-fg">
                Note on record
              </p>
              <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-success-soft-fg">
                {existing.note}
              </p>
            </div>
          </div>

          <p className="text-xs text-muted">
            This RFQ already has a recorded decision, so further approvals are
            disabled — otherwise the audit trail would be ambiguous. The full
            history stays below.
          </p>

          {approvals.length > 1 && <ApprovalHistory approvals={approvals} />}
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
          <FormField label="Quote to decide on" required error={errors.quote_id}>
            <select
              value={quoteId}
              onChange={(event) => {
                setQuoteId(event.target.value);
                setErrors((prev) => ({ ...prev, quote_id: null, note: null }));
              }}
              className={`${inputClass} ${errors.quote_id ? errorClass : ""}`}
            >
              <option value="">Select a quote…</option>
              {results.map((result) => (
                <option key={result.quote_id} value={result.quote_id}>
                  {result.rank ? `#${result.rank} ` : "(not ranked) "}
                  {result.supplier_name} —{" "}
                  {result.total_base == null
                    ? "no landed cost"
                    : formatPrice(toNumber(result.total_base), comparison.base_currency)}
                </option>
              ))}
            </select>
          </FormField>

          {selected && (
            <div className="rounded-xl border border-border-default bg-surface-2/60 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge
                  status={selected.comparable === false ? "incomplete" : "complete"}
                  domain="quote"
                />
                {selected.quote_id === comparison.recommended_quote_id && (
                  <Badge variant="success">Engine recommendation</Badge>
                )}
                {selected.comparable === false && (
                  <Badge variant="warning">Not ranked</Badge>
                )}
              </div>

              <p className="mt-2 text-xs text-muted">
                {selected.rank ? `Ranked #${selected.rank}` : "Excluded from the ranking"}
                {selected.exclusion_reason ? ` — ${selected.exclusion_reason}` : ""}
                {selected.total_base != null
                  ? ` · landed ${formatPrice(
                      toNumber(selected.total_base),
                      comparison.base_currency
                    )}`
                  : ""}
              </p>

              {selectedMissing.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {selectedMissing.map((field) => (
                    <span
                      key={field}
                      className="rounded-full bg-warning-soft px-2 py-0.5 text-[11px] font-medium text-warning-soft-fg"
                    >
                      {formatFieldKey(field)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {overrideRequired && (
            <div className="rounded-xl border border-warning-soft-fg/25 bg-warning-soft px-4 py-3">
              <p className="text-sm font-semibold text-warning-soft-fg">
                This quote is still incomplete
              </p>
              <p className="mt-1 text-sm leading-relaxed text-warning-soft-fg">
                It is missing{" "}
                {selectedMissing.map((field) => formatFieldKey(field)).join(", ")}.
                To award it anyway, start your note with the word{" "}
                <span className="font-semibold">override</span> — the reason you
                give is recorded on the audit entry.
              </p>
            </div>
          )}

          <FormField label="Decision" required>
            <select
              value={decision}
              onChange={(event) => {
                setDecision(event.target.value);
                setErrors((prev) => ({ ...prev, note: null }));
              }}
              className={inputClass}
            >
              {DECISIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </FormField>

          <FormField
            label="Decision note"
            hint="recorded on the audit entry"
            required
            error={errors.note}
          >
            <textarea
              rows={4}
              value={note}
              onChange={(event) => {
                setNote(event.target.value);
                if (errors.note) setErrors((prev) => ({ ...prev, note: null }));
              }}
              placeholder={
                overrideRequired
                  ? "override — the price is fixed for 30 days and the missing warranty is covered by our service contract"
                  : "e.g. Best landed cost, 30-day terms meet our policy, and the supplier is already approved for this category."
              }
              className={`${inputClass} resize-none ${errors.note ? errorClass : ""}`}
            />
          </FormField>

          <div className="rounded-xl border border-border-default bg-surface-2/60 px-4 py-3">
            <p className="text-xs leading-relaxed text-muted">
              <span className="font-semibold text-content">Guardrail:</span>{" "}
              approving writes a signed entry (who, when, which quote, your note)
              and is the only action that awards an RFQ. Nothing is sent to the
              supplier automatically.
            </p>
          </div>

          <Button
            type="submit"
            className="w-full"
            loading={submitting}
            loadingText="Recording decision…"
            disabled={!results.length}
          >
            {decision === "approved" ? "Approve award" : "Record decision"}
          </Button>

          {!results.length && (
            <p className="text-xs text-danger">
              There are no scored quotes to decide on yet.
            </p>
          )}
        </form>
      )}
    </Card>
  );
}

function Detail({ label, value }) {
  return (
    <div>
      <dt className="text-[11px] font-semibold uppercase tracking-wider text-success-soft-fg/80">
        {label}
      </dt>
      <dd className="mt-0.5 text-sm font-medium text-success-soft-fg">{value}</dd>
    </div>
  );
}

/** Full decision history, shown once there is more than the current entry. */
function ApprovalHistory({ approvals }) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-subtle">
        Decision history
      </h4>

      <ul className="divide-y divide-border-default overflow-hidden rounded-xl border border-border-default">
        {approvals.map((approval) => (
          <li
            key={approval.id}
            className="flex flex-col gap-1.5 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={approval.decision} domain="approval" />
                <span className="truncate text-sm font-medium text-content">
                  {approval.supplier_name || `Quote #${approval.quote_id}`}
                </span>
                {approval.overrode_recommendation && (
                  <Badge variant="warning">Override</Badge>
                )}
              </div>
              <p className="mt-1 line-clamp-2 text-xs text-muted">{approval.note}</p>
            </div>

            <div className="shrink-0 text-left sm:text-right">
              <p className="text-xs text-muted">{approval.decided_by_email}</p>
              <p className="text-[11px] text-subtle">
                {formatDateTime(approval.decided_at || approval.created_at)}
              </p>
              {approval.awarded_total_cost != null && (
                <p className="text-[11px] text-subtle">
                  {formatNumber(toNumber(approval.awarded_total_cost), {
                    maximumFractionDigits: 2,
                  })}{" "}
                  {approval.awarded_currency}
                </p>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default ApprovalPanel;
