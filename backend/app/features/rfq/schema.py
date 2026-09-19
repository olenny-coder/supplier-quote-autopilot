"""RFQ schemas.

Extended in place: every field the base codebase used keeps its name, type and
required/optional status, so existing callers and tests are unaffected. New fields
carry defaults, which means an RFQ created the old way is still valid.

The vocabulary here is **services-first** — building maintenance and minor works —
because that is what this product is for. ``procurement_type`` switches the field
contract, the default scoring weights and the vocabulary; ``"goods"`` restores the
original behaviour exactly.
"""

from datetime import date
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import model_validator

from app.core.config import settings
from app.features.rfq import taxonomy
from app.features.rfq.model import DEFAULT_REQUIRED_FIELDS

#: Every field a buyer can place in an RFQ's required-field contract.
VALID_FIELDS = (
    # universal
    "unit_price",
    "currency",
    "unit",
    "payment_terms",
    "validity_date",
    # services
    "response_time",
    "callout_charge",
    "labour_rate",
    "materials_markup",
    "compliance",
    "gst_rate",
    # goods
    "lead_time",
    "moq",
    "incoterms",
    "warranty_months",
    "shipping_cost",
    "duties",
    "taxes",
    "discount",
)

STATUS_PATTERN = "^(draft|open|closed|awarded|cancelled)$"
PROCUREMENT_TYPE_PATTERN = "^(service|goods)$"


class InlineSupplier(BaseModel):
    """A supplier created as part of RFQ creation — the three-quotes-in-one-form case."""

    name: str = Field(min_length=1, max_length=255)
    contact_email: str = Field(min_length=3, max_length=255)
    contact_name: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=128)
    risk_rating: str = Field(default="low", pattern="^(low|medium|high)$")


class RFQCreate(BaseModel):
    # ---- original fields ---------------------------------------------------
    item_name: str = Field(
        min_length=1,
        max_length=255,
        description="The works or item being quoted for, e.g. 'Quarterly AHU servicing'.",
    )

    specification: str = Field(
        min_length=1,
        max_length=1000,
        description="Scope of works or specification.",
    )

    quantity: int = Field(
        gt=0,
        default=1,
        description="Units, points or visits. 1 for a lump-sum job.",
    )

    delivery_expectation: date = Field(description="Date the works are wanted by.")

    notes: str | None = None

    # ---- what is being bought ----------------------------------------------
    procurement_type: str = Field(
        default=taxonomy.DEFAULT_PROCUREMENT_TYPE,
        pattern=PROCUREMENT_TYPE_PATTERN,
        description="'service' for maintenance and minor works, 'goods' for supplies.",
    )

    unit: str | None = Field(
        default=None,
        max_length=32,
        description="Rate basis for services ('per job', 'per hour', 'per point'), "
        "unit of measure for goods ('pcs', 'set', 'm'). Defaults to 'per job' for a "
        "services RFQ and 'pcs' for a goods one.",
    )

    currency: str = Field(default="SGD", max_length=10)

    incoterms: str | None = Field(default=None, max_length=16)

    #: Quote submission deadline. Defaults to 14 days out when omitted.
    deadline: datetime | None = None

    required_fields: list[str] | None = Field(
        default=None,
        description="Fields a submission must carry to count as complete. Omit to "
        "use the procurement type's defaults.",
    )

    scoring_weights: dict[str, float] | None = None

    status: str = Field(default="open", pattern=STATUS_PATTERN)

    buyer_company: str | None = Field(default=None, max_length=255)

    category: str | None = Field(
        default=None,
        max_length=128,
        description="Service category, e.g. 'Electrical Minor Works'.",
    )

    # ---- site (services) ---------------------------------------------------
    site_name: str | None = Field(
        default=None, max_length=255, description="Building or site name."
    )
    site_address: str | None = Field(default=None, max_length=1000)
    site_access_notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Access hours, permits, escorts, lift booking.",
    )
    required_response_hours: int | None = Field(
        default=None,
        ge=0,
        description="Response time the buyer requires, in hours.",
    )
    required_accreditations: list[str] | None = Field(
        default=None,
        description="Licences the supplier must hold. A quote missing one is capped "
        "in scoring, because the work may not lawfully proceed without it.",
    )
    gst_rate: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        description="GST or equivalent, percent. Defaults to the server's "
        "DEFAULT_GST_RATE (9% in Singapore) for an SGD RFQ.",
    )

    # ---- convenience -------------------------------------------------------
    supplier_ids: list[int] | None = None
    new_suppliers: list[InlineSupplier] | None = None
    send_invitations: bool = True

    @property
    def effective_required_fields(self) -> list[str]:
        return list(
            self.required_fields
            or taxonomy.default_required_fields(self.procurement_type)
            or DEFAULT_REQUIRED_FIELDS
        )

    @model_validator(mode="after")
    def _default_unit_for_type(self) -> "RFQCreate":
        """Give an omitted ``unit`` the right default for what is being bought.

        A single hard-coded default cannot serve both paths. If it says "pcs", every
        services RFQ quietly asks for a rate per piece; if it says "per job", a goods
        RFQ is priced per job while its suppliers quote per piece — and the unit
        mismatch check then excludes *every* quote from ranking, so the comparison
        returns no recommendation at all. That is a silent, total failure of the
        feature, so the default follows the type.
        """

        if not self.unit:
            bases = taxonomy.rate_bases_for(self.procurement_type)

            self.unit = bases[0] if bases else "per job"

        return self


class RFQUpdate(BaseModel):
    item_name: str | None = Field(default=None, min_length=1, max_length=255)
    specification: str | None = Field(default=None, min_length=1, max_length=1000)
    quantity: int | None = Field(default=None, gt=0)
    delivery_expectation: date | None = None
    notes: str | None = None

    procurement_type: str | None = Field(default=None, pattern=PROCUREMENT_TYPE_PATTERN)
    unit: str | None = Field(default=None, max_length=32)
    currency: str | None = Field(default=None, max_length=10)
    incoterms: str | None = Field(default=None, max_length=16)
    deadline: datetime | None = None
    required_fields: list[str] | None = None
    scoring_weights: dict[str, float] | None = None
    status: str | None = Field(default=None, pattern=STATUS_PATTERN)
    buyer_company: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=128)

    site_name: str | None = Field(default=None, max_length=255)
    site_address: str | None = Field(default=None, max_length=1000)
    site_access_notes: str | None = Field(default=None, max_length=2000)
    required_response_hours: int | None = Field(default=None, ge=0)
    required_accreditations: list[str] | None = None
    gst_rate: Decimal | None = Field(default=None, ge=0, le=100)


class RFQResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rfq_number: str

    item_name: str
    specification: str
    quantity: int
    delivery_expectation: date
    notes: str | None

    # ---- what is being bought ----------------------------------------------
    procurement_type: str
    unit: str
    currency: str
    incoterms: str | None
    deadline: datetime | None
    required_fields: list[str] = Field(default_factory=list)
    scoring_weights: dict[str, Any] | None
    status: str
    buyer_company: str | None
    category: str | None

    # ---- site --------------------------------------------------------------
    site_name: str | None = None
    site_address: str | None = None
    site_access_notes: str | None = None
    required_response_hours: int | None = None
    required_accreditations: list[str] = Field(default_factory=list)
    gst_rate: Decimal | None = None

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

    #: Supplier-facing label for each required field. Sent so the dashboard does not
    #: hard-code the vocabulary — adding a field becomes a backend-only change.
    required_field_labels: list[str] = Field(default_factory=list)

    @property
    def response_rate(self) -> float | None:
        if not self.invitation_count:
            return None
        return round(self.responded_count / self.invitation_count, 3)


class RFQSummary(RFQResponse):
    """List-view projection: adds the recommendation headline."""

    recommended_supplier: str | None = None
    best_total_cost: str | None = None


class CriterionOption(BaseModel):
    """One scoring criterion, for the weight editor."""

    key: str
    label: str
    description: str


class MetaOptions(BaseModel):
    """Everything the forms and pickers need, in one request.

    Served from the API rather than hard-coded in the SPAs, so adding a service
    category or changing a default contract is a backend-only change.
    """

    base_currency: str = "SGD"
    default_procurement_type: str = "service"
    default_gst_rate: float = 9.0

    procurement_types: list[str] = Field(default_factory=list)
    service_categories: list[str] = Field(default_factory=list)
    goods_categories: list[str] = Field(default_factory=list)
    service_rate_bases: list[str] = Field(default_factory=list)
    goods_units: list[str] = Field(default_factory=list)
    common_accreditations: list[str] = Field(default_factory=list)

    required_fields: dict[str, list[str]] = Field(default_factory=dict)
    #: procurement type -> field -> supplier-facing label.
    #:
    #: Nested rather than flat because the wording genuinely differs: "moq" is a
    #: minimum order quantity for goods and a minimum callout charge for services.
    #: A single flat map has to be wrong for one of the two, and the buyer would see
    #: the wrong question on the required-fields picker.
    required_field_labels: dict[str, dict[str, str]] = Field(default_factory=dict)
    criteria: list[CriterionOption] = Field(default_factory=list)
    default_weights: dict[str, dict[str, float]] = Field(default_factory=dict)

    def resolved_gst_rate(self) -> float:
        return float(self.default_gst_rate or settings.DEFAULT_GST_RATE)


RFQCreate.model_rebuild()
