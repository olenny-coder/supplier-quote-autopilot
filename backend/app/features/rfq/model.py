"""RFQ (Request for Quotation).

Extended in place from the base codebase: every original column is retained with
its original nullability so the existing manual-entry, CSV, and PDF import paths
keep working untouched. The new columns are the ones the autopilot needs —
deadline, required-field contract, and scoring weights.
"""

from datetime import date
from datetime import datetime

from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.mixins import TimestampMixin
from app.core.mixins import generate_rfq_number

RFQ_STATUSES = ("draft", "open", "closed", "awarded", "cancelled")

#: The field contract a supplier's submission is checked against. Kept as plain
#: strings (not an Enum) so new fields can be added without a migration.
DEFAULT_REQUIRED_FIELDS = [
    "unit_price",
    "currency",
    "lead_time",
    "moq",
    "payment_terms",
    "incoterms",
    "validity_date",
]


class RFQ(TimestampMixin, Base):
    __tablename__ = "rfqs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    # ---------------------------------------------------------------- tenancy
    # Nullable so the base codebase's direct constructions keep working; the
    # API always sets it, and unowned RFQs are legacy/imported records.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    #: Human-readable reference, e.g. RFQ-2026-8F3A21C4. Also the middle segment
    #: of a supplier's confirmation number (SQ-<rfq_number>-<invitation id>).
    rfq_number: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=generate_rfq_number,
        index=True,
    )

    # ------------------------------------------------------------- item detail
    item_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    specification: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    #: Unit of measure the quantity is expressed in ("pcs", "kg", "m", ...).
    unit: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pcs",
        server_default="pcs",
    )

    #: Buyer's expected delivery (kept from the base codebase).
    delivery_expectation: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    # --------------------------------------------------------------- commercial
    #: Preferred currency for comparison. Supplier quotes in other currencies are
    #: converted into this one (see comparison/fx.py).
    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="USD",
        server_default="USD",
    )

    #: Preferred Incoterms (EXW / FOB / CIF / DDP ...). Quotes on other terms are
    #: adjusted to this basis for comparison (see comparison/incoterms.py).
    incoterms: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )

    #: Submission deadline — the scheduler stops (and expires) at this instant.
    deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    #: Which fields a submission must carry to count as complete.
    required_fields: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=lambda: list(DEFAULT_REQUIRED_FIELDS),
    )

    #: Per-RFQ override of the comparison weights, e.g. {"price": 0.5, ...}.
    scoring_weights: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="open",
        server_default="open",
        index=True,
    )

    #: Printed on the public form so the supplier sees who is asking.
    buyer_company: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    category: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )

    # -------------------------------------------------------------- relations
    owner = relationship(
        "User",
        back_populates="rfqs",
    )

    quotes = relationship(
        "SupplierQuote",
        back_populates="rfq",
        cascade="all, delete-orphan",
    )

    invitations = relationship(
        "Invitation",
        back_populates="rfq",
        cascade="all, delete-orphan",
    )

    followups = relationship(
        "FollowUp",
        back_populates="rfq",
        cascade="all, delete-orphan",
    )

    comparisons = relationship(
        "Comparison",
        back_populates="rfq",
        cascade="all, delete-orphan",
    )

    # --------------------------------------------------------------- helpers
    @property
    def required_field_list(self) -> list[str]:
        return list(self.required_fields or DEFAULT_REQUIRED_FIELDS)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<RFQ id={self.id} number={self.rfq_number!r}>"
