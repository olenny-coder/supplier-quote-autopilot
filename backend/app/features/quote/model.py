from decimal import Decimal

from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.core.database import Base


class SupplierQuote(Base):
    __tablename__ = "supplier_quotes"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    rfq_id: Mapped[int] = mapped_column(
        ForeignKey(
            "rfqs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    supplier_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    lead_time: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    payment_terms: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    remarks: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )

    rfq = relationship(
        "RFQ",
        back_populates="quotes",
    )
