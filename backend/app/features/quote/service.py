from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.features.quote.model import SupplierQuote
from app.features.quote.schema import QuoteCreate
from app.features.quote.schema import QuoteUpdate
from app.features.rfq.model import RFQ


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

        return quote

    #: Columns the database declares NOT NULL. A PATCH-style update uses
    #: ``exclude_unset``, so a client that explicitly sends ``"unit": null`` would
    #: otherwise write NULL and fail at commit with an IntegrityError — a 500 for
    #: what is really a "leave this alone" request. Silently skipping the null is the
    #: behaviour the caller meant.
    REQUIRED_COLUMNS = ("supplier_name", "currency", "unit")

    #: Columns the database declares NOT NULL. A PATCH-style update uses
    #: ``exclude_unset``, so a client that explicitly sends ``"unit": null`` would
    #: otherwise write NULL and fail at commit with an IntegrityError — a 500 for
    #: what is really a "leave this alone" request. Silently skipping the null is the
    #: behaviour the caller meant.
    REQUIRED_COLUMNS = ("supplier_name", "currency", "unit")

    @staticmethod
    def update(
        db: Session,
        quote_id: int,
        payload: QuoteUpdate,
    ) -> SupplierQuote:
        quote = QuoteService.get_by_id(
            db=db,
            quote_id=quote_id,
        )

        update_data = payload.model_dump(
            exclude_unset=True,
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

        db.delete(quote)

        db.commit()

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
