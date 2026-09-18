"""Invitations — the tokenized public form link issued to one supplier for one RFQ.

This is the join that makes the whole flow work: it is the unit of "who has been
asked", "who has responded", and "who still needs a reminder". It is also the
only thing the public form is authenticated by — an unguessable token, not a
login (see ``app/features/public_form``).
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.mixins import TimestampMixin

#: Pending    - link issued, nothing received
#: Submitted  - a complete quote was received
#: Incomplete - a quote arrived but is missing required fields
#: Expired    - the deadline or link TTL passed with no complete quote
#: Declined   - the supplier told the buyer they will not quote
#: Cancelled  - the buyer withdrew the invitation
INVITATION_STATUSES = (
    "pending",
    "submitted",
    "incomplete",
    "expired",
    "declined",
    "cancelled",
)

OPEN_STATUSES = ("pending", "incomplete")


class Invitation(TimestampMixin, Base):
    __tablename__ = "invitations"

    __table_args__ = (
        UniqueConstraint("rfq_id", "supplier_id", name="uq_invitation_rfq_supplier"),
    )

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

    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: The secret in /quote/{rfq_id}/{token}. Unique and indexed for O(1) lookup.
    token: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )

    #: Denormalised for the dashboard's "who has been contacted" view, so we can
    #: say "never sent" without joining the FollowUp table.
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    #: Link expiry (distinct from the RFQ deadline: the link can outlive it).
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    #: Lightweight view analytics — useful for "opened but did not submit".
    first_viewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    view_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    reminder_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    last_reminder_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    #: Bumped whenever the buyer manually resends, so the scheduler's interval
    #: clock restarts instead of firing an automated reminder immediately after.
    last_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # -------------------------------------------------------------- relations
    rfq = relationship(
        "RFQ",
        back_populates="invitations",
    )

    supplier = relationship(
        "Supplier",
        back_populates="invitations",
    )

    quote = relationship(
        "SupplierQuote",
        back_populates="invitation",
        uselist=False,
    )

    followups = relationship(
        "FollowUp",
        back_populates="invitation",
        cascade="all, delete-orphan",
    )

    # --------------------------------------------------------------- helpers
    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Invitation id={self.id} rfq={self.rfq_id} status={self.status!r}>"
