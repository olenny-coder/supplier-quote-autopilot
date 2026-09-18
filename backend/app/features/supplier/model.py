"""Supplier directory.

A ``Supplier`` is a reusable company record owned by one buyer. Inviting a
supplier to an RFQ creates an :class:`~app.features.invitation.model.Invitation`
that points at both, which is what makes the public form link unique per
(RFQ, supplier) pair.
"""

from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.mixins import TimestampMixin

RISK_RATINGS = ("low", "medium", "high")


class Supplier(TimestampMixin, Base):
    __tablename__ = "suppliers"

    __table_args__ = (
        UniqueConstraint("user_id", "contact_email", name="uq_supplier_user_email"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    contact_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    #: Where the tokenized form link is emailed.
    contact_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    website: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    country: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    city: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )

    #: Feeds the supplier-risk term of the comparison score.
    risk_rating: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="low",
        server_default="low",
    )

    #: Buyer's own code for the supplier (ERP/Vendor ID), for CSV export.
    external_ref: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    owner = relationship(
        "User",
        back_populates="suppliers",
    )

    invitations = relationship(
        "Invitation",
        back_populates="supplier",
        cascade="all, delete-orphan",
    )

    quotes = relationship(
        "SupplierQuote",
        back_populates="supplier",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Supplier id={self.id} name={self.name!r}>"
