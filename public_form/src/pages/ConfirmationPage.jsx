import { useEffect, useRef, useState } from "react";
import BrandedHeader from "@/components/BrandedHeader";
import Notice from "@/components/Notice";
import ProgressNotice from "@/components/ProgressNotice";
import { fetchInvitationStatus } from "@/lib/api";
import {
  buildQuoteSummaryText,
  copyToClipboard,
  downloadTextFile,
  formatDate,
  formatDateTime,
  summaryFilename,
} from "@/lib/format";

/** How long the confirmation view keeps re-checking that the link still works. */
const POLL_INTERVAL_MS = 20000;
const MAX_POLLS = 10;

/**
 * Post-submission view.
 *
 * This is a distinct view rather than a toast because the supplier needs three
 * things they will come back to later: the reference number (their proof of
 * submission), the buyer's contact details, and a way to see what is still
 * missing. It also owns the status polling: the form is done, but the link may
 * expire while the supplier is still reading, and telling them early avoids a
 * failed "revise my quote" attempt.
 */
export default function ConfirmationPage({
  preview,
  result,
  payload,
  rfqId,
  token,
  onRevise,
}) {
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  const [linkStatus, setLinkStatus] = useState(null);
  const copyTimerRef = useRef(null);

  const reference = result?.reference_number || "";
  const missingLabels = Array.isArray(result?.missing_field_labels)
    ? result.missing_field_labels
    : [];
  const isIncomplete = result?.completeness === "incomplete";

  useEffect(
    () => () => {
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    },
    []
  );

  /**
   * Bounded status polling. It stops after MAX_POLLS instead of running for the
   * life of the tab: the supplier is on a phone, possibly on mobile data, and an
   * open-ended timer that keeps a page awake is a battery and data cost with no
   * benefit — the link's expiry date does not change.
   */
  useEffect(() => {
    if (!rfqId || !token) return undefined;

    let cancelled = false;
    let timer = null;
    let polls = 0;

    async function poll() {
      polls += 1;
      try {
        const next = await fetchInvitationStatus(rfqId, token);
        if (!cancelled) setLinkStatus(next);
      } catch {
        // Best effort: a failed status check must never disturb the confirmation
        // screen or suggest the quote itself failed.
      }
      if (!cancelled && polls < MAX_POLLS) {
        timer = setTimeout(poll, POLL_INTERVAL_MS);
      }
    }

    timer = setTimeout(poll, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [rfqId, token]);

  const expiresAt = linkStatus?.expires_at || preview?.expires_at || "";
  const isExpired = linkStatus?.is_expired ?? preview?.is_expired ?? false;

  async function handleCopy() {
    const ok = await copyToClipboard(reference);
    setCopied(ok);
    setCopyFailed(!ok);
    if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    copyTimerRef.current = setTimeout(() => {
      setCopied(false);
      setCopyFailed(false);
    }, 2500);
  }

  function handleDownload() {
    downloadTextFile(
      summaryFilename(result),
      buildQuoteSummaryText({ preview, result, payload })
    );
  }

  const leadTimeDays =
    typeof result?.lead_time_days === "number" ? result.lead_time_days : null;

  // Every number around this form arrives as a string, so money is assembled
  // rather than formatted on the assumption of a numeric type.
  const currency = String(payload?.currency ?? "").trim();
  const accreditations = Array.isArray(payload?.compliance_accreditations)
    ? payload.compliance_accreditations
    : [];
  const withCurrency = (value) => {
    const text = String(value ?? "").trim();
    if (!text) return "";
    return [text, currency].filter(Boolean).join(" ");
  };
  const rateValue = payload?.unit_price
    ? [String(payload.unit_price).trim(), currency].filter(Boolean).join(" ")
    : "";
  const responseValue = payload?.response_time_hours
    ? `within ${String(payload.response_time_hours).trim()} hours`
    : "";
  const mobilisationValue = payload?.lead_time
    ? leadTimeDays
      ? `${payload.lead_time} (about ${leadTimeDays} days)`
      : payload.lead_time
    : "";

  return (
    <div className="min-h-screen">
      <BrandedHeader preview={preview} />

      <main className="mx-auto w-full max-w-2xl space-y-4 px-4 py-6 pb-12">
        <div className="text-center">
          <span
            aria-hidden="true"
            className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-success-soft"
          >
            <svg
              viewBox="0 0 24 24"
              className="h-9 w-9"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{ color: "var(--success-soft-fg)" }}
            >
              <path d="M4 12.5l5.5 5.5L20 6.5" />
            </svg>
          </span>
          <h1 className="mt-3 text-2xl font-bold leading-8 text-content">
            Thank you — your quote has been received
          </h1>
          {result?.message ? (
            <p className="mx-auto mt-2 max-w-md text-base leading-6 text-muted">
              {result.message}
            </p>
          ) : null}
        </div>

        {/* Reuses the same progress component with the final step highlighted, so
            the supplier sees the required-detail count that the buyer sees. */}
        <ProgressNotice
          currentStep={1}
          requiredKeys={preview?.required_fields || []}
          values={payload || {}}
        />

        {reference ? (
          <section
            aria-labelledby="reference-heading"
            className="rounded-2xl border border-border-default bg-surface p-4 shadow-card sm:p-5"
          >
            <h2
              id="reference-heading"
              className="text-xs font-semibold uppercase tracking-wide text-subtle"
            >
              Your reference number
            </h2>
            <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="break-all text-lg font-bold tracking-wide text-content tabular-nums sm:text-xl">
                {reference}
              </p>
              <button
                type="button"
                onClick={handleCopy}
                className="flex min-h-[48px] items-center justify-center gap-2 rounded-xl border border-border-strong bg-surface px-4 text-base font-semibold text-content transition-colors hover:bg-surface-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span aria-hidden="true">{copied ? "✓" : "⧉"}</span>
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
            {/* One polite live region for the copy result — announced, not shouted. */}
            <p aria-live="polite" className="sr-only">
              {copied ? "Reference number copied to the clipboard." : ""}
              {copyFailed
                ? "Copying is blocked in this browser. Please select the reference number and copy it manually."
                : ""}
            </p>
            {copyFailed ? (
              <p className="mt-2 text-xs font-medium text-danger-soft-fg">
                Copying is blocked in this browser. Please select the reference
                number above and copy it manually.
              </p>
            ) : (
              <p className="mt-2 text-xs text-muted">
                Keep this number — the buyer will use it when they contact you.
              </p>
            )}
          </section>
        ) : null}

        {isIncomplete ? (
          <Notice
            tone="warning"
            title="A few details are still missing"
            live
          >
            <p>
              The buyer received your quote, but these details were left blank so
              it cannot be compared yet:
            </p>
            {missingLabels.length > 0 ? (
              <ul className="mt-2 list-disc space-y-0.5 pl-5">
                {missingLabels.map((label) => (
                  <li key={label}>{label}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-2">
                Open the quote again to see which questions the buyer still needs
                answered.
              </p>
            )}
            <p className="mt-2">
              Send them using the same link (tap &ldquo;Submit a revised
              quote&rdquo; below), or simply reply to the buyer&rsquo;s email.
            </p>
          </Notice>
        ) : (
          <Notice tone="success" title="Your quote is complete">
            <p>
              Everything the buyer asked for is included. They will compare your
              quote with the others and get back to you.
            </p>
          </Notice>
        )}

        <section
          aria-labelledby="submitted-heading"
          className="rounded-2xl border border-border-default bg-surface p-4 shadow-card sm:p-5"
        >
          <h2
            id="submitted-heading"
            className="text-base font-bold text-content"
          >
            What you sent
          </h2>
          <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
            {/* What was quoted for, in the buyer's own words. A contractor with
                three of these links open needs to know which job this receipt
                belongs to without scrolling back up the page. */}
            <SummaryRow label="Category" value={preview?.category} />
            <SummaryRow label="Site" value={preview?.site_name} />
            <SummaryRow
              label={preview?.procurement_type === "goods" ? "Unit price" : "Rate"}
              value={rateValue}
            />
            <SummaryRow label="Rate basis" value={payload?.unit} />
            <SummaryRow label="Response time" value={responseValue} />
            <SummaryRow label="Mobilisation time" value={mobilisationValue} />
            <SummaryRow
              label="Callout / attendance"
              value={withCurrency(payload?.callout_charge)}
            />
            <SummaryRow
              label="Labour rate / hour"
              value={withCurrency(payload?.labour_rate)}
            />
            <SummaryRow
              label="Materials markup"
              value={
                payload?.materials_markup_pct
                  ? `${String(payload.materials_markup_pct).trim()}%`
                  : ""
              }
            />
            <SummaryRow
              label="Accreditations"
              value={accreditations.join(", ")}
            />
            <SummaryRow
              label={String(payload?.currency || "").toUpperCase() === "SGD" ? "GST rate" : "Tax rate"}
              value={
                payload?.gst_rate ? `${String(payload.gst_rate).trim()}%` : ""
              }
            />
            <SummaryRow label="Payment terms" value={payload?.payment_terms} />
            <SummaryRow
              label="Rates valid until"
              value={
                payload?.validity_date ? formatDate(payload.validity_date) : ""
              }
            />
            {/* Goods-only rows are shown only when something was actually
                quoted for them, so a maintenance quote is not padded out with
                "Not provided" lines that were never questions. */}
            {payload?.moq ? (
              <SummaryRow label="Minimum order quantity" value={payload.moq} />
            ) : null}
            {payload?.incoterms ? (
              <SummaryRow label="Incoterms" value={payload.incoterms} />
            ) : null}
            {payload?.warranty_months ? (
              <SummaryRow
                label="Defect liability"
                value={`${payload.warranty_months} months`}
              />
            ) : null}
            <SummaryRow
              label="Attachments"
              value={
                payload?.attachment_keys?.length
                  ? `${payload.attachment_keys.length} file(s) received`
                  : ""
              }
            />
            <SummaryRow
              label="Submitted"
              value={result?.submitted_at ? formatDate(result.submitted_at) : ""}
            />
          </dl>
        </section>

        <section
          aria-labelledby="buyer-heading"
          className="rounded-2xl border border-border-default bg-surface p-4 shadow-card sm:p-5"
        >
          <h2 id="buyer-heading" className="text-base font-bold text-content">
            Questions? Contact the buyer
          </h2>
          <ul className="mt-3 space-y-3 text-sm leading-6">
            <li>
              <span className="block text-xs uppercase tracking-wide text-subtle">
                Company
              </span>
              <span className="font-semibold text-content">
                {preview?.buyer_company || "—"}
              </span>
            </li>
            {preview?.buyer_contact_email ? (
              <li>
                <span className="block text-xs uppercase tracking-wide text-subtle">
                  Email
                </span>
                <a
                  className="flex min-h-[44px] items-center break-all font-semibold text-primary underline"
                  href={`mailto:${preview.buyer_contact_email}?subject=${encodeURIComponent(
                    `Quote ${reference || ""}`.trim()
                  )}`}
                >
                  {preview.buyer_contact_email}
                </a>
              </li>
            ) : null}
            {preview?.buyer_contact_phone ? (
              <li>
                <span className="block text-xs uppercase tracking-wide text-subtle">
                  Phone
                </span>
                <a
                  className="flex min-h-[44px] items-center font-semibold text-primary underline"
                  href={`tel:${String(preview.buyer_contact_phone).replace(/\s+/g, "")}`}
                >
                  {preview.buyer_contact_phone}
                </a>
              </li>
            ) : null}
          </ul>
        </section>

        <div className="flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            onClick={onRevise}
            className="min-h-[52px] flex-1 rounded-xl bg-primary px-5 text-base font-semibold text-primary-fg transition-colors hover:bg-primary-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Submit a revised quote
          </button>
          <button
            type="button"
            onClick={handleDownload}
            className="min-h-[52px] flex-1 rounded-xl border border-border-strong bg-surface px-5 text-base font-semibold text-content transition-colors hover:bg-surface-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Download a copy
          </button>
        </div>

        <p className="text-center text-xs text-muted" aria-live="polite">
          {isExpired
            ? "This quote link has now expired. Contact the buyer if you need to change anything."
            : expiresAt
              ? `This link stays active until ${formatDateTime(expiresAt)} — you can update your quote until then.`
              : "Keep the link from your invitation email to update your quote later."}
        </p>
      </main>
    </div>
  );
}

function SummaryRow({ label, value }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-border-default pb-1.5">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right font-semibold text-content">
        {value ? value : <span className="text-subtle">Not provided</span>}
      </dd>
    </div>
  );
}
