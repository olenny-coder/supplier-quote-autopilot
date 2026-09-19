"""Comparison engine — schemas.

Plain Pydantic models, deliberately free of SQLAlchemy and FastAPI. The backend
converts ORM rows into these on the way in and persists the results on the way
out, which keeps the engine unit-testable without a database and reusable from a
script or a notebook.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

#: Criteria the scoring engine understands, in the order they appear in output.
#:
#: ``response_time`` and ``compliance`` exist for services. A maintenance quote is
#: differentiated less by a few dollars than by how fast someone turns up and
#: whether they are licensed to do the work at all — a cheap contractor without an
#: EMA Licensed Electrical Worker cannot legally carry out electrical minor works,
#: so price alone would recommend the wrong supplier.
CRITERIA = (
    "price",
    "response_time",
    "lead_time",
    "compliance",
    "payment_terms",
    "moq",
    "validity",
    "warranty",
    "risk",
)

#: Goods weighting — the original, unchanged, so the goods path scores exactly as it
#: always did. ``response_time`` and ``compliance`` are zero because neither applies.
DEFAULT_WEIGHTS_GOODS: dict[str, float] = {
    "price": 0.45,
    "response_time": 0.00,
    "lead_time": 0.20,
    "compliance": 0.00,
    "payment_terms": 0.10,
    "moq": 0.05,
    "validity": 0.05,
    "warranty": 0.05,
    "risk": 0.10,
}

#: Services weighting. Price still dominates — it is what the buyer has to justify —
#: but response time and accreditation carry real weight, and risk is raised because
#: a contractor entering your building is a different exposure from a parts supplier.
#: ``moq`` is zero: a minimum callout is a charge that already appears in the price,
#: not a quantity gate.
DEFAULT_WEIGHTS_SERVICE: dict[str, float] = {
    "price": 0.40,
    "response_time": 0.15,
    "lead_time": 0.05,
    "compliance": 0.10,
    "payment_terms": 0.05,
    "moq": 0.00,
    "validity": 0.05,
    "warranty": 0.05,
    "risk": 0.15,
}

#: Kept as the name most callers use. Goods, so nothing that referenced
#: ``DEFAULT_WEIGHTS`` changes behaviour.
DEFAULT_WEIGHTS: dict[str, float] = dict(DEFAULT_WEIGHTS_GOODS)


def default_weights(procurement_type: str | None = None) -> dict[str, float]:
    """Default weights for a procurement type. Unknown types get goods."""

    if (procurement_type or "").lower() == "service":
        return dict(DEFAULT_WEIGHTS_SERVICE)

    return dict(DEFAULT_WEIGHTS_GOODS)


class QuoteInput(BaseModel):
    """One supplier quote, exactly as submitted (nothing pre-converted)."""

    model_config = ConfigDict(from_attributes=True)

    quote_id: int
    supplier_name: str

    currency: str = "USD"
    unit: str = "pcs"
    unit_price: Decimal | None = None

    lead_time_days: int | None = None
    moq: int | None = None
    payment_terms: str | None = None
    incoterms: str | None = None
    validity_date: date | None = None
    warranty_months: int | None = None

    shipping_cost: Decimal | None = None
    duties: Decimal | None = None
    taxes: Decimal | None = None
    discount: Decimal | None = None

    # ------------------------------------------------------------- services
    #: Hours until someone is on site. The services equivalent of a lead time, and
    #: the single most useful number on a maintenance quote after the price.
    response_time_hours: int | None = None
    #: Attendance fee, charged whether or not billable work follows. Sits in the
    #: same slot as freight in the cost model: a real cost of getting the job done
    #: that is not part of the measured works.
    callout_charge: Decimal | None = None
    #: Hourly labour rate, for quotes that separate labour from materials.
    labour_rate: Decimal | None = None
    #: Percentage added to materials the contractor supplies.
    materials_markup_pct: Decimal | None = None
    #: Licences and certifications held. Scored against what the RFQ requires.
    compliance_accreditations: list[str] = Field(default_factory=list)
    #: GST or equivalent, as a percentage. When set and no explicit tax amount is
    #: given, tax is derived from it so the final cost is not a surprise.
    gst_rate: Decimal | None = None

    completeness: str = "complete"
    missing_fields: list[str] = Field(default_factory=list)

    #: "low" | "medium" | "high" — from the Supplier record.
    supplier_risk: str = "low"


class ComparisonInput(BaseModel):
    """Everything the engine needs for one RFQ."""

    rfq_id: int
    rfq_number: str = ""
    item_name: str = ""

    quantity: int = 1
    unit: str = "pcs"

    base_currency: str = "SGD"
    base_incoterms: str | None = None

    #: "service" | "goods". Selects the default weights and changes how the
    #: narrative describes the numbers; it does not change the arithmetic.
    #:
    #: Defaults to "goods" so the engine's behaviour is unchanged for any existing
    #: caller that does not state a type. The *product* defaults to "service" — the
    #: RFQ model does — and passes it explicitly. Keeping the library default
    #: conservative means adding this dimension could not silently reweight an
    #: existing comparison.
    procurement_type: str = "goods"

    #: Accreditations the buyer requires. Drives the compliance score.
    required_accreditations: list[str] = Field(default_factory=list)

    #: GST/tax percentage applied when a quote states a rate but no amount.
    gst_rate: Decimal | None = None

    #: Empty means "use the procurement type's defaults". Deliberately NOT populated
    #: with goods weights, because a truthy default would suppress the per-type
    #: fallback in the engine and silently score every services RFQ on goods weights.
    weights: dict[str, float] = Field(default_factory=dict)

    quotes: list[QuoteInput] = Field(default_factory=list)

    #: Today's date, injectable so tests are not clock-dependent.
    today: date | None = None


class CostBreakdown(BaseModel):
    """Where the landed-cost number came from, line by line."""

    goods: Decimal = Decimal("0")
    shipping: Decimal = Decimal("0")
    #: Attendance / callout fee. The services counterpart of freight.
    callout: Decimal = Decimal("0")
    duties: Decimal = Decimal("0")
    taxes: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")
    subtotal: Decimal = Decimal("0")
    total: Decimal = Decimal("0")

    #: True when tax was computed from the supplier's stated GST rate rather than
    #: taken from an explicit tax figure. Surfaced so the buyer can see which.
    tax_derived_from_rate: bool = False

    #: FX conversion applied to every line (from supplier currency into base).
    fx_rate: Decimal = Decimal("1")
    fx_from: str = "USD"
    fx_to: str = "USD"

    #: Incoterms rebasing applied, e.g. quoted DDP, compared on EXW.
    incoterms_from: str | None = None
    incoterms_to: str | None = None
    incoterms_factor: Decimal = Decimal("1")

    #: Total *before* Incoterms rebasing, in the base currency.
    total_before_incoterms: Decimal = Decimal("0")

    def model_dump_jsonable(self) -> dict[str, Any]:
        return {k: str(v) if isinstance(v, Decimal) else v for k, v in self.model_dump().items()}


class QuoteResult(BaseModel):
    """One scored, normalized quote."""

    quote_id: int
    supplier_name: str

    comparable: bool = True
    #: Why a quote was excluded from ranking (missing price, unknown currency…).
    exclusion_reason: str | None = None

    #: Original, exactly as submitted — never overwritten.
    currency_original: str
    unit_price_original: Decimal | None = None
    unit_original: str = "pcs"

    #: Normalized into the RFQ's currency and Incoterms basis.
    unit_price_base: Decimal | None = None
    total_base: Decimal | None = None
    unit_mismatch: bool = False

    lead_time_days: int | None = None
    moq: int | None = None
    payment_terms: str | None = None
    incoterms: str | None = None
    validity_date: date | None = None
    warranty_months: int | None = None
    supplier_risk: str = "low"

    # ------------------------------------------------------------- services
    response_time_hours: int | None = None
    callout_charge: Decimal | None = None
    labour_rate: Decimal | None = None
    materials_markup_pct: Decimal | None = None
    compliance_accreditations: list[str] = Field(default_factory=list)
    gst_rate: Decimal | None = None
    #: Accreditations the RFQ required but this supplier does not hold.
    missing_accreditations: list[str] = Field(default_factory=list)

    completeness: str = "complete"
    missing_fields: list[str] = Field(default_factory=list)
    #: Set when required fields are missing, phrased for the buyer's risk list.
    incompleteness_note: str | None = None

    breakdown: CostBreakdown = Field(default_factory=CostBreakdown)

    #: 0–100 per criterion; higher is always better.
    scores: dict[str, float] = Field(default_factory=dict)
    composite_score: float = 0.0

    rank: int | None = None
    risk_flags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def model_dump_jsonable(self) -> dict[str, Any]:
        data = self.model_dump()
        data["breakdown"] = self.breakdown.model_dump_jsonable()
        for key in (
            "unit_price_original",
            "unit_price_base",
            "total_base",
            "callout_charge",
            "labour_rate",
            "materials_markup_pct",
            "gst_rate",
        ):
            if data.get(key) is not None:
                data[key] = str(data[key])
        if data.get("validity_date") is not None:
            data["validity_date"] = data["validity_date"].isoformat()
        return data


class ComparisonResult(BaseModel):
    """The full scoring run for one RFQ."""

    rfq_id: int
    rfq_number: str = ""
    item_name: str = ""

    base_currency: str = "SGD"
    base_incoterms: str | None = None
    quantity: int = 0
    unit: str = "pcs"

    procurement_type: str = "service"
    required_accreditations: list[str] = Field(default_factory=list)

    weights: dict[str, float] = Field(default_factory=dict)
    fx_rates: dict[str, Any] = Field(default_factory=dict)

    results: list[QuoteResult] = Field(default_factory=list)

    recommended_quote_id: int | None = None
    backup_quote_id: int | None = None

    rationale: str = ""
    risks: list[str] = Field(default_factory=list)

    #: False when nothing could be ranked, or every ranked quote is incomplete.
    is_conclusive: bool = True

    def ranked(self) -> list[QuoteResult]:
        return sorted(
            (r for r in self.results if r.rank is not None),
            key=lambda r: r.rank or 0,
        )

    def by_id(self, quote_id: int) -> QuoteResult | None:
        for result in self.results:
            if result.quote_id == quote_id:
                return result
        return None

    @property
    def recommended(self) -> QuoteResult | None:
        if self.recommended_quote_id is None:
            return None
        return self.by_id(self.recommended_quote_id)

    def model_dump_jsonable(self) -> dict[str, Any]:
        data = self.model_dump()
        data["results"] = [r.model_dump_jsonable() for r in self.results]
        return data


def normalize_weights(
    weights: dict[str, float] | None,
    fallback: dict[str, float] | None = None,
) -> dict[str, float]:
    """Coerce arbitrary weights into a positive set summing to 1.0.

    Unknown keys are dropped and all-zero or missing input falls back to
    ``fallback`` (or the goods defaults), so a malformed per-RFQ override degrades to
    sensible defaults rather than producing a division by zero.
    """

    if fallback is None:
        fallback = DEFAULT_WEIGHTS_GOODS

    if not weights:
        return dict(fallback)

    filtered = {
        key: max(0.0, float(value))
        for key, value in weights.items()
        if key in CRITERIA and value is not None
    }

    total = sum(filtered.values())

    if total <= 0:
        return dict(fallback)

    # Fill any criterion the caller omitted with 0 so the output always has every
    # key — the UI renders a fixed set of rows.
    for criterion in CRITERIA:
        filtered.setdefault(criterion, 0.0)

    return {key: value / total for key, value in filtered.items()}
