/**
 * Presentation-only helpers: currencies, rate bases, accreditations, dates, byte
 * sizes, clipboard, file download and the plain-text summary a supplier can keep
 * for their records.
 *
 * Everything here is pure and dependency-free so it can be reused by the
 * confirmation view without pulling in the API client.
 */

/**
 * Common currencies offered as suggestions. The field stays free text.
 *
 * SGD leads the list because this product quotes Singapore facilities work, and
 * the invitation's own currency is prefilled from the API. Nothing in this list is
 * a *default*: the default is always whatever the buyer's RFQ says.
 */
export const CURRENCY_CODES = [
  "SGD",
  "USD",
  "EUR",
  "GBP",
  "MYR",
  "IDR",
  "CNY",
  "INR",
  "THB",
  "AUD",
  // Carried over from the goods-era list. Suppliers quote from anywhere and the
  // field is free text, so removing a suggestion only removes a convenience.
  "VND",
  "MXN",
  "BRL",
  "PLN",
  "TRY",
];

/**
 * Rate bases a service is quoted against. Mirrors the server's taxonomy
 * (`service_rate_bases`) rather than inventing vocabulary here: a rate quoted
 * "per hour" and a rate quoted "lump sum" cannot be compared unless both sides
 * agree on what the number is for.
 */
export const RATE_BASES_SERVICE = [
  "per job",
  "per visit",
  "per hour",
  "per day",
  "per point",
  "per unit",
  "per sqm",
  "per metre",
  "per month",
  "lump sum",
];

/** Units a goods RFQ is priced in. Retained so a goods RFQ still renders sensibly. */
export const UNITS_GOODS = [
  "pcs",
  "set",
  "box",
  "kg",
  "m",
  "roll",
  "sheet",
  "lot",
];

/** Rate bases / units offered for a procurement type. */
export function rateBasesFor(procurementType) {
  return procurementType === "goods" ? UNITS_GOODS : RATE_BASES_SERVICE;
}

/**
 * Picker options that always include the value the RFQ already carries, so a
 * basis outside the standard set (an older goods RFQ, a bespoke unit) is never
 * silently replaced by a different one. Appended rather than prepended so the
 * canonical order stays at the top of the list.
 */
export function withCurrentOption(options, current) {
  const value = String(current ?? "").trim();
  if (!value || options.includes(value)) return [...options];
  return [...options, value];
}

/**
 * Common Singapore credentials offered as chips. A picker, never a whitelist:
 * the supplier can add anything else in free text.
 */
export const COMMON_ACCREDITATIONS = [
  "EMA Licensed Electrical Worker (LEW)",
  "PUB Licensed Plumber",
  "BCA Registered Contractor",
  "bizSAFE Level 3",
  "bizSAFE Star",
  "ISO 9001",
  "ISO 14001",
  "ISO 45001",
  "SCDF Fire Safety Certification",
  "WSH Act Compliance",
  "Work at Height Certified",
  "Confined Space Certified",
  "Lift & Escalator (BCA Permit Holder)",
];

/** Incoterms 2020. Suggestions only — suppliers often append a named place. */
export const INCOTERMS = [
  "EXW",
  "FCA",
  "FOB",
  "CFR",
  "CIF",
  "CPT",
  "CIP",
  "DAP",
  "DPU",
  "DDP",
];

/**
 * Supplier-facing names for the fields the API can mark as missing.
 *
 * These are **not** how the form names its own controls — they are the fallback
 * used when the API response omits `required_field_labels` (the authoritative,
 * parallel array the server sends next to `required_fields`). The wording here is
 * copied verbatim from the server's single label table so the fallback can never
 * drift into a second vocabulary.
 */
export const FIELD_LABELS = {
  // price and basis
  unit_price: "rate / unit price",
  currency: "currency",
  unit: "rate basis",
  // speed
  response_time: "response time (SLA)",
  response_time_hours: "response time (SLA)",
  lead_time: "mobilisation time",
  // commercial
  payment_terms: "payment terms",
  validity_date: "rates valid until",
  callout_charge: "callout / attendance charge",
  labour_rate: "labour rate per hour",
  materials_markup: "materials markup",
  materials_markup_pct: "materials markup",
  // compliance and tax
  compliance: "accreditations and licences",
  compliance_accreditations: "accreditations and licences",
  gst_rate: "GST rate",
  // goods
  moq: "minimum callout or minimum order quantity",
  incoterms: "delivery terms (Incoterms)",
  warranty_months: "defect liability period",
  shipping_cost: "freight or delivery",
  duties: "duty and clearance cost",
  taxes: "tax amount",
  discount: "discount",
  // identity
  supplier_name: "company name",
  contact_name: "contact name",
  contact_email: "contact email address",
  notes: "notes",
};

/**
 * The buyer's required-field contract speaks in domain keys (`compliance`), while
 * the form posts wire fields (`compliance_accreditations`). This is the single
 * place that reconciles the two, in both directions — every other required-field
 * key is named the same on both sides.
 */
export const REQUIRED_KEY_TO_FIELD = {
  response_time: "response_time_hours",
  compliance: "compliance_accreditations",
  materials_markup: "materials_markup_pct",
};

/** RFQ required-field key -> the form control that answers it. */
export function fieldKeyForRequiredKey(key) {
  return REQUIRED_KEY_TO_FIELD[key] || key;
}

/** Form control name -> the RFQ required-field key it answers. */
export function requiredKeyForFieldKey(key) {
  for (const [requiredKey, fieldKey] of Object.entries(REQUIRED_KEY_TO_FIELD)) {
    if (fieldKey === key) return requiredKey;
  }
  return key;
}

/**
 * True when a value counts as an answer.
 *
 * Multi-selects answer with a list, so a blank check cannot be a string test
 * alone — an empty accreditation list must read as "not answered", exactly like an
 * empty text box.
 */
export function hasAnswer(value) {
  if (Array.isArray(value)) {
    return value.some((entry) => String(entry ?? "").trim() !== "");
  }
  return String(value ?? "").trim() !== "";
}

/**
 * Formats a decimal the API sent as a string for an input box: "9.00" -> "9",
 * "15" -> "15". Numbers around the form are strings, so they are parsed before
 * being treated as numbers. Anything that is not a plain decimal is returned
 * untouched rather than mangled.
 */
export function formatDecimalInput(value) {
  const text = String(value ?? "").trim();
  if (!text) return "";
  if (!/^-?\d+(\.\d+)?$/.test(text)) return text;
  const parsed = Number(text);
  return Number.isFinite(parsed) ? String(parsed) : text;
}

const DATE_TIME_FORMAT = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZoneName: "short",
});

const DATE_FORMAT = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

/**
 * Formats an ISO timestamp for a supplier-facing message. Unparseable values
 * are returned unchanged rather than rendered as "Invalid Date".
 */
export function formatDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return DATE_TIME_FORMAT.format(date);
}

/** Formats a `YYYY-MM-DD` (or ISO timestamp) as a short human date. */
export function formatDate(value) {
  if (!value) return "";
  // A bare date string is parsed as UTC midnight, which can shift a day in
  // negative-offset timezones when re-formatted locally. Pin it to local noon.
  const normalised = /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? `${value}T12:00:00`
    : value;
  const date = new Date(normalised);
  if (Number.isNaN(date.getTime())) return String(value);
  return DATE_FORMAT.format(date);
}

/** Human byte size, e.g. 1258291 -> "1.2 MB". */
export function formatBytes(bytes) {
  const value = Number(bytes);
  if (!Number.isFinite(value) || value < 0) return "";
  if (value < 1024) return `${value} B`;
  const units = ["KB", "MB", "GB"];
  let size = value / 1024;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

/** True for a real `YYYY-MM-DD` calendar date (rejects 2026-02-31). */
export function isValidIsoDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return (
    date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day
  );
}

/**
 * Pragmatic email check: one @, a dot-bearing domain, no spaces. Deliberately
 * not RFC 5322 — the goal is catching typos, not rejecting exotic addresses a
 * supplier legitimately uses.
 */
export function isValidEmail(value) {
  return /^[^\s@]+@[^\s@.]+(\.[^\s@.]+)+$/.test(String(value).trim());
}

/**
 * Parses a supplier-typed number, or null when there is nothing to compare.
 * Used for the "is this slower than the buyer asked for?" check, which must never
 * turn a stray character into a blocking error.
 */
export function numberOrNull(value) {
  const text = String(value ?? "").trim();
  if (!text) return null;
  const parsed = Number(text);
  return Number.isFinite(parsed) ? parsed : null;
}

/**
 * Copies text to the clipboard.
 *
 * `navigator.clipboard` needs a secure context, and suppliers occasionally open
 * these links over plain http on an internal host, so the legacy
 * `execCommand("copy")` path is kept as a fallback. Returns true on success.
 */
export async function copyToClipboard(text) {
  const value = String(text ?? "");
  if (!value) return false;

  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      // Fall through to the legacy path.
    }
  }

  try {
    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.top = "-1000px";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(textarea);
    return ok;
  } catch {
    return false;
  }
}

/**
 * Saves text as a file via a Blob + temporary anchor.
 *
 * Used for "Download a copy" so the supplier can attach the summary to their own
 * records without the buyer having to email a PDF.
 */
export function downloadTextFile(filename, text) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  // Revoke on the next tick: some browsers abort the download if the object URL
  // disappears synchronously.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Strips characters that are illegal in filenames on Windows/macOS. */
function safeFilename(value, fallback) {
  const cleaned = String(value || "")
    .replace(/[^A-Za-z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return cleaned || fallback;
}

/** "80.00 SGD", or "" when nothing was quoted. */
function money(value, currency) {
  const text = String(value ?? "").trim();
  if (!text) return "";
  return [text, String(currency ?? "").trim()].filter(Boolean).join(" ");
}

/**
 * Builds the plain-text summary offered by "Download a copy".
 *
 * @param {object} args
 * @param {object} args.preview  InvitationPreview from the API.
 * @param {object} args.result   PublicQuoteResponse from the API.
 * @param {object} args.payload  Exactly what was POSTed, so the file matches the
 *                               submission rather than the local form state.
 */
export function buildQuoteSummaryText({ preview, result, payload }) {
  const lines = [];
  const rule = "-".repeat(58);
  const currency = String(payload?.currency ?? "").trim();
  const accreditations = Array.isArray(payload?.compliance_accreditations)
    ? payload.compliance_accreditations
    : [];

  lines.push("SUPPLIER QUOTE SUMMARY");
  lines.push(rule);
  lines.push(`Reference number : ${result?.reference_number || "—"}`);
  lines.push(`Submitted        : ${result?.submitted_at || "—"}`);
  lines.push(`Buyer            : ${preview?.buyer_company || "—"}`);
  lines.push(`RFQ number       : ${preview?.rfq_number || result?.rfq_number || "—"}`);
  lines.push(`Item             : ${preview?.item_name || result?.item_name || "—"}`);
  // What was quoted for, in the buyer's own words — the same three facts the
  // confirmation screen shows.
  if (preview?.category) lines.push(`Category         : ${preview.category}`);
  if (preview?.site_name) lines.push(`Site             : ${preview.site_name}`);
  if (preview?.site_address) lines.push(`Site address     : ${preview.site_address}`);
  if (preview?.site_access_notes) {
    lines.push(`Access notes     : ${preview.site_access_notes}`);
  }
  if (preview?.specification) lines.push(`Specification    : ${preview.specification}`);
  if (preview?.quantity != null) {
    lines.push(`Quantity         : ${preview.quantity} ${preview.unit || ""}`.trimEnd());
  }
  if (preview?.delivery_expectation) {
    lines.push(`Wanted by        : ${formatDate(preview.delivery_expectation)}`);
  }
  lines.push("");

  lines.push("YOUR QUOTE");
  lines.push(rule);
  const rows = [
    ["Supplier", payload?.supplier_name],
    ["Contact name", payload?.contact_name],
    ["Contact email", payload?.contact_email],
    ["Rate", money(payload?.unit_price, currency)],
    ["Rate basis", payload?.unit],
    [
      "Response time",
      payload?.response_time_hours
        ? `within ${payload.response_time_hours} hours`
        : "",
    ],
    ["Mobilisation time", payload?.lead_time],
    ["Callout charge", money(payload?.callout_charge, currency)],
    ["Labour rate / hour", money(payload?.labour_rate, currency)],
    [
      "Materials markup",
      payload?.materials_markup_pct ? `${payload.materials_markup_pct}%` : "",
    ],
    ["GST rate", payload?.gst_rate ? `${payload.gst_rate}%` : ""],
    ["Payment terms", payload?.payment_terms],
    [
      "Rates valid until",
      payload?.validity_date ? formatDate(payload.validity_date) : "",
    ],
    ["Accreditations", accreditations.join(", ")],
    ["Minimum order qty", payload?.moq],
    ["Incoterms", payload?.incoterms],
    [
      "Defect liability",
      payload?.warranty_months ? `${payload.warranty_months} months` : "",
    ],
    ["Freight / shipping", money(payload?.shipping_cost, currency)],
    ["Duties", money(payload?.duties, currency)],
    ["Tax amount", payload?.taxes],
    ["Discount", payload?.discount],
  ];
  for (const [label, value] of rows) {
    lines.push(`${label.padEnd(21)}: ${value ? value : "—"}`);
  }
  if (payload?.notes) {
    lines.push("");
    lines.push("Notes");
    lines.push(payload.notes);
  }

  if (Array.isArray(payload?.attachment_keys) && payload.attachment_keys.length) {
    lines.push("");
    lines.push("Attachments sent");
    lines.push(rule);
    for (const key of payload.attachment_keys) {
      lines.push(`- ${String(key).split("/").pop()}`);
    }
  }

  if (result?.missing_field_labels?.length) {
    lines.push("");
    lines.push("Still needed by the buyer");
    lines.push(rule);
    for (const label of result.missing_field_labels) {
      lines.push(`- ${label}`);
    }
  }

  lines.push("");
  lines.push(rule);
  lines.push(`Buyer contact    : ${preview?.buyer_contact_email || "—"}`);
  if (preview?.buyer_contact_phone) {
    lines.push(`Buyer phone      : ${preview.buyer_contact_phone}`);
  }
  lines.push(
    "Keep this reference number: the buyer will use it when they contact you."
  );

  return `${lines.join("\n")}\n`;
}

/** Filename for the downloaded summary. */
export function summaryFilename(result) {
  const base = safeFilename(result?.reference_number, "supplier-quote");
  return `${base}.txt`;
}
