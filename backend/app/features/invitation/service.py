"""Invitation service — issuing, tracking, and resending tokenized form links."""

import asyncio
import concurrent.futures
import logging
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.quote_parser.completeness import label_for
from app.core.config import settings
from app.core.email import EmailMessage
from app.core.exceptions import BadRequestError
from app.core.exceptions import ConflictError
from app.core.exceptions import ExternalServiceError
from app.core.exceptions import InvitationExpiredError
from app.core.exceptions import NotFoundError
from app.core.mixins import utcnow
from app.core.security import generate_invitation_token
from app.features.followup.model import FollowUp
from app.features.invitation.messaging import build_invitation_email
from app.features.invitation.model import Invitation
from app.features.invitation.schema import InvitationPreview
from app.features.invitation.schema import InvitationResponse
from app.features.quote.model import SupplierQuote
from app.features.rfq import taxonomy
from app.features.rfq.model import RFQ
from app.features.supplier.model import Supplier

logger = logging.getLogger(__name__)


class InvitationService:
    # ------------------------------------------------------------- lookups
    @staticmethod
    def get_rfq(db: Session, user_id: int, rfq_id: int) -> RFQ:
        rfq = db.get(RFQ, rfq_id)

        # Legacy RFQs created before accounts existed have no owner; they are
        # visible to any authenticated buyer rather than orphaned.
        if rfq is None or (rfq.user_id is not None and rfq.user_id != user_id):
            raise NotFoundError("RFQ not found")

        return rfq

    @staticmethod
    def get_by_id(db: Session, user_id: int, invitation_id: int) -> Invitation:
        invitation = db.get(Invitation, invitation_id)

        if invitation is None:
            raise NotFoundError("Invitation not found")

        InvitationService.get_rfq(db, user_id, invitation.rfq_id)

        return invitation

    @staticmethod
    def get_by_token(db: Session, token: str) -> Invitation:
        """Public lookup. A bad token is a 404 — never "wrong token"."""

        if not token or len(token) < 16:
            raise NotFoundError("This quote link is not valid.")

        invitation = db.scalar(select(Invitation).where(Invitation.token == token))

        if invitation is None:
            raise NotFoundError("This quote link is not valid.")

        return invitation

    @staticmethod
    def list_for_rfq(db: Session, rfq_id: int) -> list[Invitation]:
        stmt = (
            select(Invitation)
            .where(Invitation.rfq_id == rfq_id)
            .order_by(Invitation.id.asc())
        )

        return list(db.scalars(stmt).all())

    # ------------------------------------------------------------- creation
    @staticmethod
    def create(
        db: Session,
        user_id: int,
        rfq_id: int,
        supplier_id: int,
        *,
        expires_at: datetime | None = None,
        send_now: bool = False,
    ) -> Invitation:
        rfq = InvitationService.get_rfq(db, user_id, rfq_id)

        supplier = db.get(Supplier, supplier_id)

        if supplier is None or supplier.user_id != user_id:
            raise NotFoundError("Supplier not found")

        existing = db.scalar(
            select(Invitation).where(
                Invitation.rfq_id == rfq_id,
                Invitation.supplier_id == supplier_id,
            )
        )

        if existing is not None:
            if existing.status == "cancelled":
                # Re-inviting a cancelled supplier reuses the row and its token,
                # so any link already in their inbox keeps working.
                existing.status = "pending"
                existing.cancelled_at = None
                existing.expires_at = expires_at or InvitationService.default_expiry(rfq)
                db.commit()
                db.refresh(existing)

                if send_now:
                    InvitationService.send(db, existing)

                return existing

            raise ConflictError(
                f"{supplier.name} has already been invited to this RFQ."
            )

        invitation = Invitation(
            rfq_id=rfq_id,
            supplier_id=supplier_id,
            token=generate_invitation_token(),
            status="pending",
            expires_at=expires_at or InvitationService.default_expiry(rfq),
        )

        db.add(invitation)
        db.commit()
        db.refresh(invitation)

        if send_now:
            InvitationService.send(db, invitation)

        return invitation

    @staticmethod
    def default_expiry(rfq: RFQ) -> datetime:
        """Link TTL: the RFQ deadline plus grace, or the configured TTL."""

        if rfq.deadline is not None:
            deadline = rfq.deadline

            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=UTC)

            grace = deadline + timedelta(days=7)

            ttl_limit = utcnow() + timedelta(days=settings.INVITATION_TTL_DAYS)

            return min(grace, ttl_limit) if grace > utcnow() else ttl_limit

        return utcnow() + timedelta(days=settings.INVITATION_TTL_DAYS)

    @staticmethod
    def bulk_create(
        db: Session,
        user_id: int,
        rfq_id: int,
        supplier_ids: list[int],
        *,
        send_now: bool = True,
    ) -> list[Invitation]:
        invitations: list[Invitation] = []

        for supplier_id in supplier_ids:
            try:
                invitations.append(
                    InvitationService.create(
                        db=db,
                        user_id=user_id,
                        rfq_id=rfq_id,
                        supplier_id=supplier_id,
                        send_now=False,
                    )
                )
            except ConflictError:
                # Already invited — keep going so one duplicate does not abort the
                # batch, and return the existing invitation.
                existing = db.scalar(
                    select(Invitation).where(
                        Invitation.rfq_id == rfq_id,
                        Invitation.supplier_id == supplier_id,
                    )
                )
                if existing is not None:
                    invitations.append(existing)

        if send_now:
            for invitation in invitations:
                if invitation.sent_at is None:
                    InvitationService.send(db, invitation)

        return invitations

    # --------------------------------------------------------------- sending
    @staticmethod
    def build_email(db: Session, invitation: Invitation) -> EmailMessage:
        rfq = invitation.rfq or db.get(RFQ, invitation.rfq_id)
        supplier = invitation.supplier or db.get(Supplier, invitation.supplier_id)
        owner = rfq.owner if rfq is not None else None

        if rfq is None or supplier is None:
            raise NotFoundError("Invitation is missing its RFQ or supplier.")

        deadline_text = None

        if rfq.deadline is not None:
            deadline = rfq.deadline

            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=UTC)

            deadline_text = deadline.strftime("%d %b %Y")

        subject, body = build_invitation_email(
            supplier_name=supplier.name,
            contact_name=supplier.contact_name,
            rfq_number=rfq.rfq_number,
            item_name=rfq.item_name,
            specification=rfq.specification,
            quantity=rfq.quantity,
            unit=rfq.unit,
            delivery_expectation=rfq.delivery_expectation.strftime("%d %b %Y"),
            deadline_text=deadline_text,
            buyer_company=rfq.buyer_company
            or (owner.company_name if owner else "Our company"),
            buyer_contact_name=owner.full_name if owner else None,
            buyer_contact_email=(
                (owner.contact_email or owner.email) if owner else None
            ),
            form_link=settings.public_form_link(invitation.rfq_id, invitation.token),
            notes=rfq.notes,
            procurement_type=rfq.procurement_type or "service",
            required_field_labels=[
                taxonomy.label_for(field, rfq.procurement_type)
                for field in rfq.required_field_list
            ],
            site_text=", ".join(
                part
                for part in (rfq.site_name, rfq.site_address)
                if part
            )
            or None,
            required_response_hours=rfq.required_response_hours,
            required_accreditations=list(rfq.required_accreditations or []),
            tax_note=taxonomy.describe_tax(
                rfq.currency,
                float(rfq.gst_rate) if rfq.gst_rate is not None else None,
            ),
        )

        return EmailMessage(
            to_email=supplier.contact_email,
            to_name=supplier.contact_name or supplier.name,
            subject=subject,
            body=body,
            reply_to=(owner.contact_email or owner.email) if owner else None,
        )

    @staticmethod
    def send(db: Session, invitation: Invitation) -> FollowUp:
        """Send the form link and log it as a FollowUp row of kind ``manual``.

        Logging the initial send in the same table as the reminders means the
        buyer's communication log is genuinely complete — every message that went
        out is one query away.
        """

        message = InvitationService.build_email(db, invitation)

        status = "sent"
        error = None
        provider_id = None

        try:
            result = send_email_message_sync(message)
            provider_id = result.message_id
        except ExternalServiceError as exc:
            # A provider outage must not lose the invitation: the row is created,
            # the token stays valid, and the buyer sees the failure and can resend.
            status = "failed"
            error = str(exc)
            logger.warning("Invitation %s email failed: %s", invitation.id, exc)

        now = utcnow()

        followup = FollowUp(
            rfq_id=invitation.rfq_id,
            invitation_id=invitation.id,
            supplier_id=invitation.supplier_id,
            kind="manual",
            status=status,
            sequence=0,
            to_email=message.to_email,
            subject=message.subject,
            body=message.body,
            llm_generated=False,
            requested_fields=None,
            provider_message_id=provider_id,
            error=error,
            sent_at=now if status == "sent" else None,
            triggered_by="buyer",
        )

        db.add(followup)

        if status == "sent":
            invitation.sent_at = invitation.sent_at or now
            invitation.last_sent_at = now

            if invitation.status in {"expired"}:
                invitation.status = "pending"

        db.commit()
        db.refresh(followup)
        db.refresh(invitation)

        return followup

    @staticmethod
    def resend(db: Session, user_id: int, invitation_id: int) -> FollowUp:
        invitation = InvitationService.get_by_id(db, user_id, invitation_id)

        if invitation.status == "submitted":
            raise BadRequestError(
                "This supplier has already submitted a complete quote."
            )

        if invitation.expires_at is not None:
            expires = invitation.expires_at

            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)

            if expires <= utcnow():
                # Give the supplier a fresh window rather than sending a dead link.
                invitation.expires_at = utcnow() + timedelta(
                    days=settings.INVITATION_TTL_DAYS
                )

        return InvitationService.send(db, invitation)

    # ---------------------------------------------------------------- status
    @staticmethod
    def derive_status(
        invitation: Invitation,
        rfq: RFQ | None,
        quote: SupplierQuote | None,
        *,
        now: datetime | None = None,
    ) -> tuple[str, str]:
        """Return ``(status, reason)`` for the dashboard.

        The stored status is authoritative for terminal states the buyer set
        deliberately (cancelled, declined). Everything else is re-derived so the
        dashboard cannot show "Pending" for a link that expired last week.
        """

        now = now or utcnow()

        if invitation.status in {"cancelled", "declined"}:
            return invitation.status, {
                "cancelled": "You withdrew this invitation.",
                "declined": "The supplier declined to quote.",
            }[invitation.status]

        if quote is not None:
            if quote.completeness == "complete":
                return "submitted", "A complete quote was received."
            return (
                "incomplete",
                "A quote was received but is missing: "
                + (", ".join(label_for(f) for f in (quote.missing_fields or [])) or "unknown"),
            )

        expires_at = invitation.expires_at

        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        deadline = rfq.deadline if rfq is not None else None

        if deadline is not None and deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)

        past_link = expires_at is not None and expires_at <= now
        past_deadline = deadline is not None and deadline <= now

        if past_link or past_deadline:
            which = "deadline" if past_deadline else "link expiry"
            return "expired", f"No quote was received before the {which} passed."

        if invitation.sent_at is None:
            return "pending", "The form link has not been sent yet."

        if invitation.view_count:
            return (
                "pending",
                f"The supplier opened the form {invitation.view_count} time(s) "
                f"but has not submitted.",
            )

        return "pending", "Waiting for the supplier to submit."

    @staticmethod
    def to_response(
        invitation: Invitation,
        rfq: RFQ | None = None,
        quote: SupplierQuote | None = None,
        *,
        next_reminder_at: datetime | None = None,
    ) -> InvitationResponse:
        rfq = rfq or invitation.rfq
        quote = quote if quote is not None else invitation.quote
        supplier = invitation.supplier

        status, reason = InvitationService.derive_status(invitation, rfq, quote)

        missing = list(quote.missing_fields or []) if quote is not None else []

        return InvitationResponse(
            id=invitation.id,
            rfq_id=invitation.rfq_id,
            supplier_id=invitation.supplier_id,
            token=invitation.token,
            form_link=settings.public_form_link(invitation.rfq_id, invitation.token),
            status=status,
            sent_at=invitation.sent_at,
            last_sent_at=invitation.last_sent_at,
            responded_at=invitation.responded_at,
            expires_at=invitation.expires_at,
            reminder_count=invitation.reminder_count or 0,
            last_reminder_at=invitation.last_reminder_at,
            view_count=invitation.view_count or 0,
            first_viewed_at=invitation.first_viewed_at,
            created_at=invitation.created_at,
            supplier_name=supplier.name if supplier else "",
            supplier_contact_name=supplier.contact_name if supplier else None,
            supplier_contact_email=supplier.contact_email if supplier else "",
            supplier_risk=supplier.risk_rating if supplier else "low",
            quote_id=quote.id if quote is not None else None,
            quote_completeness=quote.completeness if quote is not None else None,
            quote_unit_price=str(quote.unit_price) if quote and quote.unit_price else None,
            quote_currency=quote.currency if quote is not None else None,
            quote_lead_time_days=quote.lead_time if quote is not None else None,
            missing_fields=missing,
            missing_field_labels=[label_for(f) for f in missing],
            blocking_question=quote.blocking_question if quote is not None else None,
            next_reminder_at=next_reminder_at,
            status_reason=reason,
        )

    # -------------------------------------------------------------- preview
    @staticmethod
    def assert_usable(invitation: Invitation, rfq: RFQ, *, now: datetime | None = None) -> None:
        """Raise the right domain error before a supplier wastes time filling a form."""

        if invitation.status == "cancelled":
            raise InvitationExpiredError("This quote request has been withdrawn.")

        now = now or utcnow()

        expires_at = invitation.expires_at

        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at is not None and expires_at <= now:
            raise InvitationExpiredError(
                "This quote link expired on "
                f"{expires_at.date().isoformat()}. Ask the buyer to resend it."
            )

        if rfq.status == "cancelled":
            raise InvitationExpiredError("This quote request has been cancelled.")

    @staticmethod
    def build_preview(invitation: Invitation, rfq: RFQ) -> InvitationPreview:
        from app.core.rate_limit import HONEYPOT_FIELD

        supplier = invitation.supplier
        owner = rfq.owner

        expires_at = invitation.expires_at
        now = utcnow()

        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        return InvitationPreview(
            rfq_id=rfq.id,
            rfq_number=rfq.rfq_number,
            item_name=rfq.item_name,
            specification=rfq.specification,
            quantity=rfq.quantity,
            unit=rfq.unit,
            delivery_expectation=rfq.delivery_expectation,
            deadline=rfq.deadline,
                currency=rfq.currency,
            incoterms=rfq.incoterms,
            procurement_type=rfq.procurement_type or "service",
            site_name=rfq.site_name,
            site_address=rfq.site_address,
            site_access_notes=rfq.site_access_notes,
            required_response_hours=rfq.required_response_hours,
            required_accreditations=list(rfq.required_accreditations or []),
            gst_rate=(
                float(rfq.gst_rate) if rfq.gst_rate is not None else None
            ),
            tax_note=taxonomy.describe_tax(
                rfq.currency,
                float(rfq.gst_rate) if rfq.gst_rate is not None else None,
            ),
            rate_bases=list(taxonomy.rate_bases_for(rfq.procurement_type)),
            category=rfq.category,
            buyer_company=rfq.buyer_company
            or (owner.company_name if owner else "Our company"),
            buyer_contact_email=(owner.contact_email or owner.email) if owner else None,
            buyer_contact_phone=owner.contact_phone if owner else None,
            supplier_name=supplier.name if supplier else "",
            contact_name=supplier.contact_name if supplier else None,
            required_fields=rfq.required_field_list,
            required_field_labels=[
                taxonomy.label_for(field, rfq.procurement_type)
                for field in rfq.required_field_list
            ],
            already_submitted=invitation.quote is not None,
            is_expired=expires_at is not None and expires_at <= now,
            expires_at=expires_at,
            honeypot_field=HONEYPOT_FIELD,
            captcha_provider=settings.CAPTCHA_PROVIDER,
            captcha_site_key=(
                settings.CAPTCHA_SITE_KEY
                if settings.CAPTCHA_PROVIDER not in {"", "none"}
                else None
            ),
            max_upload_mb=settings.MAX_UPLOAD_MB,
            allowed_upload_extensions=list(settings.ALLOWED_UPLOAD_EXTENSIONS),
        )


def send_email_message_sync(message: EmailMessage):
    """Run the async transport from a sync service method.

    These feature slices use sync SQLAlchemy sessions, while the email transport is
    async so it can share the HTTP connection pool. Bridging in one place keeps
    every caller simple. When a sync service has been reached from an async
    endpoint (FastAPI runs it in a worker thread) there is no running loop *in this
    thread*, so ``asyncio.run`` is safe; if there is one, the send is offloaded to a
    private thread with its own loop.
    """

    from app.core.email import send_email_message as _send

    def run() -> object:
        return asyncio.run(_send(message))

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return run()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(run).result()
