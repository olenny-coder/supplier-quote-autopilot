"""Landed-cost model.

    total = unit_price × quantity
          + shipping
          + duties
          + taxes
          − discount

Everything is computed in the RFQ's base currency, with the supplier's own
currency converted first, and with the result rebased onto the RFQ's Incoterms
basis. The supplier's submitted numbers are never mutated — the breakdown is a
separate, auditable object.

Order of operations matters and is deliberate:

1. Convert each money component from the supplier's currency into the base
   currency (so duties/taxes quoted in the supplier's currency are not added to
   a converted goods value at the wrong rate).
2. Sum them into a total.
3. Rebase the total onto the RFQ's Incoterms basis.
"""

from decimal import ROUND_HALF_UP
from decimal import Decimal

from comparison.fx import UnknownCurrencyError
from comparison.fx import build_rate_table
from comparison.fx import convert
from comparison.fx import normalize_currency_code
from comparison.incoterms import build_factor_table
from comparison.incoterms import normalize_incoterm
from comparison.incoterms import rebase_factor
from comparison.schemas import CostBreakdown
from comparison.schemas import QuoteInput

TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


def money(value: Decimal | float | int | None) -> Decimal:
    """Coerce anything numeric-or-null into a 2dp Decimal, treating null as zero."""

    if value is None:
        return Decimal("0")

    if isinstance(value, Decimal):
        return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class CostModelError(Exception):
    """Raised when a quote cannot be costed — always caught and surfaced."""


def compute_cost(
    quote: QuoteInput,
    *,
    quantity: int,
    base_currency: str,
    base_incoterms: str | None,
    unit_price_base: Decimal | None,
    rates: dict[str, float] | None = None,
    factors: dict[str, float] | None = None,
) -> CostBreakdown:
    """Build the fully normalized cost breakdown for one quote.

    ``unit_price_base`` is supplied by the engine because it has already applied
    the unit-of-measure conversion; passing it in keeps unit logic out of the
    cost model.
    """

    rate_table = rates if rates is not None else build_rate_table()
    factor_table = factors if factors is not None else build_factor_table()

    target_currency = normalize_currency_code(base_currency)
    source_currency = normalize_currency_code(quote.currency)

    if unit_price_base is None:
        raise CostModelError("Quote has no unit price.")

    breakdown = CostBreakdown(
        fx_from=source_currency,
        fx_to=target_currency,
        incoterms_from=normalize_incoterm(quote.incoterms),
        incoterms_to=normalize_incoterm(base_incoterms),
    )

    try:
        fx_rate = convert(Decimal("1"), source_currency, target_currency, rate_table)[1]
    except UnknownCurrencyError:
        raise

    breakdown.fx_rate = fx_rate.quantize(Decimal("0.0000001"), rounding=ROUND_HALF_UP)

    goods = (unit_price_base * Decimal(quantity)).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )
    breakdown.goods = goods

    # Convert each add-on individually: a supplier may quote freight in their own
    # currency while the goods price is already understood in the base one, and
    # lumping them together would apply one rate to both.
    def converted(value: Decimal | None) -> Decimal:
        if value is None:
            return Decimal("0")

        # Quantized, not returned raw. A converted amount is a rate times an amount,
        # so a foreign-currency callout came back as 28 decimal places
        # (99.78723404255319148936170212) in the API and on the dashboard. Money is
        # two decimal places; the FX rate keeps its own precision on
        # ``breakdown.fx_rate`` where it belongs.
        return convert(money(value), source_currency, target_currency, rate_table)[
            0
        ].quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    breakdown.shipping = converted(quote.shipping_cost)
    breakdown.duties = converted(quote.duties)
    breakdown.taxes = converted(quote.taxes)
    breakdown.discount = converted(quote.discount)

    # Services: the callout/attendance fee occupies the same slot as freight — a
    # real cost of getting the work done that is not part of the measured works.
    # A supplier may quote one or the other, never both, but the model does not
    # care: it sums whatever was stated.
    breakdown.callout = converted(quote.callout_charge)

    # GST (or equivalent): only derive it when the supplier stated a rate but no
    # explicit amount. Deriving over an explicit figure would double-count, and
    # deriving from nothing would invent a cost the supplier never quoted.
    if breakdown.taxes == 0 and quote.gst_rate:
        taxable = breakdown.goods + breakdown.shipping + breakdown.callout
        derived = (taxable * money(quote.gst_rate) / Decimal("100")).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
        breakdown.taxes = derived
        breakdown.tax_derived_from_rate = True

    breakdown.subtotal = (
        breakdown.goods
        + breakdown.shipping
        + breakdown.callout
        + breakdown.duties
        + breakdown.taxes
        - breakdown.discount
    ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    breakdown.total_before_incoterms = breakdown.subtotal

    multiplier, adjusted = rebase_factor(
        quote.incoterms, base_incoterms, factor_table
    )
    breakdown.incoterms_factor = multiplier.quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )

    if adjusted:
        breakdown.total = (breakdown.subtotal * multiplier).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
    else:
        breakdown.total = breakdown.subtotal

    # A negative landed cost is impossible and always means bad input data.
    if breakdown.total < 0:
        raise CostModelError(
            "Discount exceeds the quoted cost; please check the submitted figures."
        )

    return breakdown


def unit_price_in_base(
    quote: QuoteInput,
    *,
    base_currency: str,
    unit_multiplier: float = 1.0,
    rates: dict[str, float] | None = None,
) -> Decimal:
    """Convert the supplier's unit price into the base currency and unit basis."""

    if quote.unit_price is None:
        raise CostModelError("Quote has no unit price.")

    rate_table = rates if rates is not None else build_rate_table()

    converted = convert(
        Decimal(str(quote.unit_price)),
        normalize_currency_code(quote.currency),
        normalize_currency_code(base_currency),
        rate_table,
    )[0]

    if unit_multiplier != 1.0:
        converted = converted * Decimal(str(unit_multiplier))

    return converted.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
