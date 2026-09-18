"""Follow-up queries and presentation helpers.

Keeping the read queries here (rather than in the service) lets the router, the
scheduler, and the dashboard share them without the service growing a second
responsibility.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.quote_parser.completeness import label_for
from app.features.followup.model import FollowUp
from app.features.followup.schema import FollowUpResponse
from app.features.invitation.model import Invitation
from app.features.rfq.model import RFQ
from app.features.supplier.model import Supplier

STATUS_LABELS = {
    "draft": "Awaiting your approval",
    "queued": "Queued to send",
    "sent": "Sent",
    "failed": "Failed to send",
    "rejected": "Discarded",
    "skipped": "No action needed",
}

KIND_LABELS = {
    "no_response": "Reminder — no quote received",
    "incomplete_quote": "Follow-up — quote incomplete",
    "deadline_warning": "Deadline warning",
    "manual": "Sent by you",
}


def followup_label(followup: FollowUp) -> str:
    """One human sentence describing what happened to this message."""

    status = STATUS_LABELS.get(followup.status, followup.status)

    if followup.status == "sent":
        return f"Sent to {followup.to_email}."

    if followup.status == "failed":
        return f"Could not send to {followup.to_email}: {followup.error or 'unknown error'}"

    if followup.status == "draft":
        return (
            f"Draft ready for {followup.to_email}. Review and approve it to send."
        )

    if followup.status == "queued":
        return f"Queued for {followup.to_email}."

    return f"{status} for {followup.to_email}."


def get_by_id(db: Session, followup_id: int) -> FollowUp | None:
    return db.get(FollowUp, followup_id)


def list_for_rfq(
    db: Session,
    rfq_id: int,
    *,
    status: str | None = None,
    limit: int = 200,
) -> list[FollowUp]:
    stmt = select(FollowUp).where(FollowUp.rfq_id == rfq_id)

    if status:
        stmt = stmt.where(FollowUp.status == status)

    stmt = stmt.order_by(FollowUp.created_at.desc(), FollowUp.id.desc()).limit(limit)

    return list(db.scalars(stmt).all())


def list_pending_drafts(db: Session, user_id: int, limit: int = 100) -> list[FollowUp]:
    stmt = (
        select(FollowUp)
        .join(RFQ, RFQ.id == FollowUp.rfq_id)
        .where(FollowUp.status == "draft", RFQ.user_id == user_id)
        .order_by(FollowUp.created_at.asc())
        .limit(limit)
    )

    return list(db.scalars(stmt).all())


def find_recent_duplicate(
    db: Session,
    invitation_id: int,
    kind: str,
    statuses: tuple[str, ...] = ("draft", "queued", "sent"),
) -> FollowUp | None:
    """Stop the scheduler creating the same draft twice.

    Because the scheduler can be driven both by its internal timer and by an
    external cron hitting ``/internal/scheduler/tick``, two runs can overlap. An
    existing unsent-or-sent message of the same kind for the same invitation means
    this run has nothing to add.
    """

    stmt = (
        select(FollowUp)
        .where(
            FollowUp.invitation_id == invitation_id,
            FollowUp.kind == kind,
            FollowUp.status.in_(statuses),
        )
        .order_by(FollowUp.id.desc())
        .limit(1)
    )

    return db.scalar(stmt)


def to_response(followup: FollowUp) -> FollowUpResponse:
    invitation = followup.invitation
    supplier = followup.supplier
    rfq = followup.rfq

    requested = [str(field) for field in (followup.requested_fields or [])]

    return FollowUpResponse(
        id=followup.id,
        rfq_id=followup.rfq_id,
        invitation_id=followup.invitation_id,
        supplier_id=followup.supplier_id,
        kind=followup.kind,
        status=followup.status,
        sequence=followup.sequence,
        triggered_by=followup.triggered_by,
        to_email=followup.to_email,
        subject=followup.subject,
        body=followup.body,
        llm_generated=bool(followup.llm_generated),
        requested_fields=requested,
        requested_labels=[label_for(field) for field in requested],
        provider_message_id=followup.provider_message_id,
        error=followup.error,
        scheduled_for=followup.scheduled_for,
        approved_at=followup.approved_at,
        sent_at=followup.sent_at,
        created_at=followup.created_at,
        supplier_name=(supplier.name if supplier else None)
        or (invitation.supplier.name if invitation and invitation.supplier else "")
        or followup.to_email,
        rfq_number=rfq.rfq_number if rfq else "",
        item_name=rfq.item_name if rfq else "",
        status_label=STATUS_LABELS.get(followup.status, followup.status),
    )


def open_invitations(db: Session, *, limit: int = 500) -> list[Invitation]:
    """Invitations the scheduler should consider: not terminal, link not cancelled."""

    stmt = (
        select(Invitation)
        .where(Invitation.status.in_(("pending", "incomplete")))
        .order_by(Invitation.id.asc())
        .limit(limit)
    )

    return list(db.scalars(stmt).all())


def supplier_names_for(db: Session, supplier_ids: list[int]) -> dict[int, str]:
    if not supplier_ids:
        return {}

    stmt = select(Supplier.id, Supplier.name).where(Supplier.id.in_(supplier_ids))

    return {row[0]: row[1] for row in db.execute(stmt).all()}
