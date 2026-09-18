"""Follow-up schemas."""

from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class FollowUpResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rfq_id: int
    invitation_id: int | None
    supplier_id: int | None

    kind: str
    status: str
    sequence: int
    triggered_by: str

    to_email: str
    subject: str
    body: str

    llm_generated: bool

    requested_fields: list[str] = Field(default_factory=list)
    requested_labels: list[str] = Field(default_factory=list)

    provider_message_id: str | None
    error: str | None

    scheduled_for: datetime | None
    approved_at: datetime | None
    sent_at: datetime | None
    created_at: datetime

    #: Joined context so the buyer's log is readable without extra requests.
    supplier_name: str = ""
    rfq_number: str = ""
    item_name: str = ""
    status_label: str = ""

    #: Why the agent decided this — carried from the FollowUpDecision.
    decision_reason: str | None = None


class FollowUpUpdate(BaseModel):
    """Let the buyer edit the copy before approving a queued draft."""

    subject: str | None = Field(default=None, min_length=1, max_length=512)
    body: str | None = Field(default=None, min_length=1, max_length=8000)


class FollowUpRejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class FollowUpActionResponse(BaseModel):
    followup: FollowUpResponse
    message: str


class ManualFollowUpRequest(BaseModel):
    """Buyer-triggered reminder or an ad-hoc message."""

    invitation_id: int
    #: "reminder" | "incomplete" | "custom"
    mode: str = Field(default="reminder", pattern="^(reminder|incomplete|custom)$")
    subject: str | None = Field(default=None, max_length=512)
    body: str | None = Field(default=None, max_length=8000)
    #: Send immediately, or queue for approval. Defaults to the configured
    #: AUTO_SEND_FOLLOWUPS setting when omitted.
    send_now: bool | None = None


class SchedulerTickResponse(BaseModel):
    status: str = "ok"
    scanned: int = 0
    drafted: int = 0
    sent: int = 0
    queued_for_approval: int = 0
    skipped: int = 0
    expired: int = 0
    failed: int = 0
    llm_calls: int = 0
    auto_send_enabled: bool = False
    llm_available: bool = False
    run_at: datetime | None = None
    actions: list[dict] = Field(default_factory=list)


class FollowUpStats(BaseModel):
    total: int = 0
    drafts_pending: int = 0
    sent: int = 0
    failed: int = 0
    rejected: int = 0
