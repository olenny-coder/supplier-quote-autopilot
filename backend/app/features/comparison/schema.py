"""Comparison and approval schemas."""

from datetime import date
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import computed_field


class QuoteSummary(BaseModel):
    """Quote projection used by the dashboard tables."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rfq_id: int
    supplier_id: int | None
    invitation_id: int | None

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

    notes: str | None
    remarks: str | None
    attachments: list[dict] = Field(default_factory=list)

    source: str
    completeness: str
    missing_fields: list[str] = Field(default_factory=list)
    missing_field_labels: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    blocking_question: str | None

    normalized_currency: str | None
    normalized_unit_price: Decimal | None
    normalized_total_cost: Decimal | None
    composite_score: Decimal | None
    scores: dict[str, Any] | None

    submitted_at: datetime | None
    created_at: datetime

    #: RFQ quantity, injected so the UI can show a total without a second request.
    quantity: int = 0

    @computed_field
    @property
    def total_price(self) -> Decimal | None:
        """Preserved from the base codebase's QuoteResponse so the existing table works."""

        if self.unit_price is None:
            return None

        return self.unit_price * self.quantity


class ComparisonRunRequest(BaseModel):
    """Trigger a scoring run, optionally with ad-hoc weights."""

    weights: dict[str, float] | None = None
    #: Ask the LLM to write the narrative. Falls back to the deterministic
    #: rationale when no provider is configured.
    use_llm: bool = True


class ApprovalRequest(BaseModel):
    quote_id: int
    #: "approved" | "rejected" | "deferred"
    decision: str = Field(default="approved", pattern="^(approved|rejected|deferred)$")
    #: Required for an approval — the audit trail needs the reasoning, not just
    #: the outcome.
    note: str = Field(min_length=3, max_length=2000)


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rfq_id: int
    comparison_id: int | None
    quote_id: int | None
    decision: str
    note: str | None
    decided_by_email: str | None
    recommended_quote_id: int | None
    overrode_recommendation: bool
    awarded_total_cost: Decimal | None
    awarded_currency: str | None
    decided_at: datetime | None
    created_at: datetime

    #: Joined for readability.
    supplier_name: str | None = None
    quote_reference: str | None = None


class ComparisonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rfq_id: int

    base_currency: str
    base_incoterms: str | None
    quantity: int = 0
    unit: str = "pcs"

    weights: dict[str, float] | None
    fx_rates: dict[str, Any] | None

    results: list[dict] = Field(default_factory=list)

    recommended_quote_id: int | None
    backup_quote_id: int | None

    summary: str | None
    rationale: str | None
    risks: list[str] = Field(default_factory=list)

    is_conclusive: bool
    llm_model: str | None
    computed_by: str
    is_current: bool

    created_at: datetime
    updated_at: datetime

    #: Joined.
    rfq_number: str = ""
    item_name: str = ""
    recommended_supplier: str | None = None

    #: The buyer's decision, once made.
    approval: ApprovalResponse | None = None

    #: Set when a recommendation exists but the buyer has not approved anything.
    awaiting_approval: bool = False

    #: Warning raised when the run could only rank part of the field.
    warnings: list[str] = Field(default_factory=list)


class ComparisonListItem(BaseModel):
    id: int
    rfq_id: int
    rfq_number: str = ""
    item_name: str = ""
    recommended_quote_id: int | None
    recommended_supplier: str | None
    best_total_cost: str | None
    base_currency: str
    is_conclusive: bool
    created_at: datetime


class DashboardSummary(BaseModel):
    """The buyer's landing page."""

    rfqs_total: int = 0
    rfqs_open: int = 0
    rfqs_awaiting_approval: int = 0
    rfqs_awarded: int = 0

    suppliers_total: int = 0

    invitations_total: int = 0
    invitations_pending: int = 0
    invitations_submitted: int = 0
    invitations_incomplete: int = 0
    invitations_expired: int = 0

    quotes_total: int = 0
    quotes_complete: int = 0

    followups_total: int = 0
    followups_pending_approval: int = 0
    followups_sent: int = 0
    followups_failed: int = 0

    #: RFQs whose deadline is within the warning window.
    deadlines_soon: list[dict] = Field(default_factory=list)

    #: Suppliers who have not responded and are due a reminder.
    needs_attention: list[dict] = Field(default_factory=list)

    ai_available: bool = False
    auto_send_followups: bool = False
