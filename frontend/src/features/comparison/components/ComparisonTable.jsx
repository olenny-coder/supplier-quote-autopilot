import EmptyState from "@/shared/components/EmptyState";
import { Badge } from "@/shared/components/ui";
import {
  formatDate,
  formatFieldKey,
  formatLeadTime,
  formatNumber,
  formatPrice,
  toNumber,
} from "@/shared/lib/format";
import { StatusBadge } from "@/shared/components/StatusBadge";

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
 * Scores and money are JSON strings (Python `Decimal`), so every value is parsed
 * with `toNumber()` before it is formatted or turned into a bar width.
 */

const COLUMNS = [
  { label: "Rank" },
  { label: "Supplier" },
  { label: "Composite score" },
  { label: "Landed cost" },
  { label: "Quoted unit price" },
  { label: "Normalised unit" },
  { label: "Lead time" },
  { label: "MOQ" },
  { label: "Payment terms" },
  { label: "Incoterms" },
  { label: "Validity" },
  { label: "Warranty" },
  { label: "Completeness" },
  { label: "Risk flags & notes" },
];

function ComparisonTable({ comparison }) {
  const results = comparison?.results || [];

  const ranked = results
    .filter((result) => result.rank !== null && result.rank !== undefined)
    .sort((a, b) => Number(a.rank) - Number(b.rank));

  const unranked = results.filter(
    (result) => result.rank === null || result.rank === undefined
  );

  const baseCurrency = comparison?.base_currency || "USD";

  if (!results.length) {
    return (
      <EmptyState
        title="No quotes have been scored yet"
        description="Run the comparison once at least one supplier has quoted."
      />
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border-default bg-surface shadow-card">
      <div className="overflow-x-auto">
        <table className="min-w-[1500px] w-full text-sm">
          <thead>
            <tr className="border-b border-border-default bg-surface-2 text-left text-xs font-semibold uppercase tracking-wider text-subtle">
              {COLUMNS.map((column) => (
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
                baseCurrency={baseCurrency}
                isRecommended={result.quote_id === comparison.recommended_quote_id}
                isBackup={result.quote_id === comparison.backup_quote_id}
              />
            ))}

            {unranked.length > 0 && (
              <>
                <tr className="bg-surface-2/60">
                  <td
                    colSpan={COLUMNS.length}
                    className="px-5 py-3 text-xs font-semibold uppercase tracking-wider text-subtle"
                  >
                    Not ranked — shown so nobody silently disappears
                  </td>
                </tr>

                {unranked.map((result) => (
                  <ResultRow
                    key={result.quote_id}
                    result={result}
                    baseCurrency={baseCurrency}
                    muted
                  />
                ))}
              </>
            )}
          </tbody>
        </table>
      </div>

      <div className="border-t border-border-default bg-surface-2 px-5 py-3">
        <p className="text-xs text-muted">
          Landed cost converts every quote into {baseCurrency}
          {comparison?.base_incoterms
            ? ` on ${comparison.base_incoterms} terms`
            : ""}
          {comparison?.quantity
            ? ` for ${formatNumber(comparison.quantity)} ${
                comparison.unit || "pcs"
              }`
            : ""}
          . Weights are recorded with the snapshot, so the ranking can always be
          reproduced.
        </p>
      </div>
    </div>
  );
}

function ResultRow({ result, baseCurrency, isRecommended, isBackup, muted = false }) {
  const score = toNumber(result.composite_score);
  const totalBase = toNumber(result.total_base);
  const fxRate = toNumber(result.breakdown?.fx_rate);
  const convertedCurrency =
    result.breakdown?.incoterms_from && result.breakdown?.incoterms_to
      ? `landed ${result.breakdown.incoterms_to}`
      : null;

  return (
    <tr
      className={`align-top transition ${
        muted
          ? "bg-surface-2/40 text-muted opacity-80"
          : isRecommended
            ? "bg-success-soft/40"
            : "hover:bg-surface-hover"
      }`}
    >
      <td className="px-5 py-4">
        <span
          className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${
            isRecommended
              ? "bg-success-soft text-success-soft-fg"
              : "bg-surface-2 text-muted"
          }`}
        >
          {result.rank ?? "—"}
        </span>
      </td>

      <td className="px-5 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium text-content">{result.supplier_name}</span>
          {isRecommended && <Badge variant="success">Recommended</Badge>}
          {isBackup && <Badge variant="primary">Backup</Badge>}
        </div>

        <div className="mt-1.5 flex flex-wrap items-center gap-2">
          <StatusBadge status={result.supplier_risk || "low"} domain="risk" />
          {result.unit_mismatch && (
            <Badge variant="warning">Unit mismatch</Badge>
          )}
        </div>
      </td>

      <td className="px-5 py-4">
        {score === null ? (
          <span className="text-subtle">—</span>
        ) : (
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
        )}
      </td>

      <td className="whitespace-nowrap px-5 py-4">
        <span className="font-semibold text-content">
          {totalBase === null ? "—" : formatPrice(totalBase, baseCurrency)}
        </span>
        {fxRate && fxRate !== 1 && result.breakdown?.fx_from && (
          <span className="mt-0.5 block text-[11px] text-subtle">
            FX {formatNumber(fxRate, { maximumFractionDigits: 4 })}{" "}
            {result.breakdown.fx_from}→{result.breakdown.fx_to}
          </span>
        )}
        {convertedCurrency && (
          <span className="mt-0.5 block text-[11px] text-subtle">
            {convertedCurrency}
          </span>
        )}
      </td>

      <td className="whitespace-nowrap px-5 py-4 text-muted">
        {result.unit_price_original == null
          ? "—"
          : formatPrice(
              toNumber(result.unit_price_original),
              result.currency_original || baseCurrency
            )}
        {result.unit_original && (
          <span className="text-subtle"> / {result.unit_original}</span>
        )}
      </td>

      <td className="whitespace-nowrap px-5 py-4 text-muted">
        {result.unit_price_base == null
          ? "—"
          : formatPrice(toNumber(result.unit_price_base), baseCurrency)}
      </td>

      <td className="whitespace-nowrap px-5 py-4 text-muted">
        {formatLeadTime(result.lead_time_days)}
      </td>

      <td className="whitespace-nowrap px-5 py-4 text-muted">
        {formatNumber(result.moq)}
      </td>

      <td className="max-w-[11rem] px-5 py-4 text-muted">
        {result.payment_terms || <span className="text-subtle">—</span>}
      </td>

      <td className="whitespace-nowrap px-5 py-4 text-muted">
        {result.incoterms || <span className="text-subtle">—</span>}
      </td>

      <td className="whitespace-nowrap px-5 py-4 text-muted">
        {result.validity_date ? (
          formatDate(result.validity_date)
        ) : (
          <span className="text-subtle">—</span>
        )}
      </td>

      <td className="whitespace-nowrap px-5 py-4 text-muted">
        {result.warranty_months == null
          ? "—"
          : `${formatNumber(result.warranty_months)} months`}
      </td>

      <td className="px-5 py-4">
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
      </td>

      <td className="px-5 py-4">
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
      </td>
    </tr>
  );
}

export default ComparisonTable;
