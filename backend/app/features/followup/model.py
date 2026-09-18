"""Follow-up records — the log of every chasing message, sent or pending.

One row per attempt, never one row per invitation, because the requirement is
"log all communication" and the buyer needs to see the sequence. The row is
created when the draft is written (``status="draft"``) and updated as it moves
through the approval/sending lifecycle, so a queued-but-unsent message is a real
object the buyer can inspect rather than an invisible side effect.

``kind`` distinguishes the two situations the brief calls out:

* ``no_response``     - the supplier has not submitted anything
* ``incomplete_quote``- the supplier submitted, but required fields are missing
* ``manual``          - the buyer clicked "Resend link" / "Send reminder"
* ``deadline_warning``- the RFQ deadline is approaching and nothing has arrived
"""

from datetime import datetime

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.mixins import TimestampMixin

FOLLOWUP_KINDS = (
    "no_response",
    "incomplete_quote",
    "deadline_warning",
    "manual",
)

#: draft    - written, awaiting buyer approval (AUTO_SEND_FOLLOWUPS=false)
#: queued   - approved/auto, waiting for the sender
#: sent     - delivered to the email provider
#: failed   - the provider rejected it
#: rejected - the buyer discarded the draft
#: skipped  - the snapshot said no action was needed
FOLLOWUP_STATUSES = ("draft", "queued", "sent", "failed", "rejected", "skipped")


class FollowUp(TimestampMixin, Base):
    __tablename__ = "follow_ups"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    rfq_id: Mapped[int] = mapped_column(
        ForeignKey("rfqs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    invitation_id: Mapped[int | None] = mapped_column(
        ForeignKey("invitations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    kind: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="no_response",
        server_default="no_response",
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="draft",
        server_default="draft",
        index=True,
    )

    #: Which reminder in the sequence this is (1-based). 0 for manual sends.
    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    to_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    subject: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    #: True when the copy came from the LLM rather than the deterministic template.
    #: Boolean rather than Integer 0/1: SQLite accepts either, but a real boolean
    #: column is what the comparison flags need for `IS true` filters to work on
    #: PostgreSQL, and mixing the two styles across the schema invites the mistake.
    llm_generated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    #: The specific fields this message asked for. Machine-checkable, so the
    #: dashboard can badge a follow-up with "asked for: MOQ, validity date".
    requested_fields: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    #: Provider message id once sent.
    provider_message_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    error: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    #: Who or what produced this row: "scheduler", "buyer", "api".
    triggered_by: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="scheduler",
        server_default="scheduler",
    )

    # -------------------------------------------------------------- relations
    rfq = relationship(
        "RFQ",
        back_populates="followups",
    )

    invitation = relationship(
        "Invitation",
        back_populates="followups",
    )

    supplier = relationship("Supplier")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<FollowUp id={self.id} kind={self.kind!r} status={self.status!r}>"
