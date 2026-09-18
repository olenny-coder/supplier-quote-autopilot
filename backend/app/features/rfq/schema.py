"""RFQ schemas.

Extended in place: every field the base codebase used keeps its name, type, and
required/optional status, so existing callers and tests are unaffected. The new
fields carry defaults, which means an RFQ created the old way is still valid and
picks up sensible commercial defaults (USD, pcs, the standard required-field set).
"""

from datetime import date
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from app.features.rfq.model import DEFAULT_REQUIRED_FIELDS

VALID_FIELDS = (
    "unit_price",
    "currency",
    "unit",
    "lead_time",
    "moq",
    "payment_terms",
    "incoterms",
    "validity_date",
    "warranty_months",
    "shipping_cost",
    "duties",
    "taxes",
    "discount",
)

STATUS_PATTERN = "^(draft|open|closed|awarded|cancelled)$"


class RFQCreate(BaseModel):
    # ---- original fields ---------------------------------------------------
    item_name: str = Field(
        min_length=1,
        max_length=255,
    )

    specification: str = Field(
        min_length=1,
        max_length=1000,
    )

    quantity: int = Field(
        gt=0,
    )

    delivery_expectation: date

    notes: str | None = None

    # ---- new fields --------------------------------------------------------
    unit: str = Field(default="pcs", max_length=32)

    currency: str = Field(default="USD", max_length=10)

    incoterms: str | None = Field(default=None, max_length=16)

    #: Quote submission deadline. Defaults to 14 days out when omitted.
    deadline: datetime | None = None

    required_fields: list[str] | None = None

    scoring_weights: dict[str, float] | None = None

    status: str = Field(default="open", pattern=STATUS_PATTERN)

    buyer_company: str | None = Field(default=None, max_length=255)

    category: str | None = Field(default=None, max_length=128)

    #: Convenience: create the suppliers and their invitations in one call.
    supplier_ids: list[int] | None = None

    #: Convenience: create suppliers inline (name + email) and invite them.
    new_suppliers: list["InlineSupplier"] | None = None

    #: Email the form links as soon as the RFQ is created.
    send_invitations: bool = True

    @property
    def effective_required_fields(self) -> list[str]:
        return list(self.required_fields or DEFAULT_REQUIRED_FIELDS)


class InlineSupplier(BaseModel):
    """A supplier created as part of RFQ creation — the 3-quotes-in-one-form case."""

    name: str = Field(min_length=1, max_length=255)
    contact_email: str = Field(min_length=3, max_length=255)
    contact_name: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=128)
    risk_rating: str = Field(default="low", pattern="^(low|medium|high)$")


class RFQUpdate(BaseModel):
    item_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    specification: str | None = Field(
        default=None,
        min_length=1,
        max_length=1000,
    )

    quantity: int | None = Field(
        default=None,
        gt=0,
    )

    delivery_expectation: date | None = None

    notes: str | None = None

    unit: str | None = Field(default=None, max_length=32)
    currency: str | None = Field(default=None, max_length=10)
    incoterms: str | None = Field(default=None, max_length=16)
    deadline: datetime | None = None
    required_fields: list[str] | None = None
    scoring_weights: dict[str, float] | None = None
    status: str | None = Field(default=None, pattern=STATUS_PATTERN)
    buyer_company: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=128)


class RFQResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int

    rfq_number: str

    item_name: str

    specification: str

    quantity: int

    delivery_expectation: date

    notes: str | None

    unit: str
    currency: str
    incoterms: str | None
    deadline: datetime | None
    required_fields: list[str] = Field(default_factory=list)
    scoring_weights: dict[str, Any] | None
    status: str
    buyer_company: str | None
    category: str | None

    created_at: datetime
    updated_at: datetime

    #: Derived counters, filled by the service.
    quote_count: int = 0
    invitation_count: int = 0
    responded_count: int = 0
    pending_count: int = 0
    incomplete_count: int = 0

    #: True when at least one complete, priced quote exists.
    ready_to_compare: bool = False

    @property
    def response_rate(self) -> float | None:
        if not self.invitation_count:
            return None
        return round(self.responded_count / self.invitation_count, 3)


class RFQSummary(RFQResponse):
    """List-view projection: adds the recommendation headline."""

    recommended_supplier: str | None = None
    best_total_cost: str | None = None


RFQCreate.model_rebuild()
