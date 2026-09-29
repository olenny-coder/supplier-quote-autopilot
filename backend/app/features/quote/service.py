from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.features.audit.service import AuditService
from app.features.quote.model import SupplierQuote
from app.features.quote.schema import QuoteCreate
from app.features.quote.schema import QuoteUpdate
from app.features.rfq.model import RFQ


def _money(value) -> str | None:
    """``Decimal`` -> string, for the audit detail. ``None`` stays ``None``."""

    return None if value is None else str(value)


class QuoteService:
    #: Columns the database declares NOT NULL. An update uses ``exclude_unset``, so a
    #: client that explicitly sends ``"unit": null`` would otherwise write NULL and
    #: fail at commit with an IntegrityError — a 500 for what is really a "leave this
    #: alone" request. Skipping the null is what the caller meant.
    REQUIRED_COLUMNS = ("supplier_name", "currency", "unit")

    @staticmethod
    def get_all_for_rfq(
        db: Session,
        rfq_id: int,
    ) -> list[SupplierQuote]:
        rfq = db.get(RFQ, rfq_id)

        if rfq is None:
            raise NotFoundError("RFQ not found")

        stmt = (
            select(SupplierQuote)
            .where(SupplierQuote.rfq_id == rfq_id)
            .order_by(SupplierQuote.unit_price.asc())
        )

        return list(db.scalars(stmt).all())

    @staticmethod
    def get_by_id(
        db: Session,
        quote_id: int,
    ) -> SupplierQuote:
        quote = db.get(SupplierQuote, quote_id)

        if quote is None:
            raise NotFoundError("Quote not found")

        return quote

    @staticmethod
    def create(
        db: Session,
        rfq_id: int,
        payload: QuoteCreate,
        user_id: int | None = None,
    ) -> SupplierQuote:
        rfq = db.get(RFQ, rfq_id)

        if rfq is None:
            raise NotFoundError("RFQ not found")

        quote = SupplierQuote(
            rfq_id=rfq_id,
            **payload.model_dump(),
        )

        db.add(quote)

        db.commit()

        db.refresh(quote)

        # "Entered by you", not "submitted": a quote that arrived by phone and was
        # typed in by the buyer is a different fact from one a supplier sent, and
        # the distinction is the whole reason the actor is recorded.
        AuditService.record(
            db,
            user_id=user_id if user_id is not None else rfq.user_id,
            action="quote.recorded",
            entity_type="quote",
            entity_id=quote.id,
            rfq=rfq,
            summary=(
                f"Recorded a quote from {quote.supplier_name} for {rfq.rfq_number}: "
                f"{_money(quote.unit_price)} {quote.currency} {quote.unit}."
            ),
            detail={
                "supplier_name": quote.supplier_name,
                "unit_price": _money(quote.unit_price),
                "currency": quote.currency,
                "unit": quote.unit,
                "source": quote.source,
            },
            commit=True,
        )

        return quote

    @staticmethod
    def update(
        db: Session,
        quote_id: int,
        payload: QuoteUpdate,
        user_id: int | None = None,
    ) -> SupplierQuote:
        quote = QuoteService.get_by_id(
            db=db,
            quote_id=quote_id,
        )

        update_data = payload.model_dump(
            exclude_unset=True,
        )

        rfq = quote.rfq

        changed = sorted(
            key
            for key, value in update_data.items()
            if not (value is None and key in QuoteService.REQUIRED_COLUMNS)
            and str(getattr(quote, key, None) or "") != str(value or "")
        )

        for key, value in update_data.items():
            if value is None and key in QuoteService.REQUIRED_COLUMNS:
                continue

            setattr(
                quote,
                key,
                value,
            )

        db.commit()

        db.refresh(quote)

        if changed:
            AuditService.record(
                db,
                user_id=(
                    user_id
                    if user_id is not None
                    else (rfq.user_id if rfq is not None else None)
                ),
                action="quote.updated",
                entity_type="quote",
                entity_id=quote.id,
                rfq=rfq,
                summary=(
                    f"Changed {', '.join(changed)} on the quote from "
                    f"{quote.supplier_name}."
                ),
                detail={"changed": changed},
                commit=True,
            )

        return quote

    @staticmethod
    def delete(
        db: Session,
        quote_id: int,
    ) -> None:
        quote = QuoteService.get_by_id(
            db=db,
            quote_id=quote_id,
        )

        # Captured before the row goes: the entry has to be able to say whose quote
        # was deleted and for which RFQ, and after the delete there is nothing left
        # to read that from except this snapshot.
        supplier_name = quote.supplier_name
        rfq = quote.rfq
        owner_id = rfq.user_id if rfq is not None else None
        quote_snapshot = {
            "supplier_name": supplier_name,
            "unit_price": _money(quote.unit_price),
            "currency": quote.currency,
            "unit": quote.unit,
            "source": quote.source,
        }

        db.delete(quote)

        db.commit()

        AuditService.record(
            db,
            user_id=owner_id,
            action="quote.deleted",
            entity_type="quote",
            entity_id=quote_id,
            rfq=rfq,
            summary=f"Deleted the quote from {supplier_name}.",
            detail=quote_snapshot,
            commit=True,
        )

    @staticmethod
    def get_best_quote(
        db: Session,
        rfq_id: int,
    ) -> SupplierQuote | None:
        rfq = db.get(RFQ, rfq_id)

        if rfq is None:
            raise NotFoundError("RFQ not found")

        stmt = (
            select(SupplierQuote)
            .where(SupplierQuote.rfq_id == rfq_id)
            .order_by(SupplierQuote.unit_price.asc())
            .limit(1)
        )

        return db.scalar(stmt)
