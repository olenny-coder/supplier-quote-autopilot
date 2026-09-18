"""Follow-up agent schemas.

The decision types mirror ForgeFlow's ``ResponseAction`` (MIT, Copyright (c) 2026
JayleeBot) — see NOTICE — reduced to the three outcomes this product needs and
with the inputs made explicit so the policy is testable without a database.
"""

from datetime import date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import Field

#: What should happen to an invitation right now:
#:   skip                     - nothing is due, or nothing may be sent
#:   remind                   - the supplier has not submitted
#:   request_missing_fields   - the supplier submitted but left required fields blank
DecisionAction = Literal["skip", "remind", "request_missing_fields"]

#: Matches FollowUp.kind in the backend.
FollowUpKind = Literal[
    "no_response",
    "incomplete_quote",
    "deadline_warning",
    "manual",
]


class InvitationSnapshot(BaseModel):
    """Everything the policy needs about one invited supplier.

    Assembled by the backend from ORM rows so the policy itself never touches the
    database, and so a scheduler run can be tested by constructing these by hand.
    """

    invitation_id: int
    rfq_id: int

    supplier_name: str
    contact_name: str | None = None
    contact_email: str
    #: "low" | "medium" | "high" — high-risk suppliers get extra reminders.
    supplier_risk: str = "low"

    #: Invitation.status — pending / incomplete / submitted / expired / …
    invitation_status: str = "pending"

    rfq_number: str = ""
    item_name: str = ""
    rfq_quantity: int = 0
    rfq_unit: str = "pcs"

    #: The buyer's identity, for the email signature and the form link.
    buyer_company: str = ""
    buyer_contact_name: str | None = None
    buyer_contact_email: str | None = None

    form_link: str = ""

    sent_at: datetime | None = None
    last_sent_at: datetime | None = None
    responded_at: datetime | None = None
    deadline: datetime | None = None
    link_expires_at: datetime | None = None

    reminder_count: int = 0
    view_count: int = 0
    first_viewed_at: datetime | None = None

    #: Set when a quote exists but is incomplete.
    quote_completeness: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    missing_field_labels: list[str] = Field(default_factory=list)

    #: A supplier waiting on the buyer must be escalated, never chased.
    blocking_question: str | None = None

    #: How many incomplete-quote reminders have already been sent.
    incomplete_reminder_count: int = 0


class FollowUpDecision(BaseModel):
    """The policy's verdict on one invitation."""

    action: DecisionAction = "skip"
    kind: FollowUpKind = "no_response"

    #: Why this action (or why it was skipped). Always populated — it is shown to
    #: the buyer and written to the log, so it must read as a sentence.
    reason: str = ""

    #: 1-based position in the reminder sequence.
    sequence: int = 1

    #: The internal field names being requested; empty for a plain reminder.
    requested_fields: list[str] = Field(default_factory=list)
    #: The same fields, phrased the way a procurement professional would say them.
    requested_labels: list[str] = Field(default_factory=list)

    #: True when the supplier's own question blocks progress and the buyer must act.
    escalate_to_buyer: bool = False

    def is_actionable(self) -> bool:
        return self.action != "skip"


class FollowUpDraft(BaseModel):
    """A ready-to-send message."""

    subject: str
    body: str
    kind: FollowUpKind = "no_response"
    requested_fields: list[str] = Field(default_factory=list)
    requested_labels: list[str] = Field(default_factory=list)
    llm_generated: bool = False
    to_email: str = ""
    to_name: str | None = None

    def as_log_entry(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "subject": self.subject,
            "body": self.body,
            "to_email": self.to_email,
            "requested_fields": self.requested_fields,
            "llm_generated": self.llm_generated,
        }


class SchedulerSummary(BaseModel):
    """Result of one scheduler pass, returned by /internal/scheduler/tick."""

    scanned: int = 0
    drafted: int = 0
    sent: int = 0
    queued_for_approval: int = 0
    skipped: int = 0
    expired: int = 0
    failed: int = 0
    llm_calls: int = 0
    run_at: datetime | None = None
    actions: list[dict[str, object]] = Field(default_factory=list)


class ExpirySummary(BaseModel):
    """Result of expiring overdue invitations and closing stale RFQs."""

    invitations_expired: int = 0
    rfqs_closed: int = 0
    today: date | None = None
