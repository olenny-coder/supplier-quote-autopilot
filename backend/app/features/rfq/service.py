"""RFQ service.

Extended in place. The original signatures are preserved — ``get_all(db)``,
``get_by_id(db, rfq_id)``, ``create(db, payload)``, ``update``, ``delete`` all work
exactly as before — with an optional ``user_id`` that scopes results to a tenant
when the API supplies one. That keeps the base codebase's tests and the CSV/PDF
importers working unchanged.
"""

import logging
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.core.exceptions import NotFoundError
from app.core.mixins import utcnow
from app.features.audit.service import AuditService
from app.features.invitation.model import Invitation
from app.features.quote.model import SupplierQuote
from app.features.rfq import taxonomy
from app.features.rfq.model import RFQ
from app.features.rfq.model import RFQ_STATUSES
from app.features.rfq.schema import RFQCreate
from app.features.rfq.schema import RFQResponse
from app.features.rfq.schema import RFQUpdate

logger = logging.getLogger(__name__)

#: Applied when a buyer does not name a deadline: two weeks to quote.
DEFAULT_QUOTE_WINDOW_DAYS = 14


def _audit_value(value: object) -> object:
    """A JSON-safe, comparable form of a column value, for the change detail.

    ``Decimal`` and ``date`` are not JSON-serialisable and compare unequally to
    themselves across types (``Decimal("9.0") != 9.0`` is false in Python but
    ``Decimal("9.00") != Decimal("9.0")`` is also false — the comparison is fine,
    the *serialisation* is what breaks). Converting once, here, keeps the engine
    change list honest and the JSON column writable.
    """

    if hasattr(value, "isoformat"):
        return value.isoformat()

    if isinstance(value, Decimal):
        return str(value)

    return value


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
            data["required_fields"] = taxonomy.default_required_fields(
                data.get("procurement_type")
            )

        # GST defaults for the currency rather than to zero. A Singapore buyer
        # comparing works quotes wants GST in the arithmetic from the start; a
        # deployment elsewhere sets DEFAULT_GST_RATE=0 or sets it per RFQ.
        if data.get("gst_rate") is None and (data.get("currency") or "").upper() == "SGD":
            data["gst_rate"] = Decimal(str(settings.DEFAULT_GST_RATE))

        if data.get("status") not in RFQ_STATUSES:
            raise BadRequestError(f"Unknown RFQ status '{data.get('status')}'.")

        rfq = RFQ(
            user_id=user_id,
            **data,
        )

        db.add(rfq)
        db.commit()
        db.refresh(rfq)

        # Written after the commit so the entry can name the RFQ number, which the
        # database generates. Its own commit, so a failure here cannot roll back an
        # RFQ the buyer has already been told exists.
        AuditService.record(
            db,
            user_id=user_id,
            action="rfq.created",
            entity_type="rfq",
            entity_id=rfq.id,
            rfq=rfq,
            summary=(
                f"Created {rfq.rfq_number} — {rfq.item_name} "
                f"({rfq.quantity:,} {rfq.unit}), {rfq.procurement_type} procurement."
            ),
            detail={
                "item_name": rfq.item_name,
                "quantity": rfq.quantity,
                "unit": rfq.unit,
                "currency": rfq.currency,
                "deadline": rfq.deadline.date().isoformat() if rfq.deadline else None,
            },
            commit=True,
        )

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

        # Recorded before the values are overwritten: the log has to name what
        # changed, and after this loop the previous values are gone. `old` is the
        # only copy of them left in the process.
        changed = {
            key: {"from": _audit_value(getattr(rfq, key, None)), "to": _audit_value(value)}
            for key, value in update_data.items()
            if _audit_value(getattr(rfq, key, None)) != _audit_value(value)
        }

        for key, value in update_data.items():
            setattr(
                rfq,
                key,
                value,
            )

        db.commit()
        db.refresh(rfq)

        if changed:
            AuditService.record(
                db,
                user_id=user_id,
                action="rfq.updated",
                entity_type="rfq",
                entity_id=rfq.id,
                rfq=rfq,
                summary=(
                    f"Changed {len(changed)} field(s) on {rfq.rfq_number}: "
                    + ", ".join(sorted(changed))
                    + "."
                ),
                detail={"changed": changed},
                commit=True,
            )

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

        # Captured before the delete: this entry is the only remaining record of
        # what the RFQ was, and it is the reason `rfq_number` and `item_name` are
        # snapshotted onto every entry rather than joined at read time.
        number = rfq.rfq_number
        item_name = rfq.item_name
        quote_count = len(rfq.quotes or [])
        invitation_count = len(rfq.invitations or [])

        owner_id = rfq.user_id if rfq.user_id is not None else user_id

        db.delete(rfq)

        db.commit()

        AuditService.record(
            db,
            user_id=owner_id,
            # No `rfq=` here: the row is gone. The snapshots below are what keeps
            # this entry readable, and `rfq_id` is kept so the history that led to
            # the deletion still filters together with it.
            action="rfq.deleted",
            entity_type="rfq",
            entity_id=rfq_id,
            rfq_id=rfq_id,
            rfq_number=number,
            item_name=item_name,
            summary=(
                f"Deleted {number} — {item_name}, with {invitation_count} "
                f"invitation(s) and {quote_count} quote(s)."
            ),
            detail={
                "rfq_number": number,
                "item_name": item_name,
                "invitations": invitation_count,
                "quotes": quote_count,
            },
            commit=True,
        )

    # ------------------------------------------------------------------ counters
    @staticmethod
    def counts(db: Session, rfq_ids: list[int]) -> dict[int, dict[str, int]]:
        """Bulk counters for list views — a fixed number of queries per RFQ.

        Buckets are derived from the *quote's* completeness rather than trusting
        ``Invitation.status``, because the stored status can lag (a quote created
        by a path that did not update the invitation) and a wrong respond/pending
        count is exactly the number a buyer acts on.

        ``incomplete_count`` is a **subset of** ``responded_count``: a supplier who
        sent a partial quote did respond, and also still owes something.
        """

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

        rows = db.execute(
            select(
                Invitation.rfq_id,
                Invitation.status,
                Invitation.responded_at,
                SupplierQuote.id,
                SupplierQuote.completeness,
                SupplierQuote.unit_price,
            )
            .outerjoin(SupplierQuote, SupplierQuote.invitation_id == Invitation.id)
            .where(Invitation.rfq_id.in_(rfq_ids))
        ).all()

        TERMINAL = {"expired", "cancelled", "declined"}

        for (
            rfq_id,
            invitation_status,
            responded_at,
            quote_id,
            completeness,
            unit_price,
        ) in rows:
            bucket = result.get(rfq_id)

            if bucket is None:
                continue

            bucket["invitation_count"] += 1

            if quote_id is not None:
                bucket["responded_count"] += 1
                bucket["quote_count"] += 1

                if completeness == "incomplete":
                    bucket["incomplete_count"] += 1
                elif unit_price is not None and unit_price > 0:
                    bucket["complete_priced_quotes"] += 1

                continue

            if invitation_status in TERMINAL:
                # Neither awaiting nor owed: the window closed.
                continue

            if responded_at is not None or invitation_status == "submitted":
                bucket["responded_count"] += 1
            elif invitation_status == "incomplete":
                bucket["responded_count"] += 1
                bucket["incomplete_count"] += 1
            else:
                bucket["pending_count"] += 1

        # Quotes that are not attached to an invitation (manual entry, CSV/PDF
        # import) still need to appear in the quote count.
        orphan_rows = db.execute(
            select(
                SupplierQuote.rfq_id,
                SupplierQuote.completeness,
                SupplierQuote.unit_price,
                func.count(SupplierQuote.id),
            )
            .where(SupplierQuote.rfq_id.in_(rfq_ids), SupplierQuote.invitation_id.is_(None))
            .group_by(
                SupplierQuote.rfq_id,
                SupplierQuote.completeness,
                SupplierQuote.unit_price,
            )
        ).all()

        for rfq_id, completeness, unit_price, count in orphan_rows:
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

        procurement_type = rfq.procurement_type or taxonomy.DEFAULT_PROCUREMENT_TYPE
        required = rfq.required_field_list

        return RFQResponse(
            id=rfq.id,
            rfq_number=rfq.rfq_number,
            item_name=rfq.item_name,
            specification=rfq.specification,
            quantity=rfq.quantity,
            delivery_expectation=rfq.delivery_expectation,
            notes=rfq.notes,
            procurement_type=procurement_type,
            unit=rfq.unit,
            currency=rfq.currency,
            incoterms=rfq.incoterms,
            deadline=rfq.deadline,
            required_fields=required,
            scoring_weights=rfq.scoring_weights,
            status=rfq.status,
            buyer_company=rfq.buyer_company,
            category=rfq.category,
            site_name=rfq.site_name,
            site_address=rfq.site_address,
            site_access_notes=rfq.site_access_notes,
            required_response_hours=rfq.required_response_hours,
            required_accreditations=list(rfq.required_accreditations or []),
            gst_rate=rfq.gst_rate,
            created_at=rfq.created_at,
            updated_at=rfq.updated_at,
            quote_count=counters.get("quote_count", 0),
            invitation_count=counters.get("invitation_count", 0),
            responded_count=counters.get("responded_count", 0),
            pending_count=counters.get("pending_count", 0),
            incomplete_count=counters.get("incomplete_count", 0),
            ready_to_compare=counters.get("complete_priced_quotes", 0) >= 1,
            # Supplier-facing labels, so the dashboard does not hard-code the
            # vocabulary. Adding a field becomes a backend-only change.
            required_field_labels=[
                taxonomy.label_for(field, procurement_type) for field in required
            ],
        )
