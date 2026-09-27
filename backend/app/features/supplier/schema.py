"""Supplier schemas."""

from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import EmailStr
from pydantic import Field

RISK_PATTERN = "^(low|medium|high)$"


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    contact_name: str | None = Field(default=None, max_length=255)
    contact_email: EmailStr
    phone: str | None = Field(default=None, max_length=64)
    website: str | None = Field(default=None, max_length=512)
    country: str | None = Field(default=None, max_length=128)
    city: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=2000)
    risk_rating: str = Field(default="low", pattern=RISK_PATTERN)
    external_ref: str | None = Field(default=None, max_length=128)


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    contact_name: str | None = Field(default=None, max_length=255)
    contact_email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=64)
    website: str | None = Field(default=None, max_length=512)
    country: str | None = Field(default=None, max_length=128)
    city: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=2000)
    risk_rating: str | None = Field(default=None, pattern=RISK_PATTERN)
    external_ref: str | None = Field(default=None, max_length=128)


class SupplierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    contact_name: str | None
    contact_email: str
    phone: str | None
    website: str | None
    country: str | None
    city: str | None
    notes: str | None
    risk_rating: str
    external_ref: str | None
    created_at: datetime


class SupplierStats(SupplierResponse):
    """Supplier plus its activity across the buyer's RFQs."""

    invitations_total: int = 0
    invitations_responded: int = 0
    quotes_total: int = 0
    average_response_hours: float | None = None

    @property
    def response_rate(self) -> float | None:
        if not self.invitations_total:
            return None
        return round(self.invitations_responded / self.invitations_total, 3)


class BulkSupplierCreate(BaseModel):
    """Add several suppliers to an RFQ in one call (the common case: 3 quotes)."""

    suppliers: list[SupplierCreate] = Field(min_length=1, max_length=50)
    #: When true, reuse an existing supplier with the same contact email rather
    #: than failing the whole batch.
    reuse_existing: bool = True


class SupplierImportRequest(BaseModel):
    """A pasted or uploaded list of suppliers, as JSON rows."""

    model_config = ConfigDict(extra="forbid")

    suppliers: list[SupplierCreate] = Field(min_length=1, max_length=500)

    #: What to do when the contact email is already in the directory.
    #:
    #: "skip" is the default because re-uploading is the *normal* case — someone
    #: adds a column to their spreadsheet and imports it again. Silently
    #: overwriting the notes, risk rating and reference they curated by hand would
    #: be the worst possible default. "update" is there for when that is what you
    #: actually want.
    on_duplicate: str = Field(default="skip", pattern="^(skip|update)$")


class SupplierImportRowError(BaseModel):
    """One row that could not be imported, and why.

    Row-level rather than all-or-nothing: a 300-line directory export with four bad
    addresses should import 296 suppliers and tell the buyer which four to fix. A
    single failure rejecting the whole file is how a bulk upload becomes useless.
    """

    row: int
    email: str | None = None
    name: str | None = None
    reason: str


class SupplierImportResponse(BaseModel):
    """What happened, row by row."""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    total: int = 0

    errors: list[SupplierImportRowError] = Field(default_factory=list)

    #: The suppliers this import touched, so the UI can highlight them without a
    #: second request. Not the whole directory.
    imported: list[SupplierResponse] = Field(default_factory=list)

    message: str = ""
