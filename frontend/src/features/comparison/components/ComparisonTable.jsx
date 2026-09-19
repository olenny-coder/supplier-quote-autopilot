import EmptyState from "@/shared/components/EmptyState";
import { Badge } from "@/shared/components/ui";
import {
  formatDate,
  formatFieldKey,
  formatHours,
  formatLeadTime,
  formatNumber,
  formatPercentValue,
  formatPrice,
  toNumber,
} from "@/shared/lib/format";
import { StatusBadge } from "@/shared/components/StatusBadge";

import { useMetaOptions } from "@/features/meta/hooks";

/**
 * The comparison table: one row per quote, ranked by composite score.
 *
 * Unranked quotes are deliberately still rendered, below the ranked ones and in
 * a muted style, with their `exclusion_reason` spelled out. A supplier who was
 * scored cannot simply vanish from the table — the buyer would have no way to
 * tell "excluded because the price is missing" from "excluded because we forgot
 * them", and the whole point of the award guardrail is that the buyer sees every
 * candidate before deciding.
 *
 * Two services-specific columns carry the argument the price alone cannot:
 * response time, because the SLA is what most often decides a maintenance award,
 * and accreditation coverage, because a contractor without the required licence
 * cannot lawfully do the work at any price.
 *
 * Columns are data rather than markup so the header and the body cannot drift
 * apart when the goods-only columns are dropped for a service RFQ.
 *
 * Scores and money are JSON strings (Python `Decimal`), so every value is parsed
 * with `toNumber()` before it is formatted or turned into a bar width.
 */

function ComparisonTable({ comparison }) {
  const { options: meta } = useMetaOptions();

  const results = comparison?.results || [];

  const ranked = results
    .filter((result) => result.rank !== null && result.rank !== undefined)
    .sort((a, b) => Number(a.rank) - Number(b.rank));

  const unranked = results.filter(
    (result) => result.rank === null || result.rank === undefined
  );

  const isGoods = comparison?.procurement_type === "goods";

  // No hard-coded "USD": a snapshot without a base currency falls through to the
  // base currency in `formatPrice` rather than to somebody else's dollars.
  const baseCurrency = comparison?.base_currency;
  const requiredAccreditations = comparison?.required_accreditations || [];
  const recommendedId = comparison?.recommended_quote_id;
  const backupId = comparison?.backup_quote_id;

  if (!results.length) {
    return (
      <EmptyState
        title="No quotes have been scored yet"
        description="Run the comparison once at least one supplier has quoted."
      />
    );
  }

  const columns = [
    {
      label: "Rank",
      cell: (result) => (
        <RankCell result={result} isRecommended={result.quote_id === recommendedId} />
      ),
    },
    {
      label: "Supplier",
      cell: (result) => (
        <SupplierCell
          result={result}
          isRecommended={result.quote_id === recommendedId}
          isBackup={result.quote_id === backupId}
        />
      ),
    },
    {
      label: "Composite score",
      cell: (result) => <ScoreCell result={result} />,
    },
    {
      label: isGoods ? "Landed cost" : "Total cost",
      cell: (result) => <CostCell result={result} baseCurrency={baseCurrency} isGoods={isGoods} />,
    },
    {
      label: "Response (SLA)",
      scope: "service",
      cell: (result) => {
        const hours = toNumber(result.response_time_hours);

        if (hours === null) {
          return <span className="text-subtle">not stated</span>;
        }

        return (
          <span
            className={hours > 24 ? "font-medium text-warning-soft-fg" : "text-muted"}
            title={
              hours > 24
                ? "Over one business day — flagged as a risk on this quote."
                : undefined
            }
          >
            {formatHours(hours)}
          </span>
        );
      },
    },
    {
      label: "Accreditations",
      scope: "service",
      cell: (result) => (
        <AccreditationCell
          result={result}
          required={requiredAccreditations}
        />
      ),
    },
    {
      label: "Quoted rate",
      cell: (result) => (
        <span className="text-muted">
          {result.unit_price_original == null
            ? "—"
            : formatPrice(
                toNumber(result.unit_price_original),
                result.currency_original || baseCurrency
              )}
          {result.unit_original && (
            <span className="text-subtle"> / {result.unit_original}</span>
          )}
        </span>
      ),
    },
    {
      label: isGoods ? "Normalised unit" : "Normalised rate",
      cell: (result) => (
        <span className="text-muted">
          {result.unit_price_base == null
            ? "—"
            : formatPrice(toNumber(result.unit_price_base), baseCurrency)}
        </span>
      ),
    },
    {
      label: isGoods ? "Lead time" : "Mobilisation",
      cell: (result) => (
        <span className="text-muted">{formatLeadTime(result.lead_time_days)}</span>
      ),
    },
    {
      label: "MOQ",
      scope: "goods",
      cell: (result) => (
        <span className="text-muted">{formatNumber(result.moq)}</span>
      ),
    },
    {
      label: "Payment terms",
      cell: (result) => (
        <span className="text-muted">
          {result.payment_terms || <span className="text-subtle">—</span>}
        </span>
      ),
    },
    {
      label: "Incoterms",
      scope: "goods",
      cell: (result) => (
        <span className="text-muted">
          {result.incoterms || <span className="text-subtle">—</span>}
        </span>
      ),
    },
    {
      label: isGoods ? "Validity" : "Rates valid until",
      cell: (result) => (
        <span className="text-muted">
          {result.validity_date ? (
            formatDate(result.validity_date)
          ) : (
            <span className="text-subtle">—</span>
          )}
        </span>
      ),
    },
    {
      label: isGoods ? "Warranty" : "Defect liability",
      cell: (result) => (
        <span className="text-muted">
          {result.warranty_months == null
            ? "—"
            : `${formatNumber(result.warranty_months)} months`}
        </span>
      ),
    },
    {
      // The per-criterion scores the composite is built from, labelled with the
      // criterion names the API publishes (so a tenth criterion appears here
      // without a code change).
      label: "Scores",
      cell: (result) => (
        <ScoreBreakdown result={result} criteria={meta?.criteria} />
      ),
    },
    {
      label: "Completeness",
      cell: (result) => (
        <div>
          <StatusBadge
            status={result.comparable === false ? "incomplete" : "complete"}
            domain="quote"
          />

          {result.missing_fields?.length > 0 && (
            <div className="mt-2 flex max-w-[13rem] flex-wrap gap-1.5">
              {result.missing_fields.map((field) => (
                <span
                  key={field}
                  className="rounded-full bg-warning-soft px-2 py-0.5 text-[11px] font-medium text-warning-soft-fg"
                >
                  {formatFieldKey(field)}
                </span>
              ))}
            </div>
          )}

          {result.incompleteness_note && (
            <p className="mt-2 max-w-[13rem] text-xs leading-relaxed text-subtle">
              {result.incompleteness_note}
            </p>
          )}

          {result.exclusion_reason && (
            <p className="mt-2 max-w-[13rem] text-xs font-medium leading-relaxed text-danger">
              {result.exclusion_reason}
            </p>
          )}
        </div>
      ),
    },
    {
      label: "Risk flags & notes",
      cell: (result) => (
        <div>
          {result.risk_flags?.length ? (
            <ul className="max-w-[18rem] space-y-1">
              {result.risk_flags.map((flag) => (
                <li
                  key={flag}
                  className="rounded-lg bg-danger-soft px-2 py-1 text-[11px] font-medium leading-relaxed text-danger-soft-fg"
                >
                  {flag}
                </li>
              ))}
            </ul>
          ) : (
            <span className="text-subtle">—</span>
          )}

          {result.notes?.length > 0 && (
            <ul className="mt-2 max-w-[18rem] space-y-1">
              {result.notes.map((note) => (
                <li key={note} className="text-[11px] leading-relaxed text-subtle">
                  {note}
                </li>
              ))}
            </ul>
          )}
        </div>
      ),
    },
  ];

  const visibleColumns = columns
    .filter((column) => column.scope !== "service" || !isGoods)
    .filter((column) => column.scope !== "goods" || isGoods);

  return (
    <div className="overflow-hidden rounded-2xl border border-border-default bg-surface shadow-card">
      <div className="overflow-x-auto">
        <table className="min-w-[1900px] w-full text-sm">
          <thead>
            <tr className="border-b border-border-default bg-surface-2 text-left text-xs font-semibold uppercase tracking-wider text-subtle">
              {visibleColumns.map((column) => (
                <th key={column.label} className="whitespace-nowrap px-5 py-3">
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>

          <tbody className="divide-y divide-border-default">
            {ranked.map((result) => (
              <ResultRow
                key={result.quote_id}
                result={result}
                columns={visibleColumns}
                recommended={result.quote_id === recommendedId}
              />
            ))}

            {unranked.length > 0 && (
              <>
                <tr className="bg-surface-2/60">
                  <td
                    colSpan={visibleColumns.length}
                    className="px-5 py-3 text-xs font-semibold uppercase tracking-wider text-subtle"
                  >
                    Not ranked — shown so nobody silently disappears
                  </td>
                </tr>

                {unranked.map((result) => (
                  <ResultRow
                    key={result.quote_id}
                    result={result}
                    columns={visibleColumns}
                    muted
                  />
                ))}
              </>
            )}
          </tbody>
        </table>
      </div>

      <div className="border-t border-border-default bg-surface-2 px-5 py-3">
        {isGoods ? (
          <p className="text-xs text-muted">
            Landed cost converts every quote into {baseCurrency || "the RFQ's currency"}
            {comparison?.base_incoterms
              ? ` on ${comparison.base_incoterms} terms`
              : ""}
            {comparison?.quantity
              ? ` for ${formatNumber(comparison.quantity)} ${
                  comparison.unit || ""
                }`
              : ""}
            . Weights are recorded with the snapshot, so the ranking can always be
            reproduced.
          </p>
        ) : (
          <p className="text-xs leading-relaxed text-muted">
            Every quote is converted into {baseCurrency || "the RFQ's currency"} and
            onto one rate basis before it is scored
            {comparison?.quantity
              ? `, for ${formatNumber(comparison.quantity)} ${
                  comparison.unit || "unit"
                }`
              : ""}
            . A callout / attendance charge is added separately from the rate,
            because attendance is invoiced whether or not the works proceed — a low
            rate with a large callout is the classic way a maintenance quote looks
            cheapest and is not. Tax derived from a stated GST rate is labelled as
            derived rather than quoted. Weights are recorded with the snapshot, so
            the ranking can always be reproduced.
          </p>
        )}
      </div>
    </div>
  );
}

function ResultRow({ result, columns, recommended = false, muted = false }) {
  return (
    <tr
      className={`align-top transition ${
        muted
          ? "bg-surface-2/40 text-muted opacity-80"
          : recommended
            ? "bg-success-soft/40"
            : "hover:bg-surface-hover"
      }`}
    >
      {columns.map((column) => (
        <td key={column.label} className="px-5 py-4">
          {column.cell(result)}
        </td>
      ))}
    </tr>
  );
}

function RankCell({ result, isRecommended }) {
  return (
    <span
      className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${
        isRecommended
          ? "bg-success-soft text-success-soft-fg"
          : "bg-surface-2 text-muted"
      }`}
    >
      {result.rank ?? "—"}
    </span>
  );
}

function SupplierCell({ result, isRecommended, isBackup }) {
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-content">{result.supplier_name}</span>
        {isRecommended && <Badge variant="success">Recommended</Badge>}
        {isBackup && <Badge variant="primary">Backup</Badge>}
      </div>

      <div className="mt-1.5 flex flex-wrap items-center gap-2">
        <StatusBadge status={result.supplier_risk || "low"} domain="risk" />
        {result.unit_mismatch && <Badge variant="warning">Rate basis mismatch</Badge>}
      </div>
    </div>
  );
}

function ScoreCell({ result }) {
  const score = toNumber(result.composite_score);

  if (score === null) return <span className="text-subtle">—</span>;

  return (
    <div className="w-32">
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-content">
          {formatNumber(score, { maximumFractionDigits: 1 })}
        </span>
        <span className="text-[11px] text-subtle">/ 100</span>
      </div>
      <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
        <span
          className="block h-full rounded-full bg-linear-to-r from-primary to-violet-500"
          style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
        />
      </div>
    </div>
  );
}

/**
 * The total, and the lines it is built from.
 *
 * The breakdown is shown rather than just the total because the buyer has to
 * justify the award: "this is the cheapest" is only credible next to what the
 * number contains. The callout line is the services equivalent of freight and is
 * named, and a tax line the engine derived from a stated GST rate is marked as
 * derived — an invented-looking figure that is in fact the supplier's own rate
 * applied to their own subtotal.
 */
function CostCell({ result, baseCurrency, isGoods }) {
  const total = toNumber(result.total_base);
  const breakdown = result.breakdown || {};
  const fxRate = toNumber(breakdown.fx_rate);

  const taxDerived = breakdown.tax_derived_from_rate === true;
  const callout = toNumber(breakdown.callout);

  const lines = [
    { key: "goods", label: isGoods ? "Goods" : "Rate × quantity", value: toNumber(breakdown.goods) },
    { key: "callout", label: "Callout", value: callout },
    { key: "shipping", label: "Freight", value: toNumber(breakdown.shipping) },
    { key: "duties", label: "Duties", value: toNumber(breakdown.duties) },
    {
      key: "taxes",
      label: taxDerived ? "GST (derived)" : "Tax",
      value: toNumber(breakdown.taxes),
      derived: taxDerived,
    },
    { key: "discount", label: "Discount", value: toNumber(breakdown.discount), negative: true },
  ].filter((line) => line.value !== null && line.value !== 0);

  return (
    <div className="min-w-[11rem]">
      <span className="font-semibold text-content">
        {total === null ? "—" : formatPrice(total, baseCurrency)}
      </span>

      {lines.length > 0 && (
        <dl className="mt-1 space-y-0.5">
          {lines.map((line) => (
            <div key={line.key} className="flex items-baseline justify-between gap-2 text-[11px]">
              <dt className={line.derived ? "text-warning-soft-fg" : "text-subtle"}>
                {line.negative ? `− ${line.label}` : line.label}
              </dt>
              <dd className={line.derived ? "text-warning-soft-fg" : "text-subtle"}>
                {formatPrice(line.value, baseCurrency)}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {taxDerived && (
        <p
          className="mt-1 text-[11px] leading-relaxed text-warning-soft-fg"
          title="The supplier stated a GST rate but no tax amount, so the engine applied their rate to their own subtotal. The figure is marked so nobody mistakes it for a quoted amount."
        >
          GST from the stated rate, not a quoted amount
          {result.gst_rate ? ` (${formatPercentValue(result.gst_rate)})` : ""}
        </p>
      )}

      {fxRate && fxRate !== 1 && breakdown.fx_from && (
        <span className="mt-1 block text-[11px] text-subtle">
          FX {formatNumber(fxRate, { maximumFractionDigits: 4 })} {breakdown.fx_from}→
          {breakdown.fx_to}
        </span>
      )}

      {breakdown.incoterms_from && breakdown.incoterms_to && (
        <span className="mt-0.5 block text-[11px] text-subtle">
          landed {breakdown.incoterms_to}
        </span>
      )}
    </div>
  );
}

/**
 * Accreditation coverage: what the RFQ required, and what this supplier holds.
 *
 * The missing set is the "cannot lawfully do the work" signal the buyer must not
 * be able to miss, so it is counted in words *and* named in danger chips. The
 * score is capped rather than zeroed for exactly this reason: the engine keeps
 * the arithmetic honest and shows the buyer the reason.
 */
function AccreditationCell({ result, required }) {
  const held = result.compliance_accreditations || [];
  const missing = result.missing_accreditations || [];

  if (!required.length) {
    return (
      <div className="max-w-[16rem] space-y-1.5">
        <span className="text-subtle">None required</span>
        {held.length > 0 && <HeldChips held={held} />}
      </div>
    );
  }

  const met = required.filter((accreditation) => !missing.includes(accreditation));

  return (
    <div className="max-w-[16rem] space-y-1.5">
      <span
        className={`text-xs font-medium ${
          missing.length ? "text-danger" : "text-success-soft-fg"
        }`}
      >
        {met.length} of {required.length} required
        {missing.length ? " — cannot lawfully proceed" : " held"}
      </span>

      {missing.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {missing.map((accreditation) => (
            <span
              key={accreditation}
              title={`Required by this RFQ and not held: ${accreditation}. The compliance score is capped for this reason.`}
              className="rounded-full bg-danger-soft px-2 py-0.5 text-[11px] font-medium text-danger-soft-fg"
            >
              ✕ {accreditation}
            </span>
          ))}
        </div>
      )}

      {held.length > 0 && <HeldChips held={held} />}
    </div>
  );
}

function HeldChips({ held }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {held.map((accreditation) => (
        <span
          key={accreditation}
          className="rounded-full bg-success-soft px-2 py-0.5 text-[11px] font-medium text-success-soft-fg"
        >
          {accreditation}
        </span>
      ))}
    </div>
  );
}

/** The per-criterion scores behind the composite, in the engine's own order. */
function ScoreBreakdown({ result, criteria }) {
  const scores = result.scores || {};
  const keys = Object.keys(scores);

  if (!keys.length) return <span className="text-subtle">—</span>;

  const labelFor = (key) =>
    criteria?.find((criterion) => criterion.key === key)?.label || formatFieldKey(key);

  return (
    <dl className="max-w-[12rem] space-y-0.5">
      {keys.map((key) => (
        <div key={key} className="flex items-baseline justify-between gap-2 text-[11px]">
          <dt className="text-subtle">{labelFor(key)}</dt>
          <dd className="text-muted">
            {formatNumber(scores[key], { maximumFractionDigits: 0 })}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export default ComparisonTable;
