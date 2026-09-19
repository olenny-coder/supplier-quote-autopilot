"""Public form schemas — the only API surface a supplier ever touches."""

from datetime import date

from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import Field


class PublicQuoteSubmit(BaseModel):
    """A supplier's submission.

    Every commercial field is optional at the schema level, because "incomplete" is
    a first-class state: a supplier who submits only a price is tracked and
    followed up, not rejected. Validation that matters (non-negative numbers,
    sensible lengths) still applies.
    """

    # ---- who is quoting ----------------------------------------------------
    supplier_name: str | None = Field(default=None, max_length=255)
    contact_email: EmailStr | None = None
    contact_name: str | None = Field(default=None, max_length=255)

    # ---- commercials -------------------------------------------------------
    currency: str | None = Field(default=None, max_length=10)
    unit_price: str | None = Field(default=None, max_length=64)
    unit: str | None = Field(default=None, max_length=32)

    lead_time: str | None = Field(default=None, max_length=64)
    moq: str | None = Field(default=None, max_length=64)
    payment_terms: str | None = Field(default=None, max_length=255)
    incoterms: str | None = Field(default=None, max_length=64)
    validity_date: str | None = Field(default=None, max_length=64)
    warranty_months: str | None = Field(default=None, max_length=64)

    shipping_cost: str | None = Field(default=None, max_length=64)
    duties: str | None = Field(default=None, max_length=64)
    taxes: str | None = Field(default=None, max_length=64)
    discount: str | None = Field(default=None, max_length=64)

    # ---- services ----------------------------------------------------------
    # Building maintenance and minor works. Every numeric value is a *string* on
    # purpose: a supplier types "within 4 hours" or "15%", and normalizing that is
    # the parser's job, not the schema's. A 422 on "same day" would lose the whole
    # submission.
    #
    # These are part of a PUBLIC contract — the supplier form and anything a supplier
    # wires up themselves post to it — so both spellings of the three fields whose
    # names are not obvious are accepted. Pydantic's default is to *ignore* unknown
    # keys, so a client that guessed wrong would receive a 201 while its SLA and
    # accreditations were dropped on the floor, and since a services RFQ requires a
    # response time, the quote would be stored incomplete and the buyer would chase a
    # supplier who had already answered. Accepting both spellings costs three fields
    # and removes that failure mode entirely; the parser's alias table already maps
    # them onto one canonical field.
    response_time_hours: str | None = Field(default=None, max_length=64)
    callout_charge: str | None = Field(default=None, max_length=64)
    labour_rate: str | None = Field(default=None, max_length=64)
    materials_markup_pct: str | None = Field(default=None, max_length=64)
    #: Either a list (the form's chips) or a delimited string (a hand-rolled client).
    compliance_accreditations: list[str] | str | None = None
    gst_rate: str | None = Field(default=None, max_length=64)

    #: Compatibility aliases. The buyer's RFQ field names, accepted so a client that
    #: reads its vocabulary off `/rfqs/{id}` still works.
    response_time: str | None = Field(default=None, max_length=64)
    materials_markup: str | None = Field(default=None, max_length=64)
    accreditations: str | None = Field(default=None, max_length=1000)

    #: Free-text notes. Parsed by the quote-parser agent.
    notes: str | None = Field(default=None, max_length=4000)

    # ---- anti-spam ---------------------------------------------------------
    #: The honeypot. Must stay empty; the field name is configurable so the form
    #: and the server cannot drift apart.
    company_website: str | None = Field(default=None, max_length=255)
    captcha_token: str | None = Field(default=None, max_length=4096)

    #: Keys of files already uploaded via POST .../attachments.
    attachment_keys: list[str] = Field(default_factory=list, max_length=10)


class PublicQuoteResponse(BaseModel):
    """What the supplier sees after submitting."""

    reference_number: str
    submitted_at: date | None = None

    supplier_name: str
    item_name: str
    rfq_number: str

    unit_price: str | None = None
    currency: str | None = None
    lead_time_days: int | None = None

    #: Confirmed back to the supplier so they can see their SLA and credentials were
    #: recorded — the two service fields most often mis-entered.
    response_time_hours: int | None = None
    accreditations: list[str] = Field(default_factory=list)

    completeness: str = "complete"
    #: Supplier-facing phrasing of anything still missing, so they can fix it now.
    missing_field_labels: list[str] = Field(default_factory=list)
    message: str = ""

    #: Usually false: a resubmission amends the existing quote.
    created: bool = True


class AttachmentUploadResponse(BaseModel):
    key: str
    filename: str
    content_type: str
    size: int
    url: str


class LinkStatusResponse(BaseModel):
    """Cheap poll endpoint so the buyer's dashboard can show "opened, not submitted"."""

    status: str
    opened: bool
    submitted: bool
    is_expired: bool
    expires_at: str | None = None
