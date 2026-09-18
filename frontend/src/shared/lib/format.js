/**
 * Shared formatting helpers. Centralized so currency/date rendering stays
 * consistent across features instead of being re-implemented per component.
 */

export function formatPrice(value, currency = "USD") {
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency || "USD",
      maximumFractionDigits: 2,
    }).format(Number(value));
  } catch {
    return `${currency || ""} ${value}`;
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
 * `missing_fields` and `required_fields` carry machine keys (`unit_price`),
 * while the API only supplies `missing_field_labels` on some projections
 * (`QuoteResult` has none), so the UI needs its own mapping to label chips and
 * the dashboard's chase list consistently.
 */
const FIELD_LABELS = {
  unit_price: "Unit price",
  currency: "Currency",
  unit: "Unit of measure",
  lead_time: "Lead time",
  moq: "MOQ",
  payment_terms: "Payment terms",
  incoterms: "Incoterms",
  validity_date: "Validity date",
  warranty_months: "Warranty",
  shipping_cost: "Shipping cost",
  duties: "Duties",
  taxes: "Taxes",
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
