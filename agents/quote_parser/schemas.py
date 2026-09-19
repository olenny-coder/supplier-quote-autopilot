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
    "response_time_hours",
    "lead_time_days",
    "moq",
    "callout_charge",
    "labour_rate",
    "materials_markup_pct",
    "payment_terms",
    "incoterms",
    "validity_date",
    "warranty_months",
    "compliance_accreditations",
    "gst_rate",
    "shipping_cost",
    "duties",
    "taxes",
    "discount",
    "notes",
)


def carries_value(value: object) -> bool:
    """True when a parsed value is an actual answer rather than an empty slot.

    Shared with the completeness checker so "the supplier answered" means exactly
    the same thing in both places. An empty list counts as *no answer*: a parse that
    produced no accreditations has not told the buyer anything.
    """

    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)

    return True


class ParsedQuote(BaseModel):
    """Commercial fields recovered from a supplier's submission or free text."""

    # ------------------------------------------------------------ contact
    supplier_name: str | None = None
    contact_email: str | None = None

    # --------------------------------------------------------- commercials
    currency: str | None = None
    unit_price: Decimal | None = None
    unit: str | None = None

    #: Services: the SLA — how fast someone attends site, in whole hours.
    response_time_hours: int | None = None

    lead_time_days: int | None = None
    moq: int | None = None
    payment_terms: str | None = None
    incoterms: str | None = None
    validity_date: date | None = None
    warranty_months: int | None = None

    # ------------------------------------------------- services, commercial
    #: Fixed attendance charge, separate from the works. The single most common
    #: hidden cost in a maintenance quote.
    callout_charge: Decimal | None = None
    #: Hourly labour rate, when the quote prices labour separately.
    labour_rate: Decimal | None = None
    #: Percentage added to materials the supplier buys on the buyer's behalf.
    materials_markup_pct: Decimal | None = None

    #: Credentials the supplier claims — LEW, bizSAFE, ISO, PUB and so on. Compared
    #: against the RFQ's required set; a missing required one caps the score.
    compliance_accreditations: list[str] = Field(default_factory=list)

    #: The tax rate the supplier applied. Used to derive the tax when they state a
    #: rate but no amount.
    gst_rate: Decimal | None = None

    shipping_cost: Decimal | None = None
    duties: Decimal | None = None
    taxes: Decimal | None = None
    discount: Decimal | None = None

    notes: str | None = None

    # ------------------------------------------------------------- meta
    #: ``None`` until some layer actually *decides*. A default of "quote_data" was
    #: a real bug: the heuristic layer always carried that default, so it won the
    #: merge and clobbered a correct "question" verdict from the classifier — which
    #: meant a supplier waiting on the buyer was recorded as ordinary quote data and
    #: then chased, the exact failure the follow-up rules exist to prevent.
    classification: Classification | None = None

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
            if carries_value(getattr(self, field, None))
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
