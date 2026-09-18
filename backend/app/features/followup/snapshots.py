"""Assemble :class:`InvitationSnapshot` objects from the database.

The follow-up policy is a pure function over a snapshot (see ``agents/followup``),
so exactly one place has to know how to build one. Keeping that here means the
scheduler, the dashboard's "next reminder" display, and the tests all reason about
the same inputs.
"""

from datetime import UTC
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.followup.schemas import InvitationSnapshot
from agents.quote_parser.completeness import label_for
from app.core.config import settings
from app.features.invitation.model import Invitation
from app.features.quote.model import SupplierQuote
from app.features.rfq.model import RFQ


def _as_aware(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; the policy compares against an aware now."""

    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value


def find_quote(db: Session, invitation_id: int) -> SupplierQuote | None:
    """Load an invitation's quote with an explicit query.

    Deliberately not ``invitation.quote``: the relationship is cached on the
    instance, so a session that has just created the quote can still see ``None``
    and conclude the supplier never responded — which silently suppresses the
    follow-up that was the whole point of the row.
    """

    return db.scalar(
        select(SupplierQuote).where(SupplierQuote.invitation_id == invitation_id)
    )


def build_snapshot(
    db: Session,
    invitation: Invitation,
    *,
    rfq: RFQ | None = None,
    quote: SupplierQuote | None = None,
    incomplete_reminder_count: int | None = None,
) -> InvitationSnapshot:
    """Build the policy's input for one invitation."""

    rfq = rfq or invitation.rfq
    supplier = invitation.supplier

    if quote is None:
        quote = find_quote(db, invitation.id)

    owner = rfq.owner if rfq is not None else None

    missing_fields: list[str] = []

    if quote is not None and quote.missing_fields:
        missing_fields = [str(field) for field in quote.missing_fields]

    if incomplete_reminder_count is None:
        incomplete_reminder_count = _count_incomplete_reminders(db, invitation.id)

    return InvitationSnapshot(
        invitation_id=invitation.id,
        rfq_id=invitation.rfq_id,
        supplier_name=supplier.name if supplier else "Supplier",
        contact_name=supplier.contact_name if supplier else None,
        contact_email=supplier.contact_email if supplier else "",
        supplier_risk=supplier.risk_rating if supplier else "low",
        invitation_status=invitation.status,
        rfq_number=rfq.rfq_number if rfq else "",
        item_name=rfq.item_name if rfq else "",
        rfq_quantity=rfq.quantity if rfq else 0,
        rfq_unit=rfq.unit if rfq else "pcs",
        buyer_company=(rfq.buyer_company if rfq else None)
        or (owner.company_name if owner else "Our company"),
        buyer_contact_name=(owner.full_name if owner else None),
        buyer_contact_email=(
            (owner.contact_email or owner.email) if owner else None
        ),
        form_link=settings.public_form_link(invitation.rfq_id, invitation.token),
        sent_at=_as_aware(invitation.sent_at),
        last_sent_at=_as_aware(invitation.last_sent_at),
        responded_at=_as_aware(invitation.responded_at),
        deadline=_as_aware(rfq.deadline) if rfq else None,
        link_expires_at=_as_aware(invitation.expires_at),
        reminder_count=invitation.reminder_count or 0,
        view_count=invitation.view_count or 0,
        first_viewed_at=_as_aware(invitation.first_viewed_at),
        quote_completeness=quote.completeness if quote else None,
        missing_fields=missing_fields,
        missing_field_labels=[label_for(field) for field in missing_fields],
        blocking_question=quote.blocking_question if quote else None,
        incomplete_reminder_count=incomplete_reminder_count,
    )


def _count_incomplete_reminders(db: Session, invitation_id: int) -> int:
    from sqlalchemy import func
    from sqlalchemy import select

    from app.features.followup.model import FollowUp

    return (
        db.scalar(
            select(func.count(FollowUp.id)).where(
                FollowUp.invitation_id == invitation_id,
                FollowUp.kind == "incomplete_quote",
                FollowUp.status.in_(("sent", "queued")),
            )
        )
        or 0
    )
