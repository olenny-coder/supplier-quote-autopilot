"""User (buyer) accounts.

Auth is a simple email + password with a JWT bearer token. A ``User`` is also the
**tenant boundary**: every RFQ and Supplier belongs to exactly one user, and every
list endpoint scopes by ``user_id``. There is no team/organisation model in this
MVP (INTEGRATION_PLAN.md assumption A8).
"""

from sqlalchemy import Boolean
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.mixins import TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    #: PBKDF2 hash — see app/core/security.py. Never returned by any schema.
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    #: Printed on the public supplier form and used as the follow-up signature.
    company_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="My Company",
    )

    #: Shown on the supplier confirmation page so they know who to contact.
    contact_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    contact_phone: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    rfqs = relationship(
        "RFQ",
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    suppliers = relationship(
        "Supplier",
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User id={self.id} email={self.email!r}>"
