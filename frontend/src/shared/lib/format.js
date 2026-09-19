/**
 * Shared formatting helpers. Centralized so currency/date rendering stays
 * consistent across features instead of being re-implemented per component.
 */

/**
 * Money, with the base currency as the default.
 *
 * This product is oriented around Singapore building services, so an unqualified
 * price is SGD — `Intl` renders that as "S$". Callers that know the currency
 * (an RFQ's `currency`, a comparison's `base_currency`) must pass it: the
 * default exists so a missing currency degrades to the base one rather than to
 * somebody else's dollars. An unusable code falls back to a plain string rather
 * than throwing inside a render.
 */
export function formatPrice(value, currency = "SGD", fallback = "—") {
  const parsed = toNumber(value);

  if (parsed === null) return fallback;

  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency || "SGD",
      maximumFractionDigits: 2,
    }).format(parsed);
  } catch {
    return `${currency || ""} ${value}`.trim();
  }
}

export function formatDate(value, fallback = "—") {
  if (!value) return fallback;

  return new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/**
 * Coerce an API value to a number, or `null` when it is missing/unusable.
 *
 * The backend serialises Python `Decimal` fields as JSON *strings*
 * (`"1234.5600"`), and sends `null` for anything a supplier left blank. Doing
 * arithmetic or `<` comparisons on the raw value silently yields NaN or string
 * concatenation, so every numeric API field is funnelled through here first —
 * `null` is then rendered as an em dash rather than "$NaN".
 */
export function toNumber(value) {
  if (value === null || value === undefined || value === "") return null;

  const parsed = Number(value);

  return Number.isFinite(parsed) ? parsed : null;
}

export function formatNumber(value, { maximumFractionDigits = 0, fallback = "—" } = {}) {
  const parsed = toNumber(value);

  if (parsed === null) return fallback;

  return new Intl.NumberFormat("en-US", { maximumFractionDigits }).format(parsed);
}

export function formatDateTime(value, fallback = "—") {
  if (!value) return fallback;

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return fallback;

  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/**
 * Human countdown/elapsed string: "just now", "in 3 days", "2 hours ago".
 * Used for reminder schedules, last activity, and sent dates.
 */
export function formatRelativeTime(value, fallback = "—") {
  if (!value) return fallback;

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return fallback;

  const diffMs = date.getTime() - Date.now();
  const past = diffMs < 0;
  const seconds = Math.abs(diffMs) / 1000;

  const units = [
    { limit: 60, divisor: 1, singular: "second" },
    { limit: 3600, divisor: 60, singular: "minute" },
    { limit: 86400, divisor: 3600, singular: "hour" },
    { limit: 604800, divisor: 86400, singular: "day" },
    { limit: 2629800, divisor: 604800, singular: "week" },
    { limit: 31557600, divisor: 2629800, singular: "month" },
    { limit: Infinity, divisor: 31557600, singular: "year" },
  ];

  const unit = units.find((candidate) => seconds < candidate.limit);

  const amount = Math.round(seconds / unit.divisor);

  if (amount <= 0 && !past) return "just now";
  if (amount <= 0 && past) return "just now";

  const label = `${amount} ${unit.singular}${amount === 1 ? "" : "s"}`;

  return past ? `${label} ago` : `in ${label}`;
}

/**
 * Renders a *fraction* (0–1) as a percentage. Comparison weights arrive as
 * fractions that sum to 1.0, so they are formatted with this rather than with
 * `formatNumber`.
 */
export function formatPercent(fraction, { maximumFractionDigits = 0, fallback = "—" } = {}) {
  const parsed = toNumber(fraction);

  if (parsed === null) return fallback;

  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits }).format(
    parsed * 100
  )}%`;
}

/**
 * Renders a value that is *already in percent* ("9.00" → "9%"), as opposed to
 * `formatPercent`, which takes a 0–1 fraction.
 *
 * GST rates and materials markups arrive in this shape, and conflating the two
 * would print a 9% GST as 900%.
 */
export function formatPercentValue(value, { maximumFractionDigits = 2, fallback = "—" } = {}) {
  const parsed = toNumber(value);

  if (parsed === null) return fallback;

  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits }).format(parsed)}%`;
}

/**
 * A response time in hours → "4h", "48h", "2 days".
 *
 * Services are sold on how fast someone attends site, and a bare "48" in a column
 * labelled hours is the kind of number a buyer misreads by an order of magnitude,
 * so the unit is always spelled out. Hours are used up to 48 — the same
 * hours/days threshold the deadline countdown uses, and how an SLA is actually
 * written ("48h response") — and days beyond it, where a count of hours stops
 * being readable.
 */
export function formatHours(hours, fallback = "—") {
  const value = toNumber(hours);

  if (value === null) return fallback;

  if (value <= 48) {
    return `${formatNumber(value, { maximumFractionDigits: 1 })}h`;
  }

  if (Number.isInteger(value / 24)) return `${value / 24} days`;

  const whole = Math.floor(value / 24);
  const rest = value % 24;

  return `${whole}d ${formatNumber(rest, { maximumFractionDigits: 1 })}h`;
}

/**
 * A rate basis / unit of measure → a phrase that reads correctly after a price.
 *
 * "per job" and "lump sum" are already phrases and are left alone; "pcs" is a
 * bare unit, so a rate reads "$120 per pcs" rather than "$120 pcs". The list of
 * bases itself lives in `/meta/options` — this only formats whatever it is given.
 */
export function formatRateBasis(unit, fallback = "—") {
  if (!unit) return fallback;

  const text = String(unit).trim();

  if (!text) return fallback;

  const lower = text.toLowerCase();

  if (lower === "lump sum" || lower === "lot") return text;

  if (lower.startsWith("per ")) return text;

  return `per ${text}`;
}

/**
 * Deadline countdown from the dashboard's `hours_left` field (which is negative
 * once a deadline has passed): "36 h left", "3 h overdue", "4 d 6 h left".
 */
export function formatHoursRemaining(hours) {
  const value = toNumber(hours);

  if (value === null) return "—";

  const overdue = value < 0;
  const absolute = Math.abs(value);

  if (absolute < 1) return overdue ? "Due now" : "Due within the hour";

  if (absolute < 48) {
    const whole = Math.round(absolute);
    return `${whole} h ${overdue ? "overdue" : "left"}`;
  }

  const days = Math.floor(absolute / 24);
  const rest = Math.round(absolute % 24);

  return rest ? `${days} d ${rest} h ${overdue ? "overdue" : "left"}` : `${days} d ${overdue ? "overdue" : "left"}`;
}

/**
 * Quote/RFQ field keys → buyer-readable labels.
 *
 * This is the *fallback* only. The API sends the supplier-facing wording with the
 * record — `RFQResponse.required_field_labels`, `missing_field_labels` on
 * invitations and quotes — and those must win, because they are the words the
 * follow-up emails use and the only table that can stay in step with the
 * backend's required-field contract. The map below covers the projections that
 * carry bare keys (`QuoteResult.missing_fields`) so a gap is never an unlabelled
 * chip, and is deliberately type-neutral: `lead_time` is "mobilisation time" for
 * a maintenance job and "production lead time" for goods, which only the API
 * knows.
 */
const FIELD_LABELS = {
  unit_price: "Rate / unit price",
  currency: "Currency",
  unit: "Rate basis",
  response_time: "Response time (SLA)",
  response_time_hours: "Response time (SLA)",
  lead_time: "Mobilisation / lead time",
  lead_time_days: "Mobilisation / lead time",
  moq: "Minimum callout / order",
  payment_terms: "Payment terms",
  incoterms: "Delivery terms (Incoterms)",
  validity_date: "Rates valid until",
  warranty_months: "Defect liability period",
  defect_liability: "Defect liability period",
  callout_charge: "Callout / attendance charge",
  labour_rate: "Labour rate per hour",
  materials_markup: "Materials markup",
  materials_markup_pct: "Materials markup",
  compliance: "Accreditations and licences",
  compliance_accreditations: "Accreditations and licences",
  gst_rate: "GST rate",
  shipping_cost: "Freight or delivery",
  duties: "Duty and clearance cost",
  taxes: "Tax amount",
  discount: "Discount",
};

export function formatFieldKey(key, fallback = null) {
  if (!key) return fallback ?? "—";

  if (FIELD_LABELS[key]) return FIELD_LABELS[key];

  const text = String(key).replace(/[_-]+/g, " ").trim();

  return text.charAt(0).toUpperCase() + text.slice(1);
}

/**
 * "Net 30" / "8" / null → a consistent day count label. Lead times arrive as
 * integers but `null` is common on incomplete quotes.
 */
export function formatLeadTime(days, fallback = "—") {
  const value = toNumber(days);

  if (value === null) return fallback;

  return `${formatNumber(value)} day${value === 1 ? "" : "s"}`;
}
