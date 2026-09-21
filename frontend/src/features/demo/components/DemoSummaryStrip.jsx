import { StatusBadge } from "@/shared/components/StatusBadge";
import { Card } from "@/shared/components/ui";
import {
  formatDateTime,
  formatHours,
  formatNumber,
  formatRateBasis,
} from "@/shared/lib/format";

/**
 * What the buyer actually asked for, in one strip.
 *
 * Every value is read from the RFQ the API returned — item, category, the rate
 * basis the rates must be quoted against, the quantity, the SLA the buyer
 * requires and the licences the work needs. Nothing here is derived in the
 * browser: if the demo page and the buyer's own RFQ page disagreed about what was
 * requested, the rest of the page would be arguing from the wrong premise.
 *
 * The required-field contract is shown too, because it is the thing the follow-up
 * drafts later chase: a visitor who has read "we asked for payment terms" is in a
 * position to understand why the agent chases exactly that and nothing else.
 */

function Field({ label, children }) {
  return (
    <div>
      <dt className="text-[11px] font-semibold uppercase tracking-wider text-subtle">
        {label}
      </dt>
      <dd className="mt-1 text-sm font-medium text-content">{children}</dd>
    </div>
  );
}

function Chip({ children, tone = "neutral" }) {
  const tones = {
    neutral: "bg-surface-2 text-muted",
    primary: "bg-primary-soft text-primary-soft-fg",
  };

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

function DemoSummaryStrip({ rfq }) {
  const requiredAccreditations = rfq.required_accreditations || [];
  const requiredFieldLabels = rfq.required_field_labels || [];

  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-col gap-3 border-b border-border-default pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold tracking-tight text-content sm:text-lg">
              {rfq.item_name}
            </h3>
            <StatusBadge status={rfq.status} domain="rfq" />
          </div>

          <p className="mt-1.5 text-xs text-subtle">
            {rfq.rfq_number}
            {rfq.buyer_company ? ` · ${rfq.buyer_company}` : ""}
            {rfq.site_name ? ` · ${rfq.site_name}` : ""}
          </p>
        </div>

        {rfq.deadline && (
          <p className="shrink-0 text-xs text-muted sm:text-right">
            <span className="block text-[11px] font-semibold uppercase tracking-wider text-subtle">
              Quotes close
            </span>
            {formatDateTime(rfq.deadline)}
          </p>
        )}
      </div>

      <p className="mt-5 text-sm leading-relaxed text-muted">
        {rfq.specification}
      </p>

      <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
        <Field label="Category">{rfq.category || "—"}</Field>
        <Field label="Rate basis">{formatRateBasis(rfq.unit)}</Field>
        <Field label="Quantity">
          {formatNumber(rfq.quantity)} {rfq.unit || ""}
        </Field>
        <Field label="Required response">{formatHours(rfq.required_response_hours)}</Field>
      </dl>

      <div className="mt-6 grid gap-5 border-t border-border-default pt-5 sm:grid-cols-2">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-subtle">
            Required accreditations
          </p>

          {requiredAccreditations.length ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {requiredAccreditations.map((accreditation) => (
                <Chip key={accreditation} tone="primary">
                  {accreditation}
                </Chip>
              ))}
            </div>
          ) : (
            <p className="mt-1 text-sm text-muted">None specified</p>
          )}
        </div>

        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-subtle">
            A quote must carry
          </p>

          {requiredFieldLabels.length ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {requiredFieldLabels.map((label) => (
                <Chip key={label}>{label}</Chip>
              ))}
            </div>
          ) : (
            <p className="mt-1 text-sm text-muted">No required-field contract set</p>
          )}
        </div>
      </div>
    </Card>
  );
}

export default DemoSummaryStrip;
