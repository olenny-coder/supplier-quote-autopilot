"""Reusable column mixins and shared column factories."""

import uuid
from datetime import UTC
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column


def utcnow() -> datetime:
    """Timezone-aware UTC now.

    Used instead of ``datetime.utcnow`` (deprecated, and naive) so comparisons
    against ``expires_at`` are meaningful.
    """

    return datetime.now(UTC)


class TimestampMixin:
    """``created_at`` / ``updated_at`` on every table."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


def generate_rfq_number() -> str:
    """Human-readable, collision-resistant RFQ reference, e.g. ``RFQ-2026-8F3A21C4``."""

    year = utcnow().year
    return f"RFQ-{year}-{uuid.uuid4().hex[:8].upper()}"


def short_token_column() -> Mapped[str]:
    return mapped_column(String(64), nullable=False)
