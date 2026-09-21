"""Comparison service — runs the engine, persists the snapshot, records approvals."""

import asyncio
import concurrent.futures
import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.quote_parser.completeness import label_for
from comparison import ComparisonInput
from comparison import QuoteInput
from comparison import comparison_to_csv
from comparison import run_comparison
from comparison.score import missing_accreditations
from app.ai.completer import get_completer
from app.ai.completer import llm_available
from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.core.exceptions import NotFoundError
from app.core.llm_client import get_llm_client
from app.core.mixins import utcnow
from app.features.comparison import repository
from app.features.comparison.model import Approval
from app.features.comparison.model import Comparison
from app.features.comparison.narrative import SYSTEM_PROMPT
from app.features.comparison.narrative import build_user_prompt
from app.features.comparison.schema import ApprovalResponse
from app.features.comparison.schema import ComparisonResponse
from app.features.comparison.schema import QuoteSummary
from app.features.quote.model import SupplierQuote
from app.features.rfq.model import RFQ
from app.features.supplier.model import Supplier

logger = logging.getLogger(__name__)


class ComparisonService:
    # ------------------------------------------------------------ projections
    @staticmethod
    def quote_summary(quote: SupplierQuote) -> QuoteSummary:
        rfq = quote.rfq
        missing = [str(field) for field in (quote.missing_fields or [])]

        return QuoteSummary(            id=quote.id,
            rfq_id=quote.rfq_id,
            supplier_id=quote.supplier_id,
            invitation_id=quote.invitation_id,
            reference_number=quote.reference_number,
            supplier_name=quote.supplier_name,
            contact_email=quote.contact_email,
            unit_price=quote.unit_price,
            currency=quote.currency,
            unit=quote.unit,
            lead_time=quote.lead_time,
            payment_terms=quote.payment_terms,
            incoterms=quote.incoterms,
            moq=quote.moq,
            validity_date=quote.validity_date,
            warranty_months=quote.warranty_months,
            shipping_cost=quote.shipping_cost,
            duties=quote.duties,
            taxes=quote.taxes,
            discount=quote.discount,
            response_time_hours=quote.response_time_hours,
            callout_charge=quote.callout_charge,
            labour_rate=quote.labour_rate,
            materials_markup_pct=quote.materials_markup_pct,
            compliance_accreditations=list(quote.compliance_accreditations or []),
            gst_rate=quote.gst_rate,
            missing_accreditations=missing_accreditations(
                quote.compliance_accreditations,
                rfq.required_accreditations if rfq is not None else None,
            ),
            notes=quote.notes,
            remarks=quote.remarks,
            attachments=list(quote.attachments or []),
            source=quote.source,
            completeness=quote.completeness,
            missing_fields=missing,
            missing_field_labels=[label_for(field) for field in missing],
            risk_flags=list(quote.risk_flags or []),
            blocking_question=quote.blocking_question,
            normalized_currency=quote.normalized_currency,
            normalized_unit_price=quote.normalized_unit_price,
            normalized_total_cost=quote.normalized_total_cost,
            composite_score=quote.composite_score,
            scores=quote.scores,
            submitted_at=quote.submitted_at,
            created_at=quote.created_at,
            quantity=rfq.quantity if rfq is not None else 0,
        )

    # ------------------------------------------------------------ input build
    @staticmethod
    def load_quotes(db: Session, rfq_id: int) -> list[SupplierQuote]:
        """Fetch an RFQ's quotes with an explicit query.

        Deliberately not ``rfq.quotes``: a relationship collection is cached on the
        instance and can be stale inside a long-running session, which silently
        drops quotes out of a scoring run. Querying is one cheap SELECT and cannot
        go stale.
        """

        stmt = (
            select(SupplierQuote)
            .where(SupplierQuote.rfq_id == rfq_id)
            .order_by(SupplierQuote.id.asc())
        )

        return list(db.scalars(stmt).all())

    @staticmethod
    def build_input(db: Session, rfq: RFQ) -> ComparisonInput:
        """Convert RFQ + ORM quotes into the engine's pure input."""

        quotes: list[QuoteInput] = []

        for quote in ComparisonService.load_quotes(db, rfq.id):
            risk = "low"

            if quote.supplier_id is not None:
                supplier = db.get(Supplier, quote.supplier_id)

                if supplier is not None:
                    risk = supplier.risk_rating or "low"

            quotes.append(
                QuoteInput(
                    quote_id=quote.id,
                    supplier_name=quote.supplier_name,
                    currency=quote.currency or rfq.currency or settings.BASE_CURRENCY,
                    unit=quote.unit or rfq.unit or "per job",
                    unit_price=quote.unit_price,
                    lead_time_days=quote.lead_time,
                    moq=quote.moq,
                    payment_terms=quote.payment_terms,
                    incoterms=quote.incoterms,
                    validity_date=quote.validity_date,
                    warranty_months=quote.warranty_months,
                    shipping_cost=quote.shipping_cost,
                    duties=quote.duties,
                    taxes=quote.taxes,
                    discount=quote.discount,
                    # ---- services ------------------------------------------
                    response_time_hours=quote.response_time_hours,
                    callout_charge=quote.callout_charge,
                    labour_rate=quote.labour_rate,
                    materials_markup_pct=quote.materials_markup_pct,
                    compliance_accreditations=list(
                        quote.compliance_accreditations or []
                    ),
                    # The supplier's own stated rate wins. When they stated none at
                    # all, the RFQ's rate applies, so every quote in this RFQ is
                    # priced on the same tax basis — comparing a GST-inclusive quote
                    # against a tax-exclusive one is how a buyer awards the wrong
                    # supplier. A supplier who explicitly said 0 (not registered)
                    # keeps their 0.
                    gst_rate=(
                        quote.gst_rate
                        if quote.gst_rate is not None
                        else rfq.gst_rate
                    ),
                    completeness=quote.completeness or "complete",
                    missing_fields=[str(f) for f in (quote.missing_fields or [])],
                    supplier_risk=risk,
                )
            )

        return ComparisonInput(
            rfq_id=rfq.id,
            rfq_number=rfq.rfq_number,
            item_name=rfq.item_name,
            quantity=rfq.quantity,
            unit=rfq.unit or "per job",
            base_currency=rfq.currency or settings.BASE_CURRENCY,
            base_incoterms=rfq.incoterms,
            # Without this the engine falls back to its goods default, and a
            # maintenance RFQ would be scored on MOQ and Incoterms while its SLA was
            # ignored — the single criterion that separates two otherwise identical
            # maintenance quotes.
            procurement_type=rfq.procurement_type or "service",
            required_accreditations=list(rfq.required_accreditations or []),
            gst_rate=rfq.gst_rate,
            # `or {}` so the engine substitutes the per-type defaults rather than a
            # stored goods weight set.
            weights=rfq.scoring_weights or settings.scoring_weights or {},
            quotes=quotes,
        )

    # ---------------------------------------------------------------- compute
    @staticmethod
    def recompute(
        db: Session,
        rfq: RFQ,
        *,
        weights: dict[str, float] | None = None,
        use_llm: bool = True,
    ) -> Comparison:
        """Score the current quotes and persist an immutable snapshot."""

        payload = ComparisonService.build_input(db, rfq)

        if weights:
            payload.weights = weights

        result = run_comparison(payload)

        summary: str | None = None
        key_risks: list[str] = []
        llm_model: str | None = None
        computed_by = "engine"

        if use_llm and llm_available():
            narrative = _narrate_sync(result)

            if narrative is not None:
                summary = narrative.get("summary")
                raw_risks = narrative.get("key_risks")

                if isinstance(raw_risks, list):
                    key_risks = [str(item)[:400] for item in raw_risks if str(item).strip()]

                llm_model = get_llm_client().model
                computed_by = "engine+llm"

        # Only one comparison per RFQ is current; the rest are history.
        for existing in repository.list_for_rfq(db, rfq.id):
            existing.is_current = False

        risks = list(result.risks)

        for extra in key_risks:
            if extra not in risks:
                risks.append(extra)

        comparison = Comparison(
            rfq_id=rfq.id,
            base_currency=result.base_currency,
            base_incoterms=result.base_incoterms,
            weights=result.weights,
            fx_rates=result.fx_rates,
            results=[item.model_dump_jsonable() for item in result.results],
            recommended_quote_id=result.recommended_quote_id,
            backup_quote_id=result.backup_quote_id,
            summary=summary,
            rationale=result.rationale,
            risks=risks,
            is_conclusive=bool(result.is_conclusive),
            llm_model=llm_model,
            computed_by=computed_by,
            is_current=True,
        )

        db.add(comparison)

        # Write the normalized figures back onto the quotes so the quotes table and
        # the CSV/PDF importers see the same numbers the comparison used.
        ComparisonService.apply_to_quotes(
            db, ComparisonService.load_quotes(db, rfq.id), result
        )

        db.commit()
        db.refresh(comparison)

        return comparison

    @staticmethod
    def apply_to_quotes(db: Session, quotes, result) -> None:
        by_id = {item.quote_id: item for item in result.results}
        now = utcnow()

        for quote in quotes:
            item = by_id.get(quote.id)

            if item is None:
                continue

            quote.normalized_currency = result.base_currency
            quote.normalized_unit_price = item.unit_price_base
            quote.normalized_incoterms = result.base_incoterms
            quote.normalized_total_cost = item.total_base
            quote.cost_breakdown = item.breakdown.model_dump_jsonable()
            quote.scores = item.scores
            quote.composite_score = Decimal(str(item.composite_score))
            quote.risk_flags = list(item.risk_flags)
            quote.completeness = item.completeness
            quote.normalized_at = now

    # --------------------------------------------------------------- response
    @staticmethod
    def to_response(
        comparison: Comparison,
        approval: Approval | None = None,
    ) -> ComparisonResponse:
        rfq = comparison.rfq

        results = list(comparison.results or [])

        recommended_name = None

        if comparison.recommended_quote_id is not None:
            for item in results:
                if item.get("quote_id") == comparison.recommended_quote_id:
                    recommended_name = item.get("supplier_name")
                    break

        warnings: list[str] = []

        fx = comparison.fx_rates or {}
        if fx.get("source"):
            warnings.append(
                f"Currency conversion uses a {fx.get('source')} rate table "
                f"(as of {fx.get('as_of')}), not a live rate."
            )

        if not comparison.is_conclusive and results:
            warnings.append(
                "At least one quote could not be ranked, or the leading quote is "
                "incomplete. Re-run the comparison after the remaining quotes arrive."
            )

        return ComparisonResponse(
            id=comparison.id,
            rfq_id=comparison.rfq_id,
            base_currency=comparison.base_currency,
            base_incoterms=comparison.base_incoterms,
            quantity=rfq.quantity if rfq is not None else 0,
            unit=(rfq.unit if rfq is not None else "pcs") or "pcs",
            # Served from the RFQ rather than the comparison row: the requirements are
            # the RFQ's current contract, and a snapshot taken last week should not
            # tell a buyer what they used to require.
            procurement_type=(
                (rfq.procurement_type if rfq is not None else None) or "service"
            ),
            required_accreditations=list(
                (rfq.required_accreditations if rfq is not None else None) or []
            ),
            weights=comparison.weights,
            fx_rates=comparison.fx_rates,
            results=results,
            recommended_quote_id=comparison.recommended_quote_id,
            backup_quote_id=comparison.backup_quote_id,
            summary=comparison.summary,
            rationale=comparison.rationale,
            risks=list(comparison.risks or []),
            is_conclusive=bool(comparison.is_conclusive),
            llm_model=comparison.llm_model,
            computed_by=comparison.computed_by,
            is_current=bool(comparison.is_current),
            created_at=comparison.created_at,
            updated_at=comparison.updated_at,
            rfq_number=rfq.rfq_number if rfq is not None else "",
            item_name=rfq.item_name if rfq is not None else "",
            recommended_supplier=recommended_name,
            approval=(
                ComparisonService.approval_response(approval)
                if approval is not None
                else None
            ),
            awaiting_approval=(
                comparison.recommended_quote_id is not None and approval is None
            ),
            warnings=warnings,
        )

    @staticmethod
    def approval_response(approval: Approval) -> ApprovalResponse:
        quote = approval.quote

        return ApprovalResponse(
            id=approval.id,
            rfq_id=approval.rfq_id,
            comparison_id=approval.comparison_id,
            quote_id=approval.quote_id,
            decision=approval.decision,
            note=approval.note,
            decided_by_email=approval.decided_by_email,
            recommended_quote_id=approval.recommended_quote_id,
            overrode_recommendation=bool(approval.overrode_recommendation),
            awarded_total_cost=approval.awarded_total_cost,
            awarded_currency=approval.awarded_currency,
            decided_at=approval.decided_at,
            created_at=approval.created_at,
            supplier_name=quote.supplier_name if quote is not None else None,
            quote_reference=quote.reference_number if quote is not None else None,
        )

    # --------------------------------------------------------------- approval
    @staticmethod
    def approve(
        db: Session,
        rfq: RFQ,
        user,
        *,
        quote_id: int,
        decision: str,
        note: str,
    ) -> Approval:
        """Record a human decision. The only path by which an RFQ is awarded.

        There is deliberately no automatic caller: nothing in the scheduler,
        the parser, or the LLM can reach this function. That is the guardrail —
        it is enforced by the call graph, not by a prompt.
        """

        quote = db.get(SupplierQuote, quote_id)

        if quote is None or quote.rfq_id != rfq.id:
            raise NotFoundError("That quote does not belong to this RFQ.")

        if decision == "approved" and not quote.has_price:
            raise BadRequestError(
                "This quote has no unit price, so it cannot be awarded."
            )

        comparison = repository.latest_for_rfq(db, rfq.id)

        recommended_id = comparison.recommended_quote_id if comparison else None

        if decision == "approved":
            supplier_missing = [
                str(field) for field in (quote.missing_fields or [])
            ]

            if supplier_missing and not note.lower().startswith("override"):
                raise BadRequestError(
                    "This quote is still missing required field(s): "
                    + ", ".join(label_for(field) for field in supplier_missing)
                    + ". Start your note with 'override' to award it anyway and "
                    "record why."
                )

        total_cost = quote.normalized_total_cost

        if total_cost is None and quote.unit_price is not None:
            total_cost = quote.unit_price * rfq.quantity

        approval = Approval(
            rfq_id=rfq.id,
            comparison_id=comparison.id if comparison else None,
            quote_id=quote.id,
            user_id=user.id,
            decided_by_email=user.email,
            decision=decision,
            note=note,
            recommended_quote_id=recommended_id,
            overrode_recommendation=bool(
                decision == "approved"
                and recommended_id is not None
                and recommended_id != quote.id
            ),
            awarded_total_cost=total_cost if decision == "approved" else None,
            awarded_currency=(
                quote.normalized_currency or quote.currency
                if decision == "approved"
                else None
            ),
            decided_at=utcnow(),
        )

        db.add(approval)

        if decision == "approved":
            rfq.status = "awarded"
        elif decision == "rejected":
            # Rejecting a quote does not close the RFQ — the buyer may still award
            # one of the others.
            rfq.status = "open"

        db.commit()
        db.refresh(approval)

        return approval

    # ----------------------------------------------------------------- export
    @staticmethod
    def export_csv(db: Session, rfq: RFQ, comparison: Comparison) -> str:
        payload = ComparisonService.build_input(db, rfq)

        # Re-run the engine from the snapshot's weights so the CSV reproduces the
        # stored run rather than drifting with the current defaults.
        if comparison.weights:
            payload.weights = comparison.weights

        result = run_comparison(payload)

        if comparison.summary:
            result.rationale = comparison.rationale or result.rationale

        return comparison_to_csv(result)


def _narrate_sync(result):
    """Run the async narrative call from sync code."""

    completer = get_completer()

    if completer is None:
        return None

    ranked = [
        item.model_dump_jsonable() for item in result.ranked()
    ]
    excluded = [
        item.model_dump_jsonable() for item in result.results if not item.comparable
    ]

    rfq_number = result.rfq_number
    item_name = result.item_name
    quantity = result.quantity
    unit = result.unit
    base_currency = result.base_currency
    base_incoterms = result.base_incoterms
    weights = result.weights
    risks = list(result.risks)
    fx_source = str((result.fx_rates or {}).get("source", "static"))

    async def call():
        return await completer(
            SYSTEM_PROMPT,
            build_user_prompt(
                rfq_number=rfq_number,
                item_name=item_name,
                quantity=quantity,
                unit=unit,
                base_currency=base_currency,
                base_incoterms=base_incoterms,
                weights=weights,
                ranked=ranked,
                excluded=excluded,
                risks=risks,
                fx_source=fx_source,
            ),
        )

    def run():
        return asyncio.run(call())

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return run()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(run).result()
