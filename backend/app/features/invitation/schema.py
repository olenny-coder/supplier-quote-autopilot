"""Invitation schemas."""

from datetime import date
from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from app.features.supplier.schema import SupplierResponse


class InvitationCreate(BaseModel):
    """Invite one supplier to one RFQ."""

    supplier_id: int
    #: Defaults to the RFQ deadline plus the configured link TTL.
    expires_at: datetime | None = None


class InvitationsBulkCreate(BaseModel):
    supplier_ids: list[int] = Field(min_length=1, max_length=100)
    #: Send the form-link email immediately.
    send_now: bool = True


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rfq_id: int
    supplier_id: int

    #: The secret. Only ever returned to the authenticated buyer who owns it.
    token: str

    #: The full public URL to paste into an email or a chat message.
    form_link: str

    status: str

    sent_at: datetime | None
    last_sent_at: datetime | None
    responded_at: datetime | None
    expires_at: datetime | None

    reminder_count: int
    last_reminder_at: datetime | None
    view_count: int
    first_viewed_at: datetime | None

    created_at: datetime

    # ------------------------------------------------------- joined context
    supplier_name: str = ""
    supplier_contact_name: str | None = None
    supplier_contact_email: str = ""
    supplier_risk: str = "low"

    quote_id: int | None = None
    quote_completeness: str | None = None
    quote_unit_price: str | None = None
    quote_currency: str | None = None
    quote_lead_time_days: int | None = None
    missing_fields: list[str] = Field(default_factory=list)
    missing_field_labels: list[str] = Field(default_factory=list)
    blocking_question: str | None = None

    #: When the scheduler would next chase this supplier (null when it won't).
    next_reminder_at: datetime | None = None

    #: Plain-English explanation of the current state, for the dashboard.
    status_reason: str = ""


class InvitationWithSupplier(InvitationResponse):
    supplier: SupplierResponse | None = None


class InvitationPreview(BaseModel):
    """What a supplier sees before filling anything in — no secrets, no buyer data."""

    rfq_id: int
    rfq_number: str
    item_name: str
    specification: str
    quantity: int
    unit: str
    delivery_expectation: date
    deadline: datetime | None

    currency: str
    incoterms: str | None

    #: "service" or "goods". Drives which fields the supplier form renders.
    procurement_type: str = "service"

    #: Services. Where the work is, and what the supplier needs to know before they
    #: can price it — access hours, permits, escorts, lift availability. A rate quoted
    #: without knowing it is a working-hours job is not comparable to one that is.
    site_name: str | None = None
    site_address: str | None = None
    site_access_notes: str | None = None

    #: The buyer's own SLA expectation. Shown to the supplier as the bar to beat.
    required_response_hours: int | None = None

    #: Credentials the buyer requires. A quote missing one of these is still ranked,
    #: but its score is capped and the shortfall is stated in plain words.
    required_accreditations: list[str] = Field(default_factory=list)

    #: Tax handling, already phrased for the supplier.
    gst_rate: float | None = None
    tax_note: str = ""

    #: The rate bases that make sense for this RFQ, for the unit dropdown.
    rate_bases: list[str] = Field(default_factory=list)

    #: The RFQ's category, so the form can label itself ("Electrical Minor Works").
    category: str | None = None

    buyer_company: str
    buyer_contact_email: str | None
    buyer_contact_phone: str | None

    supplier_name: str
    contact_name: str | None

    #: Required fields the buyer asked for — shown as "required" markers.
    required_fields: list[str] = Field(default_factory=list)

    #: The same fields, worded for the supplier and for what is being bought. Served
    #: rather than derived in the browser so the form's wording and the follow-up
    #: email's wording cannot drift apart.
    required_field_labels: list[str] = Field(default_factory=list)

    #: True when a quote already exists for this invitation (re-submission).
    already_submitted: bool = False
    is_expired: bool = False
    expires_at: datetime | None = None

    #: Anti-spam configuration the form needs to render itself.
    honeypot_field: str = "company_website"
    captcha_provider: str = "none"
    captcha_site_key: str | None = None
    max_upload_mb: int = 10
    allowed_upload_extensions: list[str] = Field(default_factory=list)


class ResendResponse(BaseModel):
    invitation_id: int
    status: str
    sent_to: str
    message: str
    followup_id: int | None = None
