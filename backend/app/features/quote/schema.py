"""Quote schemas.

The original seven fields keep their names and constraints, so the CSV/PDF
importers and the base codebase's tests are unaffected. Everything the supplier
form or the landed-cost model needs is added as optional.

``extra="forbid"`` on the write schemas is deliberate: pydantic's default is to
silently ignore unknown keys, which turns a client typo (``shipping`` instead of
``shipping_cost``) into a successful request that quietly drops the data. A 422 is
much cheaper to debug than a wrong landed cost.
"""

from datetime import date
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import computed_field
from pydantic import field_validator


class QuoteWriteBase(BaseModel):
    """Fields a buyer can set on a quote, from any source."""

    model_config = ConfigDict(extra="forbid")

    currency: str = Field(
        min_length=1,
        max_length=10,
    )

    lead_time: int | None = Field(
        default=None,
        ge=0,
        description="Mobilisation time in days. Optional: a services RFQ does not "
        "require it, and completeness flags it when the procurement type does.",
    )

    unit: str = Field(default="pcs", max_length=32)

    payment_terms: str | None = None

    remarks: str | None = Field(default=None, max_length=2000)

    incoterms: str | None = Field(default=None, max_length=16)

    moq: int | None = Field(default=None, ge=0)

    validity_date: date | None = None

    warranty_months: int | None = Field(default=None, ge=0)

    shipping_cost: Decimal | None = Field(default=None, ge=0)

    duties: Decimal | None = Field(default=None, ge=0)

    taxes: Decimal | None = Field(default=None, ge=0)

    discount: Decimal | None = Field(default=None, ge=0)

    contact_email: str | None = Field(default=None, max_length=255)

    notes: str | None = Field(default=None, max_length=4000)

    # ------------------------------------------------------------- services
    # A services quote prices differently from a goods quote: a rate against a
    # basis, an attendance promise, and often a callout charge and a labour rate on
    # top. Every one of these is optional at the schema level, so a goods quote and
    # a partially-filled services quote are both accepted.

    #: The SLA, in hours. The single biggest differentiator between two otherwise
    #: identical maintenance quotes.
    response_time_hours: int | None = Field(default=None, ge=0)

    #: Fixed attendance charge. Kept separate from the price because a low rate with
    #: a large callout is the classic way a maintenance quote looks cheapest and is
    #: not.
    callout_charge: Decimal | None = Field(default=None, ge=0)

    #: Hourly labour rate, when labour is priced separately from materials.
    labour_rate: Decimal | None = Field(default=None, ge=0)

    #: Percentage added to materials bought on the buyer's behalf.
    materials_markup_pct: Decimal | None = Field(default=None, ge=0, le=1000)

    #: Credentials the supplier claims. Compared against the RFQ's required set; a
    #: missing required one caps the quote's score rather than excluding it.
    compliance_accreditations: list[str] | None = Field(default=None, max_length=50)

    #: Tax rate applied, as a percentage. Used to derive the tax amount when the
    #: supplier states a rate but not a figure.
    gst_rate: Decimal | None = Field(default=None, ge=0, le=100)


class QuoteCreate(QuoteWriteBase):
    supplier_name: str = Field(
        min_length=1,
        max_length=255,
    )

    unit_price: Decimal = Field(
        gt=0,
        decimal_places=4,
    )


class QuoteUpdate(BaseModel):
    """Partial update — every field optional, unknown fields rejected."""

    model_config = ConfigDict(extra="forbid")

    supplier_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    unit_price: Decimal | None = Field(
        default=None,
        gt=0,
        decimal_places=4,
    )

    currency: str | None = Field(
        default=None,
        min_length=1,
        max_length=10,
    )

    lead_time: int | None = Field(
        default=None,
        ge=0,
    )

    unit: str | None = Field(default=None, max_length=32)

    payment_terms: str | None = None

    remarks: str | None = None

    incoterms: str | None = Field(default=None, max_length=16)

    moq: int | None = Field(default=None, ge=0)

    validity_date: date | None = None

    warranty_months: int | None = Field(default=None, ge=0)

    shipping_cost: Decimal | None = Field(default=None, ge=0)

    duties: Decimal | None = Field(default=None, ge=0)

    taxes: Decimal | None = Field(default=None, ge=0)

    discount: Decimal | None = Field(default=None, ge=0)

    contact_email: str | None = Field(default=None, max_length=255)

    notes: str | None = Field(default=None, max_length=4000)

    # ------------------------------------------------------------- services
    response_time_hours: int | None = Field(default=None, ge=0)

    callout_charge: Decimal | None = Field(default=None, ge=0)

    labour_rate: Decimal | None = Field(default=None, ge=0)

    materials_markup_pct: Decimal | None = Field(default=None, ge=0, le=1000)

    compliance_accreditations: list[str] | None = Field(default=None, max_length=50)

    gst_rate: Decimal | None = Field(default=None, ge=0, le=100)

    completeness: str | None = Field(
        default=None,
        pattern="^(complete|incomplete|flagged)$",
    )


class QuoteResponse(BaseModel):
    """Kept for backwards compatibility with the base codebase's shape.

    The dashboard now uses :class:`app.features.comparison.schema.QuoteSummary`,
    which carries the normalized figures, but this projection is retained (and
    still computes ``total_price``) so any existing consumer keeps working.
    """

    id: int

    rfq_id: int

    supplier_name: str

    unit_price: Decimal | None

    currency: str

    lead_time: int | None

    payment_terms: str | None

    remarks: str | None

    quantity: int

    model_config = ConfigDict(
        from_attributes=True,
    )

    @computed_field
    @property
    def total_price(self) -> Decimal | None:
        if self.unit_price is None:
            return None

        return self.unit_price * self.quantity


class QuoteAttachment(BaseModel):
    """One uploaded file attached to a quote."""

    key: str
    filename: str
    content_type: str
    size: int
    url: str


class QuoteDetail(BaseModel):
    """Single-quote view including the parse provenance and cost breakdown."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_number: str | None
    supplier_name: str
    contact_email: str | None

    unit_price: Decimal | None
    currency: str
    unit: str
    lead_time: int | None
    payment_terms: str | None
    incoterms: str | None
    moq: int | None
    validity_date: date | None
    warranty_months: int | None

    shipping_cost: Decimal | None
    duties: Decimal | None
    taxes: Decimal | None
    discount: Decimal | None

    # ------------------------------------------------------------- services
    response_time_hours: int | None = None
    callout_charge: Decimal | None = None
    labour_rate: Decimal | None = None
    materials_markup_pct: Decimal | None = None
    compliance_accreditations: list[str] = Field(default_factory=list)
    gst_rate: Decimal | None = None

    notes: str | None
    attachments: list[QuoteAttachment] = Field(default_factory=list)

    source: str
    completeness: str
    missing_fields: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    blocking_question: str | None
    normalized_currency: str | None
    normalized_unit_price: Decimal | None
    normalized_total_cost: Decimal | None
    cost_breakdown: dict | None
    scores: dict | None
    composite_score: Decimal | None

    parse_confidence: Decimal | None
    unparsed_notes: str | None

    submitted_at: datetime | None
    created_at: datetime

    @field_validator(
        "attachments",
        "compliance_accreditations",
        "missing_fields",
        "risk_flags",
        mode="before",
    )
    @classmethod
    def _empty_list_for_null(cls, value: object) -> object:
        """A JSON column that was never written is NULL, not ``[]``.

        Without this, ``from_attributes`` validation fails on a quote whose list
        column is NULL — a 500 on a read endpoint rather than an empty list.
        """

        return [] if value is None else value
