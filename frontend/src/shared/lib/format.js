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
