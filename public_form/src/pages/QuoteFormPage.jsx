import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import BrandedHeader from "@/components/BrandedHeader";
import Captcha from "@/components/Captcha";
import ConfirmDialog from "@/components/ConfirmDialog";
import { TextAreaField, TextField } from "@/components/Field";
import FileUpload from "@/components/FileUpload";
import Honeypot from "@/components/Honeypot";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import Notice from "@/components/Notice";
import ProgressNotice from "@/components/ProgressNotice";
import ConfirmationPage from "@/pages/ConfirmationPage";
import ErrorPage from "@/pages/ErrorPage";
import {
  ApiError,
  ERROR_KINDS,
  describeApiError,
  fetchInvitation,
  fetchPublicConfig,
  submitQuote,
  uploadAttachment,
} from "@/lib/api";
import { isCaptchaEnabled } from "@/lib/captcha";
import {
  CURRENCY_CODES,
  FIELD_LABELS,
  INCOTERMS,
  isValidEmail,
  isValidIsoDate,
} from "@/lib/format";

/**
 * Every text field the API accepts, in the order suppliers expect to fill them.
 * A blank string is a legal value: the API stores the quote and flags it
 * "incomplete", which is why blanks are never a hard error here.
 */
const BLANK_FORM = {
  supplier_name: "",
  contact_name: "",
  contact_email: "",
  currency: "",
  unit_price: "",
  unit: "",
  lead_time: "",
  moq: "",
  payment_terms: "",
  incoterms: "",
  validity_date: "",
  warranty_months: "",
  shipping_cost: "",
  duties: "",
  taxes: "",
  discount: "",
  notes: "",
};

const DEFAULT_MAX_UPLOAD_MB = 10;

let rowSequence = 0;
function nextRowId() {
  rowSequence += 1;
  return `attachment-${rowSequence}`;
}

/**
 * Seeds the form from the invitation. Only fields the server actually sends are
 * prefilled — an empty string from the server stays empty rather than being
 * invented from product defaults, so the supplier is never shown a price or a
 * currency the buyer did not ask about.
 */
function prefillFromPreview(preview) {
  return {
    ...BLANK_FORM,
    supplier_name: preview?.supplier_name ?? "",
    contact_name: preview?.contact_name ?? "",
    contact_email: preview?.contact_email ?? "",
    currency: preview?.currency ?? "",
    unit: preview?.unit ?? "",
    incoterms: preview?.incoterms ?? "",
  };
}

export default function QuoteFormPage() {
  const { rfqId, token } = useParams();

  const [phase, setPhase] = useState("loading");
  const [loadError, setLoadError] = useState(null);
  const [preview, setPreview] = useState(null);
  const [publicConfig, setPublicConfig] = useState(null);

  const [form, setForm] = useState(BLANK_FORM);
  const [errors, setErrors] = useState({});
  const [warnedKeys, setWarnedKeys] = useState([]);
  const [rows, setRows] = useState([]);
  const [pendingIssues, setPendingIssues] = useState(null);
  const [captchaState, setCaptchaState] = useState({ token: null, resetKey: 0 });
  const [submitState, setSubmitState] = useState({ status: "idle", message: "" });
  const [result, setResult] = useState(null);
  const submittedPayloadRef = useRef(null);

  /* ---------------------------------------------------------------- loading */

  const load = useCallback(async () => {
    if (!rfqId || !token) {
      setLoadError(
        new ApiError("This quote link is not valid.", {
          kind: ERROR_KINDS.INVALID_LINK,
        })
      );
      setPhase("error");
      return;
    }

    setPhase("loading");
    setLoadError(null);

    try {
      // The preview is the source of truth. /public/config is fetched in
      // parallel as a fallback for policy values (limits, extensions, captcha)
      // and its failure is swallowed: server-owned policy must never be a
      // reason the supplier cannot see their quote request.
      const [invitation, config] = await Promise.all([
        fetchInvitation(rfqId, token),
        fetchPublicConfig().catch(() => null),
      ]);

      setPreview(invitation);
      setPublicConfig(config);
      setForm(prefillFromPreview(invitation));
      setErrors({});
      setWarnedKeys([]);
      setRows([]);
      setPhase("ready");
    } catch (error) {
      if (error?.kind === ERROR_KINDS.ABORTED) return;
      setLoadError(error);
      setPhase("error");
    }
  }, [rfqId, token]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (preview?.buyer_company) {
      document.title = `Submit your quote — ${preview.buyer_company}`;
    }
  }, [preview]);

  /* ------------------------------------------------------------ derived config */

  const requiredKeys = useMemo(
    () => (Array.isArray(preview?.required_fields) ? preview.required_fields : []),
    [preview]
  );
  const requiredSet = useMemo(() => new Set(requiredKeys), [requiredKeys]);

  const maxUploadMb =
    Number(preview?.max_upload_mb) ||
    Number(publicConfig?.max_upload_mb) ||
    DEFAULT_MAX_UPLOAD_MB;

  const allowedExtensions = useMemo(() => {
    const fromPreview = preview?.allowed_upload_extensions;
    if (Array.isArray(fromPreview) && fromPreview.length) return fromPreview;
    const fromConfig = publicConfig?.allowed_upload_extensions;
    if (Array.isArray(fromConfig) && fromConfig.length) return fromConfig;
    return [];
  }, [preview, publicConfig]);

  const honeypotField =
    preview?.honeypot_field ||
    publicConfig?.spam_protection?.honeypot_field ||
    "company_website";

  /**
   * CAPTCHA settings come from the API, not the build. The preview wins when it
   * actually enables one; otherwise /public/config is consulted. Provider "none"
   * means no widget is rendered at all and the form works unchanged.
   */
  const captcha = useMemo(() => {
    const fromPreview = {
      provider: preview?.captcha_provider ?? "none",
      site_key: preview?.captcha_site_key ?? null,
    };
    if (isCaptchaEnabled(fromPreview)) return fromPreview;

    const fromConfig = publicConfig?.captcha;
    if (isCaptchaEnabled(fromConfig)) return fromConfig;

    return { provider: "none", site_key: null };
  }, [preview, publicConfig]);

  const captchaToken = captchaState.token;

  /* ------------------------------------------------------------------ fields */

  function handleValueChange(name, value) {
    setForm((previous) => ({ ...previous, [name]: value }));
    // Clear a shape error as soon as the supplier starts fixing it; they should
    // not have to submit again to see it disappear.
    setErrors((previous) => {
      if (!previous[name]) return previous;
      const next = { ...previous };
      delete next[name];
      return next;
    });
  }

  function hintFor(key, base) {
    const blank = String(form[key] ?? "").trim() === "";
    if (warnedKeys.includes(key) && blank) {
      return base
        ? `${base} Still blank — you can send it anyway and the buyer will follow up by email.`
        : "Still blank — you can send it anyway and the buyer will follow up by email.";
    }
    return base;
  }

  function fieldProps(key, extra = {}) {
    return {
      id: `q-${key}`,
      name: key,
      value: form[key],
      onValueChange: handleValueChange,
      required: requiredSet.has(key),
      error: errors[key],
      ...extra,
    };
  }

  /* -------------------------------------------------------------- attachments */

  const uploadRow = useCallback(
    async (rowId, file) => {
      setRows((previous) =>
        previous.map((row) =>
          row.id === rowId
            ? { ...row, status: "uploading", progress: 0, error: null }
            : row
        )
      );

      try {
        const created = await uploadAttachment(rfqId, token, file, {
          onProgress: (percent) =>
            setRows((previous) =>
              previous.map((row) =>
                row.id === rowId ? { ...row, progress: percent } : row
              )
            ),
        });

        if (!created?.key) {
          // Without a key we cannot reference the file in the quote. Treating
          // this as a failed upload is honest: submitting silently would drop
          // the document the supplier believes they sent.
          throw new ApiError(
            "The server did not confirm this file. Please try again.",
            { kind: ERROR_KINDS.SERVER }
          );
        }

        setRows((previous) =>
          previous.map((row) =>
            row.id === rowId
              ? {
                  ...row,
                  status: "uploaded",
                  progress: 100,
                  key: created.key,
                  error: null,
                }
              : row
          )
        );
      } catch (error) {
        if (error?.kind === ERROR_KINDS.ABORTED) return;
        setRows((previous) =>
          previous.map((row) =>
            row.id === rowId
              ? {
                  ...row,
                  status: "error",
                  progress: 0,
                  key: null,
                  error:
                    error?.message ||
                    "This file could not be uploaded. Please try again.",
                }
              : row
          )
        );
      }
    },
    [rfqId, token]
  );

  const handleFilesPicked = useCallback(
    (accepted, rejected) => {
      const additions = [];

      for (const file of accepted) {
        const row = {
          id: nextRowId(),
          name: file.name,
          size: file.size,
          file,
          status: "uploading",
          progress: 0,
          key: null,
          error: null,
        };
        additions.push(row);
      }

      // Rejected files stay in the list as failed rows with the reason, rather
      // than vanishing — a supplier who picked the wrong file needs to see why.
      for (const { name, message } of rejected) {
        additions.push({
          id: nextRowId(),
          name,
          size: 0,
          file: null,
          status: "error",
          progress: 0,
          key: null,
          error: message,
        });
      }

      if (additions.length === 0) return;
      setRows((previous) => [...previous, ...additions]);

      for (const row of additions) {
        if (row.file) void uploadRow(row.id, row.file);
      }
    },
    [uploadRow]
  );

  const handleRemoveRow = useCallback((rowId) => {
    // The API contract has no delete endpoint, so removing a file only drops its
    // key from this submission. The object may remain in the buyer's storage
    // until the invitation is cleaned up; that is stated plainly rather than
    // promising a deletion we cannot perform.
    setRows((previous) => previous.filter((row) => row.id !== rowId));
  }, []);

  const handleRetryRow = useCallback(
    (rowId) => {
      const row = rows.find((candidate) => candidate.id === rowId);
      if (row?.file) void uploadRow(row.id, row.file);
    },
    [rows, uploadRow]
  );

  /* ------------------------------------------------------------------ submit */

  function buildPayload() {
    const payload = {};
    for (const key of Object.keys(BLANK_FORM)) {
      // Blanks are sent as "" — the server tolerates them for optional fields
      // and records the quote as "incomplete", which is a legitimate outcome.
      payload[key] = String(form[key] ?? "").trim();
    }

    payload[honeypotField] = ""; // Honeypot: always present, always empty.
    payload.captcha_token = captchaToken || null;
    payload.attachment_keys = rows
      .filter((row) => row.status === "uploaded" && row.key)
      .map((row) => row.key);

    return payload;
  }

  /**
   * Shape checks only. A blank *required* field is never a blocking error here:
   * it is collected into the confirmation dialog, because the API accepts a
   * partial quote and the buyer prefers a missing MOQ over no quote at all.
   */
  function shapeErrors() {
    const found = {};
    const email = String(form.contact_email ?? "").trim();
    if (email && !isValidEmail(email)) {
      found.contact_email =
        "Enter a valid email address, for example name@company.com";
    }
    const validity = String(form.validity_date ?? "").trim();
    if (validity && !isValidIsoDate(validity)) {
      found.validity_date = "Enter a valid date (day, month and year).";
    }
    return found;
  }

  async function sendQuote(payload) {
    setSubmitState({ status: "submitting", message: "Sending your quote…" });
    try {
      const response = await submitQuote(rfqId, token, payload);
      submittedPayloadRef.current = payload;
      setResult(response);
      setSubmitState({ status: "success", message: "Your quote has been sent." });
      window.scrollTo({ top: 0, behavior: "auto" });
    } catch (error) {
      if (error?.kind === ERROR_KINDS.ABORTED) return;
      setSubmitState({
        status: "error",
        message: error?.message || "We could not send your quote. Please try again.",
      });
      // CAPTCHA tokens are single-use: force a fresh widget so a retry can
      // actually succeed.
      setCaptchaState((previous) => ({
        token: null,
        resetKey: previous.resetKey + 1,
      }));
      // The link died (expired or revoked) while the supplier was typing. Reload
      // so they get the blocking notice instead of an unusable form.
      if (
        error?.kind === ERROR_KINDS.EXPIRED ||
        error?.kind === ERROR_KINDS.INVALID_LINK
      ) {
        void load();
      }
    }
  }

  function handleSubmit(event) {
    event.preventDefault();

    const found = shapeErrors();
    setErrors(found);

    const missingKeys = requiredKeys.filter(
      (key) => String(form[key] ?? "").trim() === ""
    );
    setWarnedKeys(missingKeys);

    if (Object.keys(found).length > 0) {
      setSubmitState({
        status: "error",
        message: "Please correct the highlighted fields, then send again.",
      });
      const firstKey = Object.keys(found)[0];
      const element = document.getElementById(`q-${firstKey}`);
      element?.focus();
      element?.scrollIntoView({ block: "center", behavior: "smooth" });
      return;
    }

    if (rows.some((row) => row.status === "uploading")) {
      setSubmitState({
        status: "error",
        message: "Please wait for the file upload to finish before sending.",
      });
      return;
    }

    const failedRows = rows.filter((row) => row.status === "error" && row.file);

    if (missingKeys.length > 0 || failedRows.length > 0) {
      // Warn once, then let the supplier decide. This is the "partial quote"
      // path the API is designed around.
      setPendingIssues({ missingKeys, failedRows });
      return;
    }

    void sendQuote(buildPayload());
  }

  function handleConfirmPartial() {
    const issues = pendingIssues;
    setPendingIssues(null);
    if (!issues) return;
    void sendQuote(buildPayload());
  }

  function handleRevise() {
    // The form state was never discarded, so returning here hands the supplier
    // back exactly what they typed — the server amends the existing quote for
    // this token instead of creating a duplicate.
    setResult(null);
    submittedPayloadRef.current = null;
    setSubmitState({ status: "idle", message: "" });
    setCaptchaState((previous) => ({
      token: null,
      resetKey: previous.resetKey + 1,
    }));
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  /* ------------------------------------------------------------------ render */

  if (phase === "loading") return <LoadingSkeleton />;

  if (phase === "error") {
    const described = describeApiError(loadError);
    return (
      <ErrorPage
        tone={described.tone}
        title={described.title}
        message={described.message}
        // Every load failure offers a retry, even the ones we do not expect to
        // succeed on the second attempt: the link may have been fixed in the
        // supplier's email client, and a backend restart can briefly return a
        // 404 for a perfectly valid token. Retrying is free for the supplier.
        onRetry={load}
      />
    );
  }

  if (preview?.is_expired) {
    // Blocking notice with the buyer's details and no form: accepting a quote we
    // know the server will reject would be worse than refusing it clearly.
    return (
      <ErrorPage
        tone="warning"
        title="This quote link has expired"
        message={
          preview.expires_at
            ? "This invitation closed on the date shown below, so it can no longer accept a quote. Please contact the buyer if you would still like to quote."
            : "This invitation can no longer accept a quote. Please contact the buyer if you would still like to quote."
        }
        buyerPreview={preview}
      />
    );
  }

  if (result) {
    return (
      <ConfirmationPage
        preview={preview}
        result={result}
        payload={submittedPayloadRef.current}
        rfqId={rfqId}
        token={token}
        onRevise={handleRevise}
      />
    );
  }

  const submitLabel = preview?.already_submitted
    ? "Update my quote"
    : "Submit my quote";
  const submitting = submitState.status === "submitting";
  const showCaptchaNudge = isCaptchaEnabled(captcha) && !captchaToken;

  return (
    <div className="min-h-screen">
      <BrandedHeader preview={preview} />

      <main className="mx-auto w-full max-w-2xl px-4 pb-8 pt-4">
        {preview?.already_submitted ? (
          <Notice tone="info" className="mb-4" live>
            You have already submitted a quote with this link. Submitting again
            will update it.
          </Notice>
        ) : null}

        <ProgressNotice
          currentStep={0}
          requiredKeys={requiredKeys}
          values={form}
          itemName={preview?.item_name}
        />

        {/*
          `noValidate`: the browser's own validation UI would block a partial
          submission, which is exactly what we must allow. Our own checks are
          gentler (shape errors block, blanks only warn).
        */}
        <form onSubmit={handleSubmit} noValidate className="mt-4 space-y-4">
          <datalist id="currency-options">
            {CURRENCY_CODES.map((code) => (
              <option key={code} value={code} />
            ))}
          </datalist>
          <datalist id="incoterm-options">
            {INCOTERMS.map((term) => (
              <option key={term} value={term} />
            ))}
          </datalist>

          <section
            aria-labelledby="details-heading"
            className="rounded-2xl border border-border-default bg-surface p-4 shadow-card sm:p-5"
          >
            <h2 id="details-heading" className="text-base font-bold text-content">
              Who is quoting
            </h2>
            <p className="mt-1 text-sm text-muted">
              The buyer sees this on your quote, so use the name they know you by.
            </p>

            <div className="mt-4 space-y-4">
              <TextField
                label="Company name"
                placeholder="e.g. Nova Metals Ltd"
                autoComplete="organization"
                {...fieldProps("supplier_name", {
                  hint: hintFor("supplier_name"),
                })}
              />
              <TextField
                label="Contact name"
                placeholder="e.g. Ana Ruiz"
                autoComplete="name"
                {...fieldProps("contact_name", { hint: hintFor("contact_name") })}
              />
              <TextField
                label="Contact email"
                type="email"
                inputMode="email"
                autoComplete="email"
                placeholder="e.g. ana@novametals.com"
                {...fieldProps("contact_email", {
                  hint: hintFor(
                    "contact_email",
                    "The buyer sends any follow-up questions here."
                  ),
                })}
              />
            </div>
          </section>

          <section
            aria-labelledby="price-heading"
            className="rounded-2xl border border-border-default bg-surface p-4 shadow-card sm:p-5"
          >
            <h2 id="price-heading" className="text-base font-bold text-content">
              Your price
            </h2>
            <p className="mt-1 text-sm text-muted">
              Give the price for one unit. The buyer multiplies it by the
              quantity themselves.
            </p>

            <div className="mt-4 space-y-4">
              <TextField
                label="Currency"
                list="currency-options"
                placeholder="USD"
                autoComplete="off"
                hint={hintFor(
                  "currency",
                  "Three-letter code, such as USD, EUR or VND."
                )}
                maxLength={12}
                {...fieldProps("currency")}
              />
              <TextField
                label="Unit price"
                inputMode="decimal"
                placeholder="e.g. 2.50"
                autoComplete="off"
                prefix={String(form.currency || "").trim().toUpperCase() || undefined}
                {...fieldProps("unit_price", {
                  hint: hintFor(
                    "unit_price",
                    `Price for one ${String(form.unit || "").trim() || "unit"}, before shipping.`
                  ),
                })}
              />
              <TextField
                label="Unit of measure"
                placeholder="e.g. pcs, kg, m"
                autoComplete="off"
                maxLength={24}
                {...fieldProps("unit", { hint: hintFor("unit") })}
              />
              <TextField
                label="Lead time"
                placeholder="e.g. 3 weeks or 15 business days"
                autoComplete="off"
                {...fieldProps("lead_time", {
                  hint: hintFor(
                    "lead_time",
                    "How long after the order until the goods ship."
                  ),
                })}
              />
            </div>
          </section>

          <section
            aria-labelledby="terms-heading"
            className="rounded-2xl border border-border-default bg-surface p-4 shadow-card sm:p-5"
          >
            <h2 id="terms-heading" className="text-base font-bold text-content">
              Order terms
            </h2>
            <p className="mt-1 text-sm text-muted">
              Buyers compare quotes on these details, so fill in as many as you
              can.
            </p>

            <div className="mt-4 space-y-4">
              <TextField
                label="Minimum order quantity"
                inputMode="numeric"
                placeholder="e.g. 500"
                autoComplete="off"
                maxLength={32}
                {...fieldProps("moq", { hint: hintFor("moq") })}
              />
              <TextField
                label="Payment terms"
                placeholder="e.g. Net 30"
                autoComplete="off"
                maxLength={120}
                {...fieldProps("payment_terms", { hint: hintFor("payment_terms") })}
              />
              <TextField
                label="Incoterms"
                list="incoterm-options"
                placeholder="e.g. FOB Valencia"
                autoComplete="off"
                maxLength={60}
                {...fieldProps("incoterms", {
                  hint: hintFor(
                    "incoterms",
                    "Delivery term, optionally with the named place."
                  ),
                })}
              />
              <TextField
                label="Quote valid until"
                type="date"
                autoComplete="off"
                {...fieldProps("validity_date", {
                  hint: hintFor(
                    "validity_date",
                    "How long these prices hold."
                  ),
                })}
              />
              <TextField
                label="Warranty (months)"
                inputMode="numeric"
                placeholder="e.g. 12"
                autoComplete="off"
                maxLength={12}
                {...fieldProps("warranty_months", {
                  hint: hintFor("warranty_months"),
                })}
              />
            </div>
          </section>

          {/*
            Native <details> on purpose: it is keyboard- and screen-reader-
            accessible with no JavaScript, and leaving it uncontrolled means the
            supplier's open/closed choice survives re-renders.
          */}
          <details className="rounded-2xl border border-border-default bg-surface p-4 shadow-card sm:p-5">
            <summary className="flex min-h-[44px] cursor-pointer items-center justify-between gap-3 text-base font-bold text-content">
              Additional costs
              <span className="text-xs font-medium text-muted">
                optional
              </span>
            </summary>
            <p className="mt-2 text-sm text-muted">
              Only fill these in if they are not already included in your unit
              price — leaving them blank means the unit price is the total.
            </p>

            <div className="mt-4 space-y-4">
              <TextField
                label="Shipping cost"
                inputMode="decimal"
                placeholder="e.g. 450"
                autoComplete="off"
                maxLength={40}
                {...fieldProps("shipping_cost")}
              />
              <TextField
                label="Duties"
                inputMode="decimal"
                placeholder="e.g. 120"
                autoComplete="off"
                maxLength={40}
                {...fieldProps("duties")}
              />
              <TextField
                label="Taxes"
                inputMode="decimal"
                placeholder="e.g. VAT 20%"
                autoComplete="off"
                maxLength={40}
                {...fieldProps("taxes")}
              />
              <TextField
                label="Discount"
                inputMode="decimal"
                placeholder="e.g. 2% for orders over 5000"
                autoComplete="off"
                maxLength={60}
                {...fieldProps("discount")}
              />
            </div>
          </details>

          <section
            aria-labelledby="notes-heading"
            className="rounded-2xl border border-border-default bg-surface p-4 shadow-card sm:p-5"
          >
            <h2 id="notes-heading" className="text-base font-bold text-content">
              Notes for the buyer
            </h2>
            <div className="mt-4">
              <TextAreaField
                label="Anything else they should know"
                placeholder="Alternatives, tolerances, packing, certifications, payment notes…"
                rows={5}
                maxLength={4000}
                {...fieldProps("notes", { hint: hintFor("notes") })}
              />
            </div>
          </section>

          <section
            aria-labelledby="files-heading"
            className="rounded-2xl border border-border-default bg-surface p-4 shadow-card sm:p-5"
          >
            <h2 id="files-heading" className="text-base font-bold text-content">
              Attachments
            </h2>
            <p className="mt-1 text-sm text-muted">
              Datasheets, drawings or certificates help the buyer compare fairly.
              You can also send your quote without any files.
            </p>
            <div className="mt-4">
              <FileUpload
                rows={rows}
                onFilesPicked={handleFilesPicked}
                onRemove={handleRemoveRow}
                onRetry={handleRetryRow}
                maxUploadMb={maxUploadMb}
                allowedExtensions={allowedExtensions}
                disabled={submitting}
              />
            </div>
          </section>

          {isCaptchaEnabled(captcha) ? (
            <section
              aria-labelledby="captcha-heading"
              className="rounded-2xl border border-border-default bg-surface p-4 shadow-card sm:p-5"
            >
              <h2
                id="captcha-heading"
                className="text-base font-bold text-content"
              >
                Quick verification
              </h2>
              <p className="mt-1 text-sm text-muted">
                This check keeps automated spam out of the buyer&rsquo;s inbox.
              </p>
              <div className="mt-4">
                <Captcha
                  captcha={captcha}
                  resetKey={captchaState.resetKey}
                  onToken={(value) =>
                    setCaptchaState((previous) => ({
                      ...previous,
                      token: value || null,
                    }))
                  }
                />
              </div>
            </section>
          ) : null}

          {/* Spam honeypot: see components/Honeypot.jsx for why it is styled
              this way. It is rendered inside the form so a bot's clicking and
              form-filling heuristics meet it, and it is never submitted with a
              value the supplier typed. */}
          <Honeypot fieldName={honeypotField} />

          {showCaptchaNudge ? (
            <Notice tone="warning">
              Please finish the verification above before sending — it is the
              only thing the buyer&rsquo;s spam filter insists on.
            </Notice>
          ) : null}

          {/*
            Sticky action bar. On a phone the supplier's thumb lives at the
            bottom of the screen, so the primary action stays reachable without
            scrolling back through seventeen fields. It becomes a normal
            in-flow block from `sm` up, where the whole form is visible at once.
          */}
          <div
            className="sticky bottom-0 z-20 -mx-4 mt-2 border-t border-border-default bg-bg px-4 pt-3 sm:static sm:mx-0 sm:rounded-2xl sm:border sm:border-border-default sm:bg-surface sm:p-4"
            style={{ paddingBottom: "calc(0.75rem + var(--safe-bottom))" }}
          >
            <p
              aria-live="polite"
              className={[
                "mb-2 text-sm font-medium",
                submitState.status === "error"
                  ? "text-danger-soft-fg"
                  : submitState.status === "success"
                    ? "text-success-soft-fg"
                    : "text-muted",
              ].join(" ")}
            >
              {submitState.message}
            </p>

            <button
              type="submit"
              disabled={submitting}
              className="min-h-[52px] w-full rounded-xl bg-primary px-5 text-base font-semibold text-primary-fg transition-colors hover:bg-primary-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-70"
            >
              {submitting ? "Sending…" : submitLabel}
            </button>
            <p className="mt-2 text-center text-xs text-muted">
              {requiredSet.size > 0
                ? "Fields marked * are what the buyer needs. You can still send a partial quote — they will follow up by email."
                : "You can send this quote as it is."}
            </p>
          </div>
        </form>

        <p className="mt-6 text-center text-xs text-subtle">
          Supplier Quote Autopilot — your quote goes straight to{" "}
          {preview?.buyer_company || "the buyer"}.
        </p>
      </main>

      <ConfirmDialog
        open={Boolean(pendingIssues)}
        title="Send this quote as it is?"
        confirmLabel="Yes, send it"
        cancelLabel="Go back and complete it"
        busy={submitting}
        onConfirm={handleConfirmPartial}
        onCancel={() => setPendingIssues(null)}
      >
        {pendingIssues?.missingKeys?.length ? (
          <p>
            You have left{" "}
            <strong className="font-semibold text-content">
              {pendingIssues.missingKeys.length} required field
              {pendingIssues.missingKeys.length === 1 ? "" : "s"}
            </strong>{" "}
            blank
            {pendingIssues.missingKeys.length > 0
              ? ` (${pendingIssues.missingKeys
                  .map((key) => FIELD_LABELS[key] || key.replace(/_/g, " "))
                  .join(", ")})`
              : ""}
            . We will send the quote and the buyer will follow up by email.
          </p>
        ) : null}
        {pendingIssues?.failedRows?.length ? (
          <p>
            {pendingIssues.failedRows.length} file
            {pendingIssues.failedRows.length === 1 ? "" : "s"} did not finish
            uploading and will not be attached. You can remove them and send the
            quote, or go back and retry.
          </p>
        ) : null}
        <p>You can update the quote later with the same link.</p>
      </ConfirmDialog>
    </div>
  );
}
