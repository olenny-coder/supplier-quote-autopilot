"""Currency conversion.

A **static, env-overridable** rate table, not a live feed. Rationale
(INTEGRATION_PLAN.md assumption A5): a live FX API is another network dependency,
another key, and another free-tier quota — and the failure mode of a live feed
that goes down mid-comparison is worse than a slightly stale rate.

Every rate carries an ``as_of`` date and a ``source`` string that the engine
copies into the comparison snapshot, so a buyer looking at the numbers can see
exactly which rate was applied and when it was taken. Rates are quoted as
*units of the currency per 1 USD*.

Override without a deploy:

    FX_RATES_JSON={"EUR": 0.93, "INR": 84.1}
"""

from datetime import date
from decimal import Decimal
from decimal import InvalidOperation

#: Units per 1 USD. Update via FX_RATES_JSON rather than editing this file.
DEFAULT_RATES: dict[str, float] = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "CHF": 0.88,
    "CAD": 1.36,
    "AUD": 1.52,
    "JPY": 157.0,
    "CNY": 7.24,
    "HKD": 7.81,
    "SGD": 1.34,
    "INR": 83.2,
    "PKR": 278.0,
    "BDT": 117.0,
    "VND": 25400.0,
    "THB": 36.5,
    "MYR": 4.70,
    "IDR": 16200.0,
    "PHP": 58.5,
    "KRW": 1370.0,
    "TWD": 32.3,
    "AED": 3.67,
    "SAR": 3.75,
    "TRY": 32.5,
    "PLN": 3.95,
    "CZK": 23.2,
    "MXN": 17.1,
    "BRL": 5.40,
    "ZAR": 18.60,
    "EGP": 48.5,
    "NGN": 1550.0,
}

#: Currencies that are not simple float-multiples (documented for the buyer).
RATE_AS_OF = date(2026, 1, 1)
RATE_SOURCE = "static-baseline"

#: Common aliases so a supplier typing "US$" or "Euro" still normalizes.
CURRENCY_ALIASES: dict[str, str] = {
    "US$": "USD",
    "US DOLLAR": "USD",
    "DOLLAR": "USD",
    "DOLLARS": "USD",
    "$": "USD",
    "EURO": "EUR",
    "EUROS": "EUR",
    "€": "EUR",
    "POUND": "GBP",
    "POUNDS": "GBP",
    "STERLING": "GBP",
    "£": "GBP",
    "RMB": "CNY",
    "YUAN": "CNY",
    "YEN": "JPY",
    "¥": "JPY",
    "RS": "INR",
    "RUPEES": "INR",
    "RUPEE": "INR",
}


class UnknownCurrencyError(ValueError):
    """Raised when a currency has no rate — never silently treated as 1:1."""

    def __init__(self, currency: str) -> None:
        super().__init__(
            f"No FX rate for '{currency}'. Add it to FX_RATES_JSON to make this "
            f"quote comparable."
        )
        self.currency = currency


def normalize_currency_code(value: str | None, default: str = "USD") -> str:
    """Turn free text into an ISO-4217-style code."""

    if not value:
        return default

    cleaned = str(value).strip().upper().replace(".", "")

    if cleaned in CURRENCY_ALIASES:
        return CURRENCY_ALIASES[cleaned]

    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned

    # "USD 45.00" / "45 USD" / "Price in EUR" — look for any 3-letter token.
    for token in cleaned.replace("/", " ").replace("-", " ").split():
        token = token.strip()
        if token in CURRENCY_ALIASES:
            return CURRENCY_ALIASES[token]
        if len(token) == 3 and token.isalpha():
            return token

    return default


def build_rate_table(overrides: dict[str, float] | None = None) -> dict[str, float]:
    rates = dict(DEFAULT_RATES)

    for code, value in (overrides or {}).items():
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric > 0:
            rates[code.upper()] = numeric

    return rates


def get_rate(
    currency: str,
    rates: dict[str, float] | None = None,
) -> float:
    table = rates if rates is not None else build_rate_table()

    code = normalize_currency_code(currency)

    if code not in table:
        raise UnknownCurrencyError(code)

    return table[code]


def convert(
    amount: Decimal,
    from_currency: str,
    to_currency: str,
    rates: dict[str, float] | None = None,
) -> tuple[Decimal, Decimal]:
    """Convert ``amount`` and return ``(converted, rate_applied)``.

    The returned rate is *from → to* (multiply the source amount by it), so the
    snapshot can show the buyer the exact multiplier used.
    """

    table = rates if rates is not None else build_rate_table()

    source = normalize_currency_code(from_currency)
    target = normalize_currency_code(to_currency)

    source_rate = get_rate(source, table)

    if source == target:
        return amount, Decimal("1")

    target_rate = get_rate(target, table)

    rate = Decimal(str(target_rate)) / Decimal(str(source_rate))

    try:
        return (amount * rate), rate
    except InvalidOperation as exc:  # pragma: no cover - defensive
        raise UnknownCurrencyError(source) from exc


def describe(rates: dict[str, float] | None = None) -> dict[str, object]:
    """Snapshot metadata persisted on every ``Comparison`` row."""

    table = rates if rates is not None else build_rate_table()

    return {
        "source": RATE_SOURCE,
        "as_of": RATE_AS_OF.isoformat(),
        "base": "USD",
        "rates": {code: round(value, 6) for code, value in sorted(table.items())},
    }
