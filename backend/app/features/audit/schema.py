"""Audit log request and response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict


class AuditActionOption(BaseModel):
    """One choice in the page's action filter."""

    action: str
    label: str
    count: int


class AuditRFQOption(BaseModel):
    """One choice in the page's RFQ filter.

    ``rfq_number`` is nullable because entries outlive their RFQ (the log records
    the deletion), and an entry with no RFQ at all — a supplier added to the
    directory — has no option here.
    """

    rfq_id: int
    rfq_number: str | None = None
    item_name: str | None = None


class AuditEntryResponse(BaseModel):
    """One line of the audit log, ready to render or export.

    ``action_label`` is resolved server-side from the action code so the CSV and
    the page cannot disagree about what "comparison.run" is called, and so a new
    action means editing one dictionary rather than two front ends.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime

    action: str
    action_label: str

    entity_type: str
    entity_id: int | None = None

    rfq_id: int | None = None
    rfq_number: str | None = None
    item_name: str | None = None

    actor_type: str
    actor_label: str

    summary: str
    detail: dict[str, Any] | None = None


class AuditLogResponse(BaseModel):
    """A page of the log, plus what the filter controls need to render."""

    entries: list[AuditEntryResponse]

    #: Rows matching the filters, ignoring paging — so the page can say "showing
    #: 50 of 213" instead of guessing from the length of one page.
    total: int
    limit: int
    offset: int

    #: Every action code present in *this workspace*, with its label, so the filter
    #: dropdown offers what actually happened rather than all 29 codes including
    #: ones this buyer will never trigger.
    available_actions: list[AuditActionOption]

    #: The RFQs this workspace has entries for, newest first — the other filter the
    #: page offers, and the reason an entry snapshots its RFQ number.
    available_rfqs: list[AuditRFQOption]
