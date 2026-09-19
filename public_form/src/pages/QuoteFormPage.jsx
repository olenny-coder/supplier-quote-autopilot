import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import AccreditationField from "@/components/AccreditationField";
import BrandedHeader from "@/components/BrandedHeader";
import Captcha from "@/components/Captcha";
import ConfirmDialog from "@/components/ConfirmDialog";
import { SelectField, TextAreaField, TextField } from "@/components/Field";
import FileUpload from "@/components/FileUpload";
import FormSection from "@/components/FormSection";
import Honeypot from "@/components/Honeypot";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import Notice from "@/components/Notice";
import ProgressNotice from "@/components/ProgressNotice";
import SiteScopeCard from "@/components/SiteScopeCard";
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
  COMMON_ACCREDITATIONS,
  CURRENCY_CODES,
  FIELD_LABELS,
  INCOTERMS,
  fieldKeyForRequiredKey,
  formatDecimalInput,
  hasAnswer,
  isValidEmail,
  isValidIsoDate,
  numberOrNull,
  rateBasesFor,
  requiredKeyForFieldKey,
  withCurrentOption,
} from "@/lib/format";

/**
 * Every value the API accepts, in the order a contractor thinks about them.
 *
 * A blank is a legal value everywhere: the API stores the quote and flags it
 * "incomplete", which is why blanks are never a hard error here. Multi-selects use
 * an empty array as their blank, matching the contract.
 */
const BLANK_FORM = {
  // who is quoting
  supplier_name: "",
  contact_name: "",
  contact_email: "",
  // your rate
  unit_price: "",
  currency: "",
  unit: "",
  // speed
  response_time_hours: "",
  lead_time: "",
  // commercial terms
  callout_charge: "",
  labour_rate: "",
  materials_markup_pct: "",
  payment_terms: "",
  validity_date: "",
  // compliance and tax
  compliance_accreditations: [],
  gst_rate: "",
  // goods-only, hidden for a services RFQ and submitted as blanks
  moq: "",
  incoterms: "",
  warranty_months: "",
  shipping_cost: "",
  duties: "",
  taxes: "",
  discount: "",
  // notes
  notes: "",
};

/** The goods-only group, hidden entirely for a services RFQ. */
const GOODS_ONLY_KEYS = [
  "moq",
  "incoterms",
  "warranty_months",
  "shipping_cost",
  "duties",
  "taxes",
  "discount",
];

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
 *
 * The two exceptions are both explicit buyer instructions rather than product
 * defaults: the RFQ's own currency (SGD for Singapore work) and its GST rate.
 */
function prefillFromPreview(preview) {
  const requiredAccreditations = (
    Array.isArray(preview?.required_accreditations)
      ? preview.required_accreditations
      : []
  )
    .map((entry) => String(entry ?? "").trim())
    .filter(Boolean);

  return {
    ...BLANK_FORM,
    supplier_name: preview?.supplier_name ?? "",
    contact_name: preview?.contact_name ?? "",
    contact_email: preview?.contact_email ?? "",
    currency: preview?.currency ?? "",
    unit: preview?.unit ?? "",
    incoterms: preview?.incoterms ?? "",
    // The rate arrives as a string ("9.00"); it is parsed before it is shown.
    gst_rate: formatDecimalInput(preview?.gst_rate),
    // Pre-ticking what the buyer requires is the whole point of the field: the
    // contractor sees exactly which licences are being asked for and only has to
    // untick what they do not hold.
    compliance_accreditations: [...requiredAccreditations],
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

  /**
   * The buyer's contract, as sent. `required_fields` holds the buyer's own field
   * keys and `required_field_labels` is the same list in the same order, phrased
   * for a supplier. Both are used as the server sends them: labels are never
   * composed here, so adding a field stays a backend-only change.
   */
  const requiredKeys = useMemo(
    () => (Array.isArray(preview?.required_fields) ? preview.required_fields : []),
    [preview]
  );
  const requiredSet = useMemo(() => new Set(requiredKeys), [requiredKeys]);
  const requiredLabels = useMemo(
    () =>
      Array.isArray(preview?.required_field_labels)
        ? preview.required_field_labels
        : [],
    [preview]
  );

  const procurementType = preview?.procurement_type || "";
  // Anything that is not explicitly goods is treated as services: that is the
  // product this form exists for, and the services layout is the safe default for
  // a link whose type we somehow do not know.
  const isService = procurementType !== "goods";

  const requiredAccreditations = useMemo(
    () =>
      Array.isArray(preview?.required_accreditations)
        ? preview.required_accreditations
        : [],
    [preview]
  );

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
  // Declared here, above `fieldProps`, so the controls can be disabled while a
  // submission is in flight without relying on declaration order inside render.
  const submitting = submitState.status === "submitting";

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

  /** The buyer's requirement, phrased the way a supplier reads it. */
  function labelForRequiredKey(key) {
    const index = requiredKeys.indexOf(key);
    const fromServer = index >= 0 ? requiredLabels[index] : "";
    // The server's labels are authoritative. The local table is only a fallback
    // for a response that carries the keys but not the labels yet.
    return String(fromServer || FIELD_LABELS[key] || key.replace(/_/g, " "));
  }

  function hintFor(fieldKey, base) {
    const requiredKey = requiredKeyForFieldKey(fieldKey);
    if (warnedKeys.includes(requiredKey) && !hasAnswer(form[fieldKey])) {
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
      // Required markers are driven by the buyer's contract and rendered as a
      // visual marker plus `aria-required` — never the HTML `required` attribute,
      // which would make the browser block the partial submissions the API
      // deliberately accepts. See components/Field.jsx.
      required: requiredSet.has(requiredKeyForFieldKey(key)),
      error: errors[key],
      disabled: submitting,
      ...extra,
    };
  }

  /* ------------------------------------------------------------ services copy */

  const currencyCode = String(form.currency || "").trim().toUpperCase();
  // The live value, falling back to the RFQ's own basis: when a contractor
  // switches from "per hour" to "lump sum" the label must follow what they are
  // actually quoting, not what the buyer originally suggested.
  const rateBasis =
    String(form.unit || "").trim() || String(preview?.unit || "").trim();

  const rateLabel = isService
    ? rateBasis
      ? `Rate (${rateBasis})`
      : "Rate"
    : "Unit price";
  const rateHint = isService
    ? `What you would charge ${rateBasis || "for this job"}. Note in the notes whether materials are included.`
    : `Price for one ${rateBasis || "unit"}, before shipping.`;

  const rateBasisOptions = useMemo(() => {
    // The picker's vocabulary is the server's (`rate_bases`), so adding a rate
    // basis stays a backend-only change. The local taxonomy is only the fallback
    // for a response that predates that field.
    const fromServer =
      Array.isArray(preview?.rate_bases) && preview.rate_bases.length
        ? preview.rate_bases
        : rateBasesFor(procurementType);
    return withCurrentOption(fromServer, rateBasis);
  }, [preview, procurementType, rateBasis]);

  const requiredResponseHours = numberOrNull(preview?.required_response_hours);
  const enteredResponseHours = numberOrNull(form.response_time_hours);
  const responseIsSlower =
    requiredResponseHours !== null &&
    enteredResponseHours !== null &&
    enteredResponseHours > requiredResponseHours;
  const responseHint = [
    "e.g. 4 for within 4 hours, 24 for next business day.",
    requiredResponseHours !== null
      ? `The buyer asks for someone on site within ${requiredResponseHours} hour${requiredResponseHours === 1 ? "" : "s"}.`
      : "",
  ]
    .filter(Boolean)
    .join(" ");
  // Warn, never block: a slower attendance may be the honest answer, and the buyer
  // would rather have the quote with the real number on it than no quote.
  const responseWarning = responseIsSlower
    ? `That is slower than the ${requiredResponseHours} hour${requiredResponseHours === 1 ? "" : "s"} the buyer asked for. Send it if that is the best you can do — the buyer will see the difference.`
    : undefined;

  const gstLabel = currencyCode === "SGD" ? "GST rate (%)" : "Tax rate (%)";
  // Why the buyer asks for a rate at all, in the buyer's own words when the API
  // sends them (`tax_note`), so the form never invents tax policy.
  const gstHint = [
    "Used when you do not give a separate tax amount.",
    String(preview?.tax_note || "").trim(),
  ]
    .filter(Boolean)
    .join(" ");

  const goodsGroupHoldsRequiredField = GOODS_ONLY_KEYS.some((key) =>
    requiredSet.has(key)
  );

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
      const value = form[key];
      if (Array.isArray(value)) {
        // A multi-select answers with a list, so its blank is `[]` — the same
        // "nothing here" the numeric fields express as "".
        payload[key] = value
          .map((entry) => String(entry ?? "").trim())
          .filter(Boolean);
      } else {
        payload[key] = String(value ?? "").trim();
      }
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

    // The buyer's contract names its own fields ("compliance"), the form posts
    // wire fields ("compliance_accreditations"); lib/format reconciles the two.
    const missing = requiredKeys
      .filter((key) => !hasAnswer(form[fieldKeyForRequiredKey(key)]))
      .map((key) => ({ key, label: labelForRequiredKey(key) }));

    setWarnedKeys(missing.map((entry) => entry.key));

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

    if (missing.length > 0 || failedRows.length > 0) {
      // Warn once, then let the supplier decide. This is the "partial quote"
      // path the API is designed around.
      setPendingIssues({ missing, failedRows });
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
          {!isService ? (
            <datalist id="incoterm-options">
              {INCOTERMS.map((term) => (
                <option key={term} value={term} />
              ))}
            </datalist>
          ) : null}

          <FormSection
            id="who"
            title="Who is quoting"
            description="The buyer sees this on your quote, so use the name they know you by."
          >
            <TextField
              label="Company name"
              placeholder="e.g. Sunrise Facilities Pte Ltd"
              autoComplete="organization"
              {...fieldProps("supplier_name", {
                hint: hintFor("supplier_name"),
              })}
            />
            <TextField
              label="Contact name"
              placeholder="e.g. Suresh Kumar"
              autoComplete="name"
              {...fieldProps("contact_name", { hint: hintFor("contact_name") })}
            />
            <TextField
              label="Contact email"
              type="email"
              inputMode="email"
              autoComplete="email"
              placeholder="e.g. suresh@sunrise.sg"
              {...fieldProps("contact_email", {
                hint: hintFor(
                  "contact_email",
                  "The buyer sends any follow-up questions here."
                ),
              })}
            />
          </FormSection>

          <FormSection
            id="rate"
            title="Your rate"
            description={
              isService
                ? "The rate you would charge, and what it is charged against. The buyer compares quotes on exactly this."
                : "Give the price for one unit. The buyer multiplies it by the quantity themselves."
            }
          >
            <TextField
              label={rateLabel}
              inputMode="decimal"
              placeholder="e.g. 80.00"
              autoComplete="off"
              prefix={currencyCode || undefined}
              {...fieldProps("unit_price", {
                hint: hintFor("unit_price", rateHint),
              })}
            />
            <TextField
              label="Currency"
              list="currency-options"
              placeholder={String(preview?.currency || "").trim() || undefined}
              autoComplete="off"
              hint={hintFor(
                "currency",
                "Three-letter code. This request is priced in " +
                  `${String(preview?.currency || "").trim() || "the buyer's currency"}.`
              )}
              maxLength={12}
              {...fieldProps("currency")}
            />
            <SelectField
              label={isService ? "Rate basis" : "Unit of measure"}
              options={rateBasisOptions}
              placeholder={
                isService ? "Choose what the rate is for" : "Choose a unit"
              }
              {...fieldProps("unit", {
                hint: hintFor(
                  "unit",
                  isService
                    ? "What the rate is charged against — a day's work and an hourly rate are not comparable."
                    : "How one unit is counted."
                ),
              })}
            />
          </FormSection>

          <FormSection
            id="speed"
            title="Speed"
            description={
              isService
                ? "Response time is the single biggest difference between two maintenance quotes."
                : "When the buyer would have the goods."
            }
          >
            {isService ? (
              <TextField
                label="How fast can you attend?"
                inputMode="numeric"
                placeholder="e.g. 4"
                autoComplete="off"
                maxLength={12}
                {...fieldProps("response_time_hours", {
                  hint: hintFor("response_time", responseHint),
                  warning: responseWarning,
                })}
              />
            ) : null}
            <TextField
              label={
                isService
                  ? "Mobilisation time (time until you can start)"
                  : "Lead time"
              }
              placeholder={
                isService
                  ? "e.g. next working day, or 2 weeks for a full crew"
                  : "e.g. 3 weeks or 15 business days"
              }
              autoComplete="off"
              {...fieldProps("lead_time", {
                hint: hintFor(
                  "lead_time",
                  isService
                    ? "From the buyer's go-ahead to your team being on site."
                    : "How long after the order until the goods ship."
                ),
              })}
            />
          </FormSection>

          <SiteScopeCard preview={preview} />

          <FormSection
            id="terms"
            title="Commercial terms"
            description={
              isService
                ? "How you charge for the work and when you expect to be paid."
                : "Buyers compare quotes on these details, so fill in as many as you can."
            }
          >
            {isService ? (
              <>
                <TextField
                  label="Callout / attendance charge"
                  inputMode="decimal"
                  placeholder="e.g. 80.00"
                  autoComplete="off"
                  maxLength={40}
                  prefix={currencyCode || undefined}
                  {...fieldProps("callout_charge", {
                    hint: hintFor(
                      "callout_charge",
                      "What you charge to attend site, even if no work is done. Leave blank if it is already inside your rate."
                    ),
                  })}
                />
                <TextField
                  label="Labour rate per hour"
                  inputMode="decimal"
                  placeholder="e.g. 65.00"
                  autoComplete="off"
                  maxLength={40}
                  prefix={currencyCode || undefined}
                  {...fieldProps("labour_rate", {
                    hint: hintFor(
                      "labour_rate",
                      "The hourly rate for the person who attends."
                    ),
                  })}
                />
                <TextField
                  label="Materials markup (%)"
                  inputMode="decimal"
                  placeholder="e.g. 15"
                  autoComplete="off"
                  maxLength={12}
                  {...fieldProps("materials_markup_pct", {
                    hint: hintFor(
                      "materials_markup",
                      "What you add on top of trade prices for parts and materials."
                    ),
                  })}
                />
              </>
            ) : null}
            <TextField
              label="Payment terms"
              placeholder={
                isService ? "e.g. 30 days from invoice" : "e.g. Net 30"
              }
              autoComplete="off"
              maxLength={120}
              {...fieldProps("payment_terms", {
                hint: hintFor(
                  "payment_terms",
                  isService
                    ? "When you expect to be paid after the work is done."
                    : undefined
                ),
              })}
            />
            <TextField
              label="Rates valid until"
              type="date"
              autoComplete="off"
              {...fieldProps("validity_date", {
                hint: hintFor(
                  "validity_date",
                  "How long you can hold these rates."
                ),
              })}
            />
          </FormSection>

          <FormSection
            id="compliance"
            title="Compliance"
            description="Licences and certifications the buyer checks before awarding maintenance work."
          >
            <AccreditationField
              id="q-compliance_accreditations"
              label="Accreditations and licences you hold"
              value={form.compliance_accreditations}
              onChange={(next) =>
                handleValueChange("compliance_accreditations", next)
              }
              suggestions={COMMON_ACCREDITATIONS}
              requiredAccreditations={requiredAccreditations}
              required={requiredSet.has("compliance")}
              disabled={submitting}
            />
          </FormSection>

          <FormSection
            id="tax"
            title="Tax"
            description="Only one of a rate and a separate tax amount is needed — the buyer adds this on top when you give a rate."
          >
            <TextField
              label={gstLabel}
              inputMode="decimal"
              placeholder="e.g. 9"
              autoComplete="off"
              maxLength={12}
              {...fieldProps("gst_rate", {
                hint: hintFor("gst_rate", gstHint),
              })}
            />
          </FormSection>

          {/*
            Goods-only group: MOQ, Incoterms, freight, duties, taxes and discount
            mean nothing on a plumbing job, so the whole group is hidden for a
            services RFQ rather than shown empty. Mobilisation time deliberately
            lives above with the response time, because it is the one time-related
            question a contractor is always asked. Native <details> on purpose: it
            is keyboard- and screen-reader-accessible with no JavaScript, and it is
            opened by default when the buyer made one of these fields required, so
            a required field is never hidden behind a collapsed summary.
          */}
          {!isService ? (
            <details
              open={goodsGroupHoldsRequiredField}
              className="rounded-2xl border border-border-default bg-surface p-4 shadow-card sm:p-5"
            >
              <summary className="flex min-h-[44px] cursor-pointer items-center justify-between gap-3 text-base font-bold text-content">
                Additional details
                <span className="text-xs font-medium text-muted">optional</span>
              </summary>
              <p className="mt-2 text-sm text-muted">
                Only fill these in if they are not already included in your unit
                price — leaving them blank means the unit price is the total.
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
                  label="Warranty (months)"
                  inputMode="numeric"
                  placeholder="e.g. 12"
                  autoComplete="off"
                  maxLength={12}
                  {...fieldProps("warranty_months", {
                    hint: hintFor("warranty_months"),
                  })}
                />
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
          ) : null}

          <FormSection
            id="notes"
            title="Notes for the buyer"
            description="Anything that changes what your rate covers belongs here."
          >
            <TextAreaField
              label="Anything else they should know"
              placeholder="What your rate includes and excludes, access needs, when you can start, alternatives…"
              rows={5}
              maxLength={4000}
              {...fieldProps("notes", { hint: hintFor("notes") })}
            />
          </FormSection>

          <FormSection
            id="files"
            title="Attachments"
            description="Licences, job sheets or a photo of the site back up your quote. You can also send it without any files."
          >
            <FileUpload
              rows={rows}
              onFilesPicked={handleFilesPicked}
              onRemove={handleRemoveRow}
              onRetry={handleRetryRow}
              maxUploadMb={maxUploadMb}
              allowedExtensions={allowedExtensions}
              disabled={submitting}
            />
          </FormSection>

          {isCaptchaEnabled(captcha) ? (
            <FormSection
              id="captcha"
              title="Quick verification"
              description="This check keeps automated spam out of the buyer's inbox."
            >
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
            </FormSection>
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
        {pendingIssues?.missing?.length ? (
          <p>
            You have left{" "}
            <strong className="font-semibold text-content">
              {pendingIssues.missing.length} required field
              {pendingIssues.missing.length === 1 ? "" : "s"}
            </strong>{" "}
            blank
            {` (${pendingIssues.missing
              .map((entry) => entry.label)
              .join(", ")})`}
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
