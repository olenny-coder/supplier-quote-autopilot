"""RFQ service.

Extended in place. The original signatures are preserved — ``get_all(db)``,
``get_by_id(db, rfq_id)``, ``create(db, payload)``, ``update``, ``delete`` all work
exactly as before — with an optional ``user_id`` that scopes results to a tenant
when the API supplies one. That keeps the base codebase's tests and the CSV/PDF
importers working unchanged.
"""

import logging
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError
from app.core.exceptions import NotFoundError
from app.core.mixins import utcnow
from app.features.invitation.model import Invitation
from app.features.quote.model import SupplierQuote
from app.features.rfq.model import DEFAULT_REQUIRED_FIELDS
from app.features.rfq.model import RFQ
from app.features.rfq.model import RFQ_STATUSES
from app.features.rfq.schema import RFQCreate
from app.features.rfq.schema import RFQResponse
from app.features.rfq.schema import RFQUpdate

logger = logging.getLogger(__name__)

#: Applied when a buyer does not name a deadline: two weeks to quote.
DEFAULT_QUOTE_WINDOW_DAYS = 14


class RFQService:
    @staticmethod
    def get_all(db: Session, user_id: int | None = None) -> list[RFQ]:
        stmt = select(RFQ)

        if user_id is not None:
            # Legacy RFQs predating accounts have no owner; they stay visible
            # rather than becoming unreachable.
            stmt = stmt.where((RFQ.user_id == user_id) | (RFQ.user_id.is_(None)))

        stmt = stmt.order_by(RFQ.id.desc())

        return list(db.scalars(stmt).all())

    @staticmethod
    def get_by_id(
        db: Session,
        rfq_id: int,
        user_id: int | None = None,
    ) -> RFQ:
        rfq = db.get(RFQ, rfq_id)

        if rfq is None:
            raise NotFoundError("RFQ not found")

        if user_id is not None and rfq.user_id is not None and rfq.user_id != user_id:
            raise NotFoundError("RFQ not found")

        return rfq

    @staticmethod
    def create(
        db: Session,
        payload: RFQCreate,
        user_id: int | None = None,
    ) -> RFQ:
        data = payload.model_dump(
            exclude={"supplier_ids", "new_suppliers", "send_invitations"},
        )

        if data.get("deadline") is None:
            data["deadline"] = utcnow() + timedelta(days=DEFAULT_QUOTE_WINDOW_DAYS)

        if data.get("required_fields") is None:
            data["required_fields"] = list(DEFAULT_REQUIRED_FIELDS)

        if data.get("status") not in RFQ_STATUSES:
            raise BadRequestError(f"Unknown RFQ status '{data.get('status')}'.")

        rfq = RFQ(
            user_id=user_id,
            **data,
        )

        db.add(rfq)
        db.commit()
        db.refresh(rfq)

        return rfq

    @staticmethod
    def update(
        db: Session,
        rfq_id: int,
        payload: RFQUpdate,
        user_id: int | None = None,
    ) -> RFQ:
        rfq = RFQService.get_by_id(
            db=db,
            rfq_id=rfq_id,
            user_id=user_id,
        )

        update_data = payload.model_dump(
            exclude_unset=True,
        )

        for key, value in update_data.items():
            setattr(
                rfq,
                key,
                value,
            )

        db.commit()
        db.refresh(rfq)

        return rfq

    @staticmethod
    def delete(
        db: Session,
        rfq_id: int,
        user_id: int | None = None,
    ) -> None:
        rfq = RFQService.get_by_id(
            db=db,
            rfq_id=rfq_id,
            user_id=user_id,
        )

        db.delete(rfq)

        db.commit()

    # ------------------------------------------------------------------ counters
    @staticmethod
    def counts(db: Session, rfq_ids: list[int]) -> dict[int, dict[str, int]]:
        """Bulk counters for list views — three queries, not three per RFQ."""

        if not rfq_ids:
            return {}

        result: dict[int, dict[str, int]] = {
            rfq_id: {
                "invitation_count": 0,
                "responded_count": 0,
                "pending_count": 0,
                "incomplete_count": 0,
                "quote_count": 0,
                "complete_priced_quotes": 0,
            }
            for rfq_id in rfq_ids
        }

        invite_rows = db.execute(
            select(
                Invitation.rfq_id,
                Invitation.status,
                Invitation.responded_at,
                func.count(Invitation.id),
            )
            .where(Invitation.rfq_id.in_(rfq_ids))
            .group_by(Invitation.rfq_id, Invitation.status, Invitation.responded_at)
        ).all()

        for rfq_id, status, responded_at, count in invite_rows:
            bucket = result.get(rfq_id)

            if bucket is None:
                continue

            bucket["invitation_count"] += count

            if responded_at is not None or status == "submitted":
                bucket["responded_count"] += count
            elif status == "incomplete":
                bucket["incomplete_count"] += count
            elif status == "pending":
                bucket["pending_count"] += count

        quote_rows = db.execute(
            select(
                SupplierQuote.rfq_id,
                SupplierQuote.completeness,
                SupplierQuote.unit_price,
                func.count(SupplierQuote.id),
            )
            .where(SupplierQuote.rfq_id.in_(rfq_ids))
            .group_by(
                SupplierQuote.rfq_id,
                SupplierQuote.completeness,
                SupplierQuote.unit_price,
            )
        ).all()

        for rfq_id, completeness, unit_price, count in quote_rows:
            bucket = result.get(rfq_id)

            if bucket is None:
                continue

            bucket["quote_count"] += count

            if completeness == "complete" and unit_price is not None and unit_price > 0:
                bucket["complete_priced_quotes"] += count

        return result

    @staticmethod
    def to_response(rfq: RFQ, counters: dict[str, int] | None = None) -> RFQResponse:
        counters = counters or {}

        return RFQResponse(
            id=rfq.id,
            rfq_number=rfq.rfq_number,
            item_name=rfq.item_name,
            specification=rfq.specification,
            quantity=rfq.quantity,
            delivery_expectation=rfq.delivery_expectation,
            notes=rfq.notes,
            unit=rfq.unit,
            currency=rfq.currency,
            incoterms=rfq.incoterms,
            deadline=rfq.deadline,
            required_fields=rfq.required_field_list,
            scoring_weights=rfq.scoring_weights,
            status=rfq.status,
            buyer_company=rfq.buyer_company,
            category=rfq.category,
            created_at=rfq.created_at,
            updated_at=rfq.updated_at,
            quote_count=counters.get("quote_count", 0),
            invitation_count=counters.get("invitation_count", 0),
            responded_count=counters.get("responded_count", 0),
            pending_count=counters.get("pending_count", 0),
            incomplete_count=counters.get("incomplete_count", 0),
            ready_to_compare=counters.get("complete_priced_quotes", 0) >= 1,
        )
