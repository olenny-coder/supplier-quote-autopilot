"""Comparison snapshots and award approvals.

A ``Comparison`` is an *immutable snapshot* of a scoring run: the normalized
quote figures, each quote's per-criterion scores, the weights used, and the AI
narrative. Storing the run (rather than recomputing on read) matters because
weights and FX rates change — a buyer must be able to see the basis on which a
recommendation was made.

An ``Approval`` is the human decision. Per the guardrails: **nothing is ever
auto-awarded**. A recommendation is a suggestion; the only way an RFQ reaches
``awarded`` is a row here, written by an authenticated buyer.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.mixins import TimestampMixin

APPROVAL_DECISIONS = ("approved", "rejected", "deferred")


class Comparison(TimestampMixin, Base):
    __tablename__ = "comparisons"

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

    #: Currency every quote was normalized into.
    base_currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="USD",
    )

    #: Incoterms basis every quote was adjusted to.
    base_incoterms: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )

    #: The weights actually applied, e.g. {"price": 0.45, "lead_time": 0.2, ...}
    weights: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    #: FX rates used, with their as-of date, so a stale rate is visible.
    fx_rates: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    #: The full per-quote result: costs, breakdowns, scores, risks.
    results: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    recommended_quote_id: Mapped[int | None] = mapped_column(
        ForeignKey("supplier_quotes.id", ondelete="SET NULL"),
        nullable=True,
    )

    #: Winner among quotes that are actually comparable (complete + priced).
    backup_quote_id: Mapped[int | None] = mapped_column(
        ForeignKey("supplier_quotes.id", ondelete="SET NULL"),
        nullable=True,
    )

    #: LLM-written narrative. Null when the LLM was unavailable — the
    #: deterministic ``rationale`` below is always present.
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    rationale: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    risks: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    #: False when the run could only rank a subset (missing prices, no FX rate).
    #:
    #: Boolean, NOT Integer. These flags are filtered with ``.is_(True)``, and
    #: SQLAlchemy compiles that to ``col IS true`` — which PostgreSQL rejects
    #: outright on an integer column ("argument of IS must be boolean"). Storing
    #: 0/1 works fine on SQLite, so the mistake is invisible in tests and fails
    #: only against the production database.
    is_conclusive: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("false"),
    )

    llm_model: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    computed_by: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="engine",
        server_default="engine",
    )

    #: See the note on ``is_conclusive``: Boolean, because it is filtered with
    #: ``.is_(True)`` in repository.latest_for_rfq.
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
        index=True,
    )

    # -------------------------------------------------------------- relations
    rfq = relationship(
        "RFQ",
        back_populates="comparisons",
    )

    approvals = relationship(
        "Approval",
        back_populates="comparison",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Comparison id={self.id} rfq={self.rfq_id}>"


class Approval(TimestampMixin, Base):
    __tablename__ = "approvals"

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

    comparison_id: Mapped[int | None] = mapped_column(
        ForeignKey("comparisons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    #: The quote being awarded/considered.
    quote_id: Mapped[int | None] = mapped_column(
        ForeignKey("supplier_quotes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    #: The human who decided. Nullable only so a deleted user does not destroy
    #: the audit trail.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    decided_by_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    decision: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="approved",
        server_default="approved",
        index=True,
    )

    #: Free-text justification captured from the buyer. Required by the API for
    #: an approval, because "why" is the part an audit needs.
    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    #: The recommended quote at decision time — preserved so overriding the
    #: recommendation is always visible after the fact.
    recommended_quote_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    #: True when the buyer approved a quote other than the recommendation.
    overrode_recommendation: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    #: Landed cost of the awarded quote at decision time.
    awarded_total_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(16, 2),
        nullable=True,
    )

    awarded_currency: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # -------------------------------------------------------------- relations
    comparison = relationship(
        "Comparison",
        back_populates="approvals",
    )

    rfq = relationship("RFQ")

    quote = relationship("SupplierQuote")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Approval id={self.id} decision={self.decision!r}>"
