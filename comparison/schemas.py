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
CRITERIA = (
    "price",
    "lead_time",
    "payment_terms",
    "moq",
    "validity",
    "warranty",
    "risk",
)

#: Defaults sum to 1.0. Overridable per RFQ (``RFQ.scoring_weights``) or globally
#: (``DEFAULT_SCORING_WEIGHTS_JSON``).
DEFAULT_WEIGHTS: dict[str, float] = {
    "price": 0.45,
    "lead_time": 0.20,
    "payment_terms": 0.10,
    "moq": 0.05,
    "validity": 0.05,
    "warranty": 0.05,
    "risk": 0.10,
}


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

    completeness: str = "complete"
    missing_fields: list[str] = Field(default_factory=list)

    #: "low" | "medium" | "high" — from the Supplier record.
    supplier_risk: str = "low"


class ComparisonInput(BaseModel):
    """Everything the engine needs for one RFQ."""

    rfq_id: int
    rfq_number: str = ""
    item_name: str = ""

    quantity: int
    unit: str = "pcs"

    base_currency: str = "USD"
    base_incoterms: str | None = None

    weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    quotes: list[QuoteInput] = Field(default_factory=list)

    #: Today's date, injectable so tests are not clock-dependent.
    today: date | None = None


class CostBreakdown(BaseModel):
    """Where the landed-cost number came from, line by line."""

    goods: Decimal = Decimal("0")
    shipping: Decimal = Decimal("0")
    duties: Decimal = Decimal("0")
    taxes: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")
    subtotal: Decimal = Decimal("0")
    total: Decimal = Decimal("0")

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

    base_currency: str = "USD"
    base_incoterms: str | None = None
    quantity: int = 0
    unit: str = "pcs"

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


def normalize_weights(weights: dict[str, float] | None) -> dict[str, float]:
    """Coerce arbitrary weights into a positive set summing to 1.0.

    Unknown keys are dropped and all-zero/missing input falls back to
    :data:`DEFAULT_WEIGHTS`, so a malformed per-RFQ override degrades to the
    default rather than producing a division by zero.
    """

    if not weights:
        return dict(DEFAULT_WEIGHTS)

    filtered = {
        key: max(0.0, float(value))
        for key, value in weights.items()
        if key in CRITERIA and value is not None
    }

    total = sum(filtered.values())

    if total <= 0:
        return dict(DEFAULT_WEIGHTS)

    # Fill any criterion the caller omitted with 0 so the output always has all
    # seven keys — the UI renders a fixed set of rows.
    for criterion in CRITERIA:
        filtered.setdefault(criterion, 0.0)

    return {key: value / total for key, value in filtered.items()}
