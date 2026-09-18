"""Public form service — ingest a supplier submission as a Quote.

The whole point of this feature: a supplier with nothing but a URL submits a form
and a normalized :class:`~app.features.quote.model.SupplierQuote` appears against
the right RFQ, with its completeness assessed and its missing fields recorded so
the follow-up agent knows exactly what to ask for.

Ingestion pipeline:

    1. anti-spam  (honeypot → rate limit → optional CAPTCHA)
    2. parse      (agents.quote_parser: form values, then LLM, then heuristics)
    3. complete?  (agents.quote_parser.completeness against the RFQ's contract)
    4. persist    (quote upsert + invitation status + attachments)
    5. normalize  (comparison engine, so the dashboard has numbers immediately)
"""

import logging

from sqlalchemy.orm import Session

from agents.quote_parser import evaluate_completeness
from agents.quote_parser.parser import parse_submission
from app.ai.completer import get_completer
from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.core.exceptions import NotFoundError
from app.core.mixins import utcnow
from app.core.security import generate_reference_number
from app.features.invitation.model import Invitation
from app.features.invitation.service import InvitationService
from app.features.public_form.schema import PublicQuoteResponse
from app.features.public_form.schema import PublicQuoteSubmit
from app.features.quote.model import SupplierQuote
from app.features.rfq.model import RFQ

logger = logging.getLogger(__name__)


class PublicFormService:
    # ---------------------------------------------------------------- loading
    @staticmethod
    def load_invitation(db: Session, token: str) -> tuple[Invitation, RFQ]:
        """Resolve a token and record the view.

        Counting views is what lets the dashboard distinguish "never opened" from
        "opened three times and never submitted" — which is exactly the signal the
        follow-up agent uses to change its message.
        """

        invitation = InvitationService.get_by_token(db, token)

        rfq = invitation.rfq

        if rfq is None:
            raise NotFoundError("This quote link is not valid.")

        InvitationService.assert_usable(invitation, rfq)

        invitation.view_count = (invitation.view_count or 0) + 1

        if invitation.first_viewed_at is None:
            invitation.first_viewed_at = utcnow()

        db.commit()
        db.refresh(invitation)

        return invitation, rfq

    @staticmethod
    def peek(db: Session, token: str) -> tuple[Invitation, RFQ]:
        """Resolve a token without recording a view (used by the status poll)."""

        invitation = InvitationService.get_by_token(db, token)

        if invitation.rfq is None:
            raise NotFoundError("This quote link is not valid.")

        return invitation, invitation.rfq

    # ------------------------------------------------------------- submission
    @staticmethod
    async def submit(
        db: Session,
        invitation: Invitation,
        rfq: RFQ,
        payload: PublicQuoteSubmit,
    ) -> PublicQuoteResponse:
        """Validate, parse, and store a submission."""

        form_values = payload.model_dump(
            exclude={
                "company_website",
                "captcha_token",
                "attachment_keys",
                "notes",
            }
        )

        completer = get_completer()

        parsed, _ = await parse_submission(
            form_values=form_values,
            free_text=payload.notes,
            llm=completer,
            rfq_context=PublicFormService.rfq_context(rfq),
            supplier_context=(
                f"Supplier on file: {invitation.supplier.name} "
                f"<{invitation.supplier.contact_email}>"
            ),
        )

        report = evaluate_completeness(
            parsed,
            rfq.required_field_list,
            raw_text=payload.notes,
        )

        if parsed.unit_price is None and report.is_complete:
            # Should be unreachable: unit_price is in the default required set. If a
            # buyer removes it from the contract, a price-less "complete" quote
            # would poison comparison, so it is caught here rather than there.
            raise BadRequestError(
                "A unit price is required to submit a quote. Please add one and "
                "submit again."
            )

        quote, created = PublicFormService.upsert_quote(
            db,
            invitation,
            rfq,
            parsed,
            report,
            payload,
        )

        return PublicFormService.build_confirmation(
            quote, rfq, report, parsed, created=created
        )

    @staticmethod
    def rfq_context(rfq: RFQ) -> str:
        """Grounding text handed to the parser so it knows what was asked for."""

        return (
            f"RFQ {rfq.rfq_number}\n"
            f"Item: {rfq.item_name}\n"
            f"Specification: {rfq.specification}\n"
            f"Quantity requested: {rfq.quantity} {rfq.unit}\n"
            f"Buyer's preferred currency: {rfq.currency}\n"
            f"Buyer's preferred Incoterms: {rfq.incoterms or 'not specified'}\n"
            f"Fields the buyer requires: {', '.join(rfq.required_field_list)}"
        )

    # ---------------------------------------------------------------- persist
    @staticmethod
    def upsert_quote(
        db: Session,
        invitation: Invitation,
        rfq: RFQ,
        parsed,
        report,
        payload: PublicQuoteSubmit,
    ) -> tuple[SupplierQuote, bool]:
        """Create the quote, or amend the existing one on a resubmission."""

        quote = invitation.quote

        created = quote is None

        if quote is None:
            quote = SupplierQuote(
                rfq_id=rfq.id,
                invitation_id=invitation.id,
                supplier_id=invitation.supplier_id,
                supplier_name=invitation.supplier.name,
                currency=parsed.currency or rfq.currency or "USD",
                source="form",
                submitted_at=utcnow(),
                reference_number=generate_reference_number(rfq.rfq_number, invitation.id),
            )
            db.add(quote)

        # A resubmission amends rather than duplicates: the supplier's second,
        # more complete answer is the one that counts, and the buyer sees one row.
        quote.supplier_name = parsed.supplier_name or invitation.supplier.name
        quote.contact_email = (
            parsed.contact_email or invitation.supplier.contact_email
        )
        quote.currency = parsed.currency or rfq.currency or "USD"
        quote.unit = parsed.unit or rfq.unit or "pcs"
        quote.unit_price = parsed.unit_price
        quote.lead_time = parsed.lead_time_days
        quote.moq = parsed.moq
        quote.payment_terms = parsed.payment_terms
        quote.incoterms = parsed.incoterms
        quote.validity_date = parsed.validity_date
        quote.warranty_months = parsed.warranty_months
        quote.shipping_cost = parsed.shipping_cost
        quote.duties = parsed.duties
        quote.taxes = parsed.taxes
        quote.discount = parsed.discount
        quote.notes = parsed.notes or payload.notes
        quote.remarks = parsed.notes or payload.notes
        quote.unparsed_notes = parsed.unparsed
        quote.blocking_question = parsed.blocking_question
        quote.parse_confidence = parsed.confidence
        quote.completeness = report.status
        quote.missing_fields = list(report.missing)
        quote.attachments = PublicFormService.resolve_attachments(
            db, invitation, payload.attachment_keys
        )
        quote.submitted_at = quote.submitted_at or utcnow()

        risk_flags: list[str] = []

        if report.is_complete:
            risk_flags.append("Complete submission.")
        else:
            risk_flags.append(
                "Missing required field(s): "
                + ", ".join(report.missing_labels)
            )

        if parsed.blocking_question:
            risk_flags.append(
                f"Supplier is waiting on the buyer: {parsed.blocking_question}"
            )

        if quote.source == "form" and quote.parse_confidence is not None:
            if float(quote.parse_confidence) < 0.5:
                risk_flags.append(
                    "Low parsing confidence — check the submitted figures against "
                    "the supplier's notes before relying on them."
                )

        quote.risk_flags = risk_flags

        invitation.status = "submitted" if report.is_complete else "incomplete"
        invitation.responded_at = utcnow()

        db.commit()
        db.refresh(quote)

        # Normalize immediately so the buyer's dashboard shows a landed cost the
        # moment the supplier submits, without waiting for a manual comparison run.
        if quote.has_price:
            try:
                PublicFormService.normalize_quote(db, rfq)
            except Exception:  # noqa: BLE001 - normalization must not lose the quote
                logger.exception(
                    "Quote %s stored but normalization failed", quote.id
                )

        logger.info(
            "Quote %s %s for RFQ %s (%s)",
            quote.id,
            "created" if created else "amended",
            rfq.id,
            report.status,
        )

        return quote, created

    @staticmethod
    def normalize_quote(db: Session, rfq: RFQ) -> None:
        """Run the comparison engine and write the normalized figures back."""

        from app.features.comparison.service import ComparisonService

        ComparisonService.recompute(db, rfq, use_llm=False)

    @staticmethod
    def resolve_attachments(
        db: Session,
        invitation: Invitation,
        keys: list[str],
    ) -> list[dict]:
        """Validate that every claimed attachment key belongs to this invitation."""

        if not keys:
            return []

        from app.features.attachment.service import AttachmentService

        return AttachmentService.resolve(db, invitation, keys)

    # ------------------------------------------------------------- confirmation
    @staticmethod
    def build_confirmation(
        quote: SupplierQuote,
        rfq: RFQ,
        report,
        parsed,
        *,
        created: bool = True,
    ) -> PublicQuoteResponse:
        owner = rfq.owner

        if report.is_complete:
            message = (
                f"Thank you — your quote has been received. Please keep the "
                f"reference {quote.reference_number} for your records."
            )
        else:
            message = (
                f"Thank you — your quote has been received under reference "
                f"{quote.reference_number}. We noticed a few details are still "
                f"missing, so we will follow up shortly. You can also add them now "
                f"using the same link."
            )

        return PublicQuoteResponse(
            reference_number=quote.reference_number or "",
            submitted_at=quote.submitted_at.date() if quote.submitted_at else None,
            supplier_name=quote.supplier_name,
            item_name=rfq.item_name,
            rfq_number=rfq.rfq_number,
            unit_price=str(quote.unit_price) if quote.unit_price is not None else None,
            currency=quote.currency,
            lead_time_days=quote.lead_time,
            completeness=report.status,
            missing_field_labels=list(report.missing_labels),
            message=message
            + (
                f" For any questions, contact "
                f"{owner.contact_email or owner.email}."
                if owner is not None
                else ""
            ),
            created=created,
        )
