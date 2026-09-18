/**
 * Presentation-only helpers: dates, byte sizes, clipboard, file download and the
 * plain-text summary a supplier can keep for their records.
 *
 * Everything here is pure and dependency-free so it can be reused by the
 * confirmation view without pulling in the API client.
 */

/** Common trade currencies offered as suggestions. The field stays free text. */
export const CURRENCY_CODES = [
  "USD",
  "EUR",
  "GBP",
  "INR",
  "CNY",
  "VND",
  "THB",
  "MXN",
  "BRL",
  "PLN",
  "TRY",
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

/** Supplier-facing names for the fields the API can mark as missing. */
export const FIELD_LABELS = {
  supplier_name: "company name",
  contact_name: "contact name",
  contact_email: "contact email",
  currency: "currency",
  unit_price: "unit price",
  unit: "unit of measure",
  lead_time: "lead time",
  moq: "minimum order quantity",
  payment_terms: "payment terms",
  incoterms: "incoterms",
  validity_date: "validity date",
  warranty_months: "warranty months",
  shipping_cost: "shipping cost",
  duties: "duties",
  taxes: "taxes",
  discount: "discount",
  notes: "notes",
};

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

  lines.push("SUPPLIER QUOTE SUMMARY");
  lines.push(rule);
  lines.push(`Reference number : ${result?.reference_number || "—"}`);
  lines.push(`Submitted        : ${result?.submitted_at || "—"}`);
  lines.push(`Buyer            : ${preview?.buyer_company || "—"}`);
  lines.push(`RFQ number       : ${preview?.rfq_number || result?.rfq_number || "—"}`);
  lines.push(`Item             : ${preview?.item_name || result?.item_name || "—"}`);
  if (preview?.specification) lines.push(`Specification    : ${preview.specification}`);
  if (preview?.quantity != null) {
    lines.push(`Quantity         : ${preview.quantity} ${preview.unit || ""}`.trimEnd());
  }
  if (preview?.delivery_expectation) {
    lines.push(`Delivery wanted  : ${formatDate(preview.delivery_expectation)}`);
  }
  lines.push("");

  lines.push("YOUR QUOTE");
  lines.push(rule);
  const rows = [
    ["Supplier", payload?.supplier_name],
    ["Contact name", payload?.contact_name],
    ["Contact email", payload?.contact_email],
    ["Currency", payload?.currency],
    ["Unit price", payload?.unit_price],
    ["Unit of measure", payload?.unit],
    ["Lead time", payload?.lead_time],
    ["Minimum order quantity", payload?.moq],
    ["Payment terms", payload?.payment_terms],
    ["Incoterms", payload?.incoterms],
    ["Validity date", payload?.validity_date ? formatDate(payload.validity_date) : ""],
    ["Warranty (months)", payload?.warranty_months],
    ["Shipping cost", payload?.shipping_cost],
    ["Duties", payload?.duties],
    ["Taxes", payload?.taxes],
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
