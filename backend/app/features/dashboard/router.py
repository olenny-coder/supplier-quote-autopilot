"""Dashboard router — the buyer's landing page in one request.

Counting client-side would mean the dashboard firing a request per RFQ, which is
the wrong shape for a backend that cold-starts in about a minute on Render's free
tier. One aggregate endpoint keeps first paint to a single round trip.
"""

from datetime import timedelta

from fastapi import APIRouter
from sqlalchemy import func
from sqlalchemy import select

from app.ai.completer import llm_available
from app.core.config import settings
from app.core.dependencies import CurrentUser
from app.core.dependencies import DBSession
from app.core.mixins import utcnow
from app.features.comparison import repository as comparison_repository
from app.features.comparison.schema import DashboardSummary
from app.features.followup.model import FollowUp
from app.features.invitation.model import Invitation
from app.features.quote.model import SupplierQuote
from app.features.rfq.model import RFQ
from app.features.supplier.model import Supplier

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)

#: An RFQ whose deadline is inside this window is surfaced as "closing soon".
DEADLINE_WARNING_HOURS = 72


@router.get(
    "/summary",
    response_model=DashboardSummary,
)
def get_summary(
    user: CurrentUser,
    db: DBSession,
) -> DashboardSummary:
    now = utcnow()

    def count(stmt) -> int:
        return db.scalar(stmt) or 0

    rfq_ids = [
        row[0]
        for row in db.execute(select(RFQ.id).where(RFQ.user_id == user.id)).all()
    ]

    summary = DashboardSummary(ai_available=llm_available())

    summary.auto_send_followups = settings.AUTO_SEND_FOLLOWUPS
    summary.rfqs_total = len(rfq_ids)
    summary.suppliers_total = count(
        select(func.count(Supplier.id)).where(Supplier.user_id == user.id)
    )

    if not rfq_ids:
        return summary

    summary.rfqs_open = count(
        select(func.count(RFQ.id)).where(
            RFQ.user_id == user.id, RFQ.status == "open"
        )
    )
    summary.rfqs_awarded = count(
        select(func.count(RFQ.id)).where(
            RFQ.user_id == user.id, RFQ.status == "awarded"
        )
    )

    # ---- invitations -------------------------------------------------------
    invite_rows = db.execute(
        select(Invitation.status, func.count(Invitation.id))
        .join(RFQ, RFQ.id == Invitation.rfq_id)
        .where(RFQ.user_id == user.id)
        .group_by(Invitation.status)
    ).all()

    for status, total in invite_rows:
        summary.invitations_total += total

        if status == "pending":
            summary.invitations_pending += total
        elif status == "submitted":
            summary.invitations_submitted += total
        elif status == "incomplete":
            summary.invitations_incomplete += total
        elif status == "expired":
            summary.invitations_expired += total

    # ---- quotes ------------------------------------------------------------
    summary.quotes_total = count(
        select(func.count(SupplierQuote.id)).where(
            SupplierQuote.rfq_id.in_(rfq_ids)
        )
    )
    summary.quotes_complete = count(
        select(func.count(SupplierQuote.id)).where(
            SupplierQuote.rfq_id.in_(rfq_ids),
            SupplierQuote.completeness == "complete",
            SupplierQuote.unit_price.is_not(None),
        )
    )

    # ---- follow-ups --------------------------------------------------------
    followup_rows = db.execute(
        select(FollowUp.status, func.count(FollowUp.id))
        .where(FollowUp.rfq_id.in_(rfq_ids))
        .group_by(FollowUp.status)
    ).all()

    for status, total in followup_rows:
        summary.followups_total += total

        if status == "draft":
            summary.followups_pending_approval += total
        elif status == "sent":
            summary.followups_sent += total
        elif status == "failed":
            summary.followups_failed += total

    # ---- RFQs awaiting a decision -----------------------------------------
    # "Awaiting approval" means a comparison recommended someone and no approval
    # has been recorded — the buyer's actual to-do list.
    from app.features.comparison.model import Approval

    approved_rfq_ids = {
        row[0]
        for row in db.execute(
            select(Approval.rfq_id).where(
                Approval.rfq_id.in_(rfq_ids), Approval.decision == "approved"
            )
        ).all()
    }

    recommended = db.execute(
        select(RFQ.id).where(
            RFQ.user_id == user.id, RFQ.status.in_(("open", "closed"))
        )
    ).all()

    for (rfq_id,) in recommended:
        comparison = comparison_repository.latest_for_rfq(db, rfq_id)

        if (
            comparison is not None
            and comparison.recommended_quote_id is not None
            and rfq_id not in approved_rfq_ids
        ):
            summary.rfqs_awaiting_approval += 1

    # ---- deadline watchlist -----------------------------------------------
    window_end = now + timedelta(hours=DEADLINE_WARNING_HOURS)

    soon = db.execute(
        select(RFQ.id, RFQ.rfq_number, RFQ.item_name, RFQ.deadline)
        .where(
            RFQ.user_id == user.id,
            RFQ.status == "open",
            RFQ.deadline.is_not(None),
            RFQ.deadline <= window_end,
        )
        .order_by(RFQ.deadline.asc())
        .limit(10)
    ).all()

    from app.features.rfq.service import RFQService

    count_map = RFQService.counts(db, [row[0] for row in soon])

    for rfq_id, rfq_number, item_name, deadline in soon:
        bucket = count_map.get(rfq_id, {})
        hours_left = (deadline - now).total_seconds() / 3600.0

        summary.deadlines_soon.append(
            {
                "rfq_id": rfq_id,
                "rfq_number": rfq_number,
                "item_name": item_name,
                "deadline": deadline.isoformat() if deadline else None,
                "hours_left": round(hours_left, 1),
                "overdue": hours_left < 0,
                "pending_suppliers": bucket.get("pending_count", 0),
                "incomplete_suppliers": bucket.get("incomplete_count", 0),
            }
        )

    # ---- who needs a nudge ------------------------------------------------
    stale = db.execute(
        select(Invitation, RFQ, Supplier)
        .join(RFQ, RFQ.id == Invitation.rfq_id)
        .join(Supplier, Supplier.id == Invitation.supplier_id)
        .where(
            RFQ.user_id == user.id,
            Invitation.status.in_(("pending", "incomplete")),
            Invitation.sent_at.is_not(None),
        )
        .order_by(Invitation.sent_at.asc())
        .limit(200)
    ).all()

    from agents.followup.policy import next_reminder_due_at
    from app.features.followup.snapshots import build_snapshot

    for invitation, rfq, supplier in stale:
        snapshot = build_snapshot(db, invitation, rfq=rfq)

        due_at = next_reminder_due_at(
            snapshot,
            intervals_hours=settings.FOLLOWUP_INTERVALS_HOURS,
            max_followups=settings.MAX_FOLLOWUPS_PER_INVITATION,
        )

        if invitation.status == "incomplete" or (
            due_at is not None and due_at <= now
        ):
            summary.needs_attention.append(
                {
                    "invitation_id": invitation.id,
                    "rfq_id": rfq.id,
                    "rfq_number": rfq.rfq_number,
                    "supplier_name": supplier.name,
                    "status": invitation.status,
                    "missing_fields": list(invitation.quote.missing_fields or [])
                    if invitation.quote is not None
                    else [],
                    "reminder_count": invitation.reminder_count or 0,
                    "next_reminder_at": due_at.isoformat() if due_at else None,
                    "reason": (
                        snapshot.missing_fields
                        and "Quote is incomplete"
                        or "No response yet"
                    ),
                }
            )

        if len(summary.needs_attention) >= 10:
            break

    return summary
