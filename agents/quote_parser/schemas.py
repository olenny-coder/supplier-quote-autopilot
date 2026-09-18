"""Quote-parser schemas.

Adapted from ForgeFlow's extraction schema (MIT, Copyright (c) 2026 JayleeBot) —
see NOTICE. The shape is preserved (a flat set of nullable commercial fields plus
an explicit "what is missing" report) but the field set is this project's own:
single-line-item quotes submitted through a web form rather than multi-part
price breaks parsed out of an email thread.

The governing rule, carried over from ForgeFlow unchanged, is **verbatim-or-null**:
a commercial value is only recorded when it appears literally in the source text.
Anything absent, ambiguous, or "TBD" is ``None``. The ``evidence`` map exists so a
buyer can see the exact phrase each value came from.
"""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel
from pydantic import Field

#: What an inbound free-text block is doing.
#:   quote_data - it provides commercial values
#:   question   - it asks the buyer something before a value can be settled
#:   other      - neither (acknowledgement, out-of-office, chit-chat)
Classification = Literal["quote_data", "question", "other"]

#: Where a parsed value came from.
ParseSource = Literal["form", "llm", "heuristic", "merged"]

#: Fields the parser can produce, in the order they are presented to a buyer.
PARSABLE_FIELDS = (
    "supplier_name",
    "contact_email",
    "currency",
    "unit_price",
    "unit",
    "lead_time_days",
    "moq",
    "payment_terms",
    "incoterms",
    "validity_date",
    "warranty_months",
    "shipping_cost",
    "duties",
    "taxes",
    "discount",
    "notes",
)


class ParsedQuote(BaseModel):
    """Commercial fields recovered from a supplier's submission or free text."""

    # ------------------------------------------------------------ contact
    supplier_name: str | None = None
    contact_email: str | None = None

    # --------------------------------------------------------- commercials
    currency: str | None = None
    unit_price: Decimal | None = None
    unit: str | None = None

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

    notes: str | None = None

    # ------------------------------------------------------------- meta
    classification: Classification = "quote_data"

    #: 0–1. Low confidence is surfaced to the buyer rather than acted on.
    confidence: float = 0.0

    #: field -> the verbatim phrase the value came from.
    evidence: dict[str, str] = Field(default_factory=dict)

    #: Which layer produced each field, so an LLM guess is distinguishable from a
    #: value the supplier literally typed into a form field.
    field_sources: dict[str, str] = Field(default_factory=dict)

    #: Text the parser could not map to any field. Kept, never discarded.
    unparsed: str | None = None

    #: Set when the supplier is waiting on the buyer before a value can be fixed.
    #: Such a gap is *not* chased — it is escalated to the buyer.
    blocking_question: str | None = None

    source: ParseSource = "form"

    def provided_fields(self) -> dict[str, object]:
        """Only the fields that actually carry a value."""

        return {
            field: getattr(self, field)
            for field in PARSABLE_FIELDS
            if getattr(self, field, None) not in (None, "")
        }


class CompletenessReport(BaseModel):
    """The result of checking a submission against the RFQ's required fields."""

    is_complete: bool
    status: Literal["complete", "incomplete"] = "complete"

    #: Required fields with no answer.
    missing: list[str] = Field(default_factory=list)
    #: Required fields that were answered.
    satisfied: list[str] = Field(default_factory=list)

    #: Supplier-facing phrasing of each missing field, for the follow-up email.
    missing_labels: list[str] = Field(default_factory=list)

    #: Fields the supplier explicitly declined to answer ("no MOQ", "N/A"). These
    #: count as answered and must never be chased (ForgeFlow rule).
    declined: list[str] = Field(default_factory=list)

    #: Fields left blank that were not required — worth mentioning, never chasing.
    missing_optional: list[str] = Field(default_factory=list)

    summary: str = ""
