"""Follow-up service — drafting, approving, sending, and the scheduler sweep.

The scheduler is an in-process interval loop **plus** an HTTP tick endpoint
(``POST /internal/scheduler/tick``). Both call :func:`run_scheduler`. Two drivers
exist because Render's free tier spins the service down after 15 idle minutes, so
a purely internal timer stops firing; an external free cron (cron-job.org,
GitHub Actions) can hit the endpoint to drive the same work reliably.

Idempotency matters here: overlapping runs must not double-send. Three guards:

* ``AUTO_SEND_FOLLOWUPS`` off by default, so a run produces *drafts*, not email.
* :func:`repository.find_recent_duplicate` suppresses a second draft of the same
  kind for the same invitation.
* The reminder counter is incremented in the same transaction as the send.
"""

import logging
from datetime import UTC
from datetime import datetime

from sqlalchemy.orm import Session

from agents.followup.drafter import draft_followup
from agents.followup.policy import decide
from agents.followup.schemas import FollowUpDecision
from agents.followup.schemas import InvitationSnapshot
from agents.followup.schemas import SchedulerSummary
from app.ai.completer import get_completer
from app.ai.completer import llm_available
from app.core.config import settings
from app.core.email import EmailMessage
from app.core.exceptions import BadRequestError
from app.core.exceptions import ExternalServiceError
from app.core.exceptions import NotFoundError
from app.core.mixins import utcnow
from app.features.followup import repository
from app.features.followup.model import FollowUp
from app.features.followup.snapshots import build_snapshot
from app.features.followup.snapshots import find_quote
from app.features.invitation.model import Invitation
from app.features.invitation.service import send_email_message_sync
from app.features.rfq.model import RFQ

logger = logging.getLogger(__name__)


class FollowUpService:
    # ------------------------------------------------------------- accessors
    @staticmethod
    def get_for_user(db: Session, user_id: int, followup_id: int) -> FollowUp:
        followup = repository.get_by_id(db, followup_id)

        if followup is None:
            raise NotFoundError("Follow-up not found")

        rfq = db.get(RFQ, followup.rfq_id)

        if rfq is None or (rfq.user_id is not None and rfq.user_id != user_id):
            raise NotFoundError("Follow-up not found")

        return followup

    # ------------------------------------------------------------- drafting
    @staticmethod
    def create_draft(
        db: Session,
        invitation: Invitation,
        decision: FollowUpDecision,
        *,
        triggered_by: str = "scheduler",
        snapshot: InvitationSnapshot | None = None,
        scheduled_for: datetime | None = None,
        llm_used: bool = False,
    ) -> FollowUp:
        """Persist the message the policy decided on, as a draft or queued row."""

        snapshot = snapshot or build_snapshot(db, invitation)

        draft = _draft_sync(
            snapshot,
            decision,
            total_sequences=max(1, len(settings.FOLLOWUP_INTERVALS_HOURS)),
            allow_llm=llm_used,
        )

        auto_send = settings.AUTO_SEND_FOLLOWUPS

        followup = FollowUp(
            rfq_id=invitation.rfq_id,
            invitation_id=invitation.id,
            supplier_id=invitation.supplier_id,
            kind=draft.kind,
            status="queued" if auto_send else "draft",
            sequence=decision.sequence,
            to_email=draft.to_email,
            subject=draft.subject,
            body=draft.body,
            llm_generated=bool(draft.llm_generated),
            requested_fields=list(draft.requested_fields) or None,
            scheduled_for=scheduled_for,
            triggered_by=triggered_by,
        )

        db.add(followup)
        db.commit()
        db.refresh(followup)

        return followup

    # -------------------------------------------------------------- sending
    @staticmethod
    def approve(
        db: Session,
        user_id: int,
        followup_id: int,
        *,
        subject: str | None = None,
        body: str | None = None,
    ) -> tuple[FollowUp, str]:
        """Buyer approves a queued draft (optionally edited) and it is sent."""

        followup = FollowUpService.get_for_user(db, user_id, followup_id)

        if followup.status == "sent":
            raise BadRequestError("This follow-up has already been sent.")

        if followup.status == "rejected":
            raise BadRequestError("This follow-up was discarded.")

        if subject:
            followup.subject = subject
        if body:
            followup.body = body

        message = "Follow-up sent."
        result = FollowUpService._deliver(db, followup)

        if result.status != "sent":
            message = result.error or "The email provider rejected the message."

        return result, message

    @staticmethod
    def reject(
        db: Session,
        user_id: int,
        followup_id: int,
        reason: str | None = None,
    ) -> FollowUp:
        followup = FollowUpService.get_for_user(db, user_id, followup_id)

        if followup.status == "sent":
            raise BadRequestError("This follow-up has already been sent.")

        followup.status = "rejected"
        followup.error = reason

        db.commit()
        db.refresh(followup)

        return followup

    @staticmethod
    def _deliver(db: Session, followup: FollowUp) -> FollowUp:
        """Send a follow-up and record the outcome on the same row."""

        message = EmailMessage(
            to_email=followup.to_email,
            subject=followup.subject,
            body=followup.body,
        )

        try:
            result = send_email_message_sync(message)
            followup.status = "sent"
            followup.sent_at = utcnow()
            followup.approved_at = followup.approved_at or utcnow()
            followup.provider_message_id = result.message_id
            followup.error = None
        except ExternalServiceError as exc:
            followup.status = "failed"
            followup.error = str(exc)
            logger.warning("Follow-up %s failed to send: %s", followup.id, exc)

        if followup.status == "sent":
            invitation = followup.invitation

            if invitation is not None:
                invitation.last_reminder_at = utcnow()

                if followup.kind in {"no_response", "deadline_warning"}:
                    invitation.reminder_count = (invitation.reminder_count or 0) + 1

        db.commit()
        db.refresh(followup)

        return followup

    # --------------------------------------------------- buyer-triggered send
    @staticmethod
    def create_manual(
        db: Session,
        user_id: int,
        invitation_id: int,
        *,
        mode: str = "reminder",
        subject: str | None = None,
        body: str | None = None,
        send_now: bool | None = None,
    ) -> FollowUp:
        """Buyer asks for a reminder right now, bypassing the interval schedule."""

        from app.features.invitation.service import InvitationService

        invitation = InvitationService.get_by_id(
            db=db, user_id=user_id, invitation_id=invitation_id
        )

        snapshot = build_snapshot(db, invitation)

        if mode == "custom":
            if not subject or not body:
                raise BadRequestError(
                    "A custom follow-up needs both a subject and a body."
                )

            followup = FollowUp(
                rfq_id=invitation.rfq_id,
                invitation_id=invitation.id,
                supplier_id=invitation.supplier_id,
                kind="manual",
                status="queued",
                sequence=0,
                to_email=invitation.supplier.contact_email,
                subject=subject,
                body=body,
                llm_generated=False,
                triggered_by="buyer",
            )

            db.add(followup)
            db.commit()
            db.refresh(followup)

            return FollowUpService._deliver(db, followup)

        # A reminder built by the agent, ignoring the "not due yet" check — the
        # buyer asked for it explicitly.
        if mode == "incomplete" and snapshot.missing_fields:
            decision = FollowUpDecision(
                action="request_missing_fields",
                kind="incomplete_quote",
                sequence=(snapshot.incomplete_reminder_count or 0) + 1,
                requested_fields=list(snapshot.missing_fields),
                requested_labels=list(snapshot.missing_field_labels),
                reason="You asked to chase the missing fields on this quote.",
            )
        else:
            decision = FollowUpDecision(
                action="remind",
                kind="no_response",
                sequence=snapshot.reminder_count + 1,
                reason="You asked to send a reminder now.",
            )

        followup = FollowUpService.create_draft(
            db,
            invitation,
            decision,
            triggered_by="buyer",
            snapshot=snapshot,
            llm_used=llm_available(),
        )

        followup.status = "queued"
        db.commit()
        db.refresh(followup)

        should_send = settings.AUTO_SEND_FOLLOWUPS if send_now is None else send_now

        if should_send:
            return FollowUpService._deliver(db, followup)

        return followup


# ------------------------------------------------------------------ scheduler
def run_scheduler(db: Session, *, now: datetime | None = None) -> SchedulerSummary:
    """One pass: expire overdue invitations, then draft or send the due follow-ups."""

    now = now or utcnow()

    summary = SchedulerSummary(
        run_at=now,
        auto_send_enabled=settings.AUTO_SEND_FOLLOWUPS,
        llm_available=llm_available(),
    )

    summary.expired = expire_overdue(db, now=now)

    invitations = repository.open_invitations(db)
    summary.scanned = len(invitations)

    # Decide once whether LLM drafting is worth attempting, rather than per item.
    llm_ok = summary.llm_available and settings.LLM_BATCH_MAX_CALLS > 0
    llm_calls = 0

    intervals = settings.FOLLOWUP_INTERVALS_HOURS

    for invitation in invitations:
        snapshot = build_snapshot(db, invitation)

        decision = decide(
            snapshot,
            now=now,
            intervals_hours=intervals,
            max_followups=settings.MAX_FOLLOWUPS_PER_INVITATION,
            max_incomplete_reminders=settings.MAX_INCOMPLETE_REMINDERS,
            before_deadline_hours=settings.FOLLOWUP_BEFORE_DEADLINE_HOURS,
        )

        if not decision.is_actionable():
            summary.skipped += 1

            if decision.escalate_to_buyer:
                summary.actions.append(
                    {
                        "invitation_id": invitation.id,
                        "supplier": snapshot.supplier_name,
                        "action": "escalate_to_buyer",
                        "reason": decision.reason,
                    }
                )

            continue

        # Idempotency: an overlapping run (internal timer + external cron) must not
        # produce a second identical draft.
        if repository.find_recent_duplicate(db, invitation.id, decision.kind) is not None:
            summary.skipped += 1
            continue

        use_llm = llm_ok and llm_calls < settings.LLM_BATCH_MAX_CALLS

        followup = FollowUpService.create_draft(
            db,
            invitation,
            decision,
            triggered_by="scheduler",
            snapshot=snapshot,
            llm_used=use_llm,
        )

        if use_llm and followup.llm_generated:
            llm_calls += 1

        summary.drafted += 1

        entry = {
            "invitation_id": invitation.id,
            "followup_id": followup.id,
            "supplier": snapshot.supplier_name,
            "action": decision.action,
            "kind": decision.kind,
            "reason": decision.reason,
            "requested": decision.requested_labels,
            "llm_generated": bool(followup.llm_generated),
        }

        if followup.status == "queued":
            followup = FollowUpService._deliver(db, followup)

            if followup.status == "sent":
                summary.sent += 1
                entry["result"] = "sent"
            else:
                summary.failed += 1
                entry["result"] = "failed"
                entry["error"] = followup.error
        else:
            summary.queued_for_approval += 1
            entry["result"] = "awaiting_approval"

        summary.actions.append(entry)

    summary.llm_calls = llm_calls

    logger.info(
        "Scheduler run: scanned=%s drafted=%s sent=%s queued=%s skipped=%s expired=%s",
        summary.scanned,
        summary.drafted,
        summary.sent,
        summary.queued_for_approval,
        summary.skipped,
        summary.expired,
    )

    return summary


def expire_overdue(db: Session, *, now: datetime | None = None) -> int:
    """Mark unanswered invitations expired and close RFQs past their deadline.

    Stop-follow-ups-when-the-deadline-passes is enforced by the policy too, but
    recording the state change means the dashboard shows *why* nothing is being
    chased instead of leaving rows in limbo forever.
    """

    now = now or utcnow()

    from sqlalchemy import select

    expired = 0

    for invitation in repository.open_invitations(db):
        if find_quote(db, invitation.id) is not None:
            continue

        expires_at = invitation.expires_at

        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        rfq = invitation.rfq
        deadline = rfq.deadline if rfq is not None else None

        if deadline is not None and deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)

        past_link = expires_at is not None and expires_at <= now
        past_deadline = deadline is not None and deadline <= now

        if past_link or past_deadline:
            invitation.status = "expired"
            expired += 1

    closed = 0

    if expired:
        stmt = select(RFQ).where(
            RFQ.status == "open",
            RFQ.deadline.is_not(None),
            RFQ.deadline <= now,
        )

        for rfq in db.scalars(stmt).all():
            rfq.status = "closed"
            closed += 1

        db.commit()

    return expired


# -------------------------------------------------------------------- helpers
def _draft_sync(
    snapshot: InvitationSnapshot,
    decision: FollowUpDecision,
    *,
    total_sequences: int,
    allow_llm: bool,
):
    """Run the async drafter from sync code."""

    import asyncio
    import concurrent.futures

    completer = get_completer() if allow_llm else None

    def run():
        return asyncio.run(
            draft_followup(
                snapshot,
                decision,
                llm=completer,
                total_sequences=total_sequences,
                allow_llm=allow_llm and completer is not None,
            )
        )

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return run()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(run).result()
