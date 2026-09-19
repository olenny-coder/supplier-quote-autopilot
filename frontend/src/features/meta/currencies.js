/**
 * Currency picker options.
 *
 * `GET /meta/options` exposes the *base* currency (SGD) but deliberately not an
 * exhaustive ISO-4217 list, so the buy-side forms carry a short convenience list
 * of the codes their buyers actually quote in. The base currency is always
 * inserted first, which is what makes it the default of every currency select
 * instead of the literal "SGD" being repeated in each form.
 *
 * The base currency leads the convenience list too, because it is this product's
 * base currency: `formatPrice` falls back to it, so a form that has not yet
 * loaded `/meta/options` still defaults to the right money.
 */

/** Codes a Singapore facilities buyer is likely to receive a quote in. */
const COMMON_CURRENCY_CODES = [
  "SGD",
  "USD",
  "EUR",
  "GBP",
  "MYR",
  "INR",
  "JPY",
  "AUD",
  "CNY",
  "HKD",
  "AED",
];

/**
 * Currency codes for a `<Select>`: the codes given first, in order, deduplicated,
 * then the convenience list. Passing the base currency (and the currency already
 * on the record) guarantees the current value is always representable, even if a
 * buyer was invoiced in something unusual.
 */
export function currencyOptions(...codes) {
  const ordered = [];

  [...codes, ...COMMON_CURRENCY_CODES].forEach((code) => {
    const normalised = String(code ?? "")
      .trim()
      .toUpperCase();

    if (normalised && !ordered.includes(normalised)) ordered.push(normalised);
  });

  return ordered;
}
