"""Procurement taxonomy: what is being bought, and what a quote for it must contain.

This product is oriented around **services** — building maintenance and minor works
— rather than goods. The difference is not cosmetic. A services RFQ asks very
different questions from a goods RFQ:

======================  ==============================  ============================
Dimension               Goods                           Services
======================  ==============================  ============================
Price basis             per unit (pcs, kg, m)           per job, per hour, per visit,
                                                        per point, per sqm, lump sum
Where                   Incoterms, freight, duties      Site name/address, access
                                                        hours, permits, escorts
Speed                   Production lead time            Response/attendance time (SLA)
                                                        and mobilisation time
Fit to buy              Minimum order quantity          Minimum callout, contract term
Quality assurance       Warranty                        Defect liability period,
                                                        accreditation (LEW, bizSAFE,
                                                        ISO, PUB)
Tax                     Import duties, VAT              GST (Singapore, 9%)
======================  ==============================  ============================

This module owns the *domain* metadata: which categories exist, which rate bases
make sense, and which fields an RFQ of each type must collect.

It deliberately owns nothing else:

* the **scoring vocabulary** (which criteria exist and their default weights) lives
  in :mod:`comparison.schemas`, because the engine is what scores, and duplicating it
  here would let the two drift;
* the **supplier-facing labels** live in :mod:`agents.quote_parser.completeness`,
  because those are the words the follow-up emails already use, and a second label
  table would eventually disagree with the first.

Both are re-exported below so callers have one import for everything domain-shaped.
"""

from typing import Literal

from agents.quote_parser.completeness import label_for as _supplier_label_for
from comparison.schemas import CRITERIA
from comparison.schemas import DEFAULT_WEIGHTS_GOODS
from comparison.schemas import DEFAULT_WEIGHTS_SERVICE
from comparison.schemas import default_weights as _engine_default_weights

ProcurementType = Literal["service", "goods"]

PROCUREMENT_TYPES: tuple[str, ...] = ("service", "goods")

#: The default, because this product exists for maintenance and minor works.
DEFAULT_PROCUREMENT_TYPE: str = "service"


# ---------------------------------------------------------------------------
#  Categories
# ---------------------------------------------------------------------------
#: Ordered roughly by how often a facilities team buys them. The first entry is the
#: form default so the common case needs no interaction.
SERVICE_CATEGORIES: tuple[str, ...] = (
    "Building Maintenance & Handyman",
    "Electrical Minor Works",
    "Mechanical Minor Works",
    "Plumbing & Sanitary Minor Works",
    "Painting & Decorating",
    "ACMV / Air-Conditioning",
    "Fire Protection Systems",
    "Lift & Escalator",
    "CCTV & Security Systems",
    "Roofing & Waterproofing",
    "Flooring & Carpet",
    "Cleaning Services",
    "Pest Control",
    "Landscaping & Horticulture",
    "Waste Management",
    "Signage & Wayfinding",
    "General Building Works",
    "Testing & Commissioning",
    "Other Services",
)

#: Common goods categories, kept so the goods path stays usable.
GOODS_CATEGORIES: tuple[str, ...] = (
    "Spare Parts & Consumables",
    "Electrical Components",
    "Plumbing Fittings",
    "Building Materials",
    "Tools & Equipment",
    "Safety & PPE",
    "Other Goods",
)


def categories_for(procurement_type: str | None) -> tuple[str, ...]:
    if (procurement_type or DEFAULT_PROCUREMENT_TYPE) == "goods":
        return GOODS_CATEGORIES

    return SERVICE_CATEGORIES


# ---------------------------------------------------------------------------
#  Rate bases
# ---------------------------------------------------------------------------
#: What a services price is quoted against — the service analogue of a unit of
#: measure, and the field that most often makes two quotes silently incomparable
#: when it is left implicit. A "per hour" rate and a "lump sum" cannot be ranked
#: against each other without knowing the estimated effort, so the engine must be
#: able to tell that they differ.
SERVICE_RATE_BASES: tuple[str, ...] = (
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
)

GOODS_UNITS: tuple[str, ...] = ("pcs", "set", "box", "kg", "m", "roll", "sheet", "lot")


def rate_bases_for(procurement_type: str | None) -> tuple[str, ...]:
    if (procurement_type or DEFAULT_PROCUREMENT_TYPE) == "goods":
        return GOODS_UNITS

    return SERVICE_RATE_BASES


# ---------------------------------------------------------------------------
#  Required-field contract, per procurement type
# ---------------------------------------------------------------------------
#: Goods: the original set, unchanged, so existing behaviour is preserved exactly.
REQUIRED_FIELDS_GOODS: list[str] = [
    "unit_price",
    "currency",
    "lead_time",
    "moq",
    "payment_terms",
    "incoterms",
    "validity_date",
]

#: Services: what is genuinely needed to compare two maintenance quotes on equal
#: terms.
#:
#:  * ``unit_price`` and ``unit`` — the rate, and the basis it is quoted against
#:  * ``response_time``      — the SLA. The single biggest differentiator between two
#:                             otherwise identical maintenance quotes.
#:  * ``payment_terms``      — cash-flow terms matter more on services, where work is
#:                             invoiced after completion.
#:  * ``validity_date``      — rates are held for a period and then re-quoted. An
#:                             expired rate sheet is the services equivalent of an
#:                             expired price.
#:
#: Deliberately NOT required: MOQ (a services minimum callout is a *charge*, not a
#: quantity gate, and it already shows up inside the price), Incoterms, and freight
#: — nothing is being shipped.
REQUIRED_FIELDS_SERVICE: list[str] = [
    "unit_price",
    "currency",
    "unit",
    "response_time",
    "payment_terms",
    "validity_date",
]

#: Scored when present, never chased when absent.
OPTIONAL_FIELDS_SERVICE: list[str] = [
    "callout_charge",
    "labour_rate",
    "materials_markup",
    "compliance",
    "gst_rate",
    "defect_liability",
]

OPTIONAL_FIELDS_GOODS: list[str] = [
    "warranty_months",
    "shipping_cost",
    "duties",
    "taxes",
    "discount",
]


def default_required_fields(procurement_type: str | None) -> list[str]:
    if (procurement_type or DEFAULT_PROCUREMENT_TYPE) == "goods":
        return list(REQUIRED_FIELDS_GOODS)

    return list(REQUIRED_FIELDS_SERVICE)


def optional_fields(procurement_type: str | None) -> list[str]:
    if (procurement_type or DEFAULT_PROCUREMENT_TYPE) == "goods":
        return list(OPTIONAL_FIELDS_GOODS)

    return list(OPTIONAL_FIELDS_SERVICE)


# ---------------------------------------------------------------------------
#  Accreditations
# ---------------------------------------------------------------------------
#: Common Singapore credentials a buyer can require and a supplier can hold. Free
#: text is allowed as well — this list drives a picker, not a whitelist.
COMMON_ACCREDITATIONS: tuple[str, ...] = (
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
)


# ---------------------------------------------------------------------------
#  Weights and labels, delegated to the packages that own them
# ---------------------------------------------------------------------------
def default_weights(procurement_type: str | None) -> dict[str, float]:
    """Per-type scoring defaults, from the engine."""

    return _engine_default_weights(procurement_type or DEFAULT_PROCUREMENT_TYPE)


def label_for(field: str, procurement_type: str | None = None) -> str:
    """Supplier-facing label for a field, worded for what is being bought.

    Delegates to the parser's label table — the same one the follow-up emails use —
    and applies the type-specific overrides for the few fields whose meaning really
    changes. ``lead_time`` is "how long production takes" for goods and "how long
    until someone is on site" for services; ``moq`` is an order quantity for goods and
    a minimum callout charge for services. Both are fields a supplier would otherwise
    answer the wrong question to.
    """

    return _supplier_label_for(field, procurement_type or DEFAULT_PROCUREMENT_TYPE)


def describe_tax(currency: str, gst_rate: float | None) -> str:
    """One sentence about tax, written for the *supplier*.

    Every caller is supplier-facing — the invitation email, the public form's
    preview, and the grounding text handed to the quote parser — so it is phrased as
    an instruction to the supplier rather than as a note to the buyer. The previous
    wording ("figures are compared before GST, which is added at 9%") described the
    engine to the wrong audience and left the supplier unsure whether the rate they
    typed should include tax.
    """

    is_sgd = (currency or "").upper() == "SGD"
    label = "GST" if is_sgd else "tax"
    # `str.capitalize()` would turn the acronym GST into "Gst", which reads as a typo.
    start_of_sentence = "GST" if is_sgd else "Tax"

    if gst_rate is None:
        return (
            f"Please state whether your prices include {label}; figures are compared "
            f"before tax so quotes are ranked on the same basis."
        )

    return (
        f"Please quote your rates excluding {label}. {start_of_sentence} is added at "
        f"{gst_rate:g}% when the final cost is worked out — state a different rate if "
        f"we have this wrong for you."
    )


__all__ = [
    "COMMON_ACCREDITATIONS",
    "CRITERIA",
    "DEFAULT_PROCUREMENT_TYPE",
    "DEFAULT_WEIGHTS_GOODS",
    "DEFAULT_WEIGHTS_SERVICE",
    "GOODS_CATEGORIES",
    "GOODS_UNITS",
    "OPTIONAL_FIELDS_GOODS",
    "OPTIONAL_FIELDS_SERVICE",
    "PROCUREMENT_TYPES",
    "REQUIRED_FIELDS_GOODS",
    "REQUIRED_FIELDS_SERVICE",
    "SERVICE_CATEGORIES",
    "SERVICE_RATE_BASES",
    "categories_for",
    "default_required_fields",
    "default_weights",
    "describe_tax",
    "label_for",
    "optional_fields",
    "rate_bases_for",
]
