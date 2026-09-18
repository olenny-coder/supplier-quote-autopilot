"""RFQ router.

Extended in place. Every existing route keeps its path and verb. The additions:

* ``GET /rfqs`` now returns per-RFQ counters (invited / responded / pending) so the
  dashboard is one request instead of N.
* ``POST /rfqs`` can create suppliers and issue their tokenized form links in the
  same call — the acceptance path is "create an RFQ, add 3 suppliers, get 3 links".
* ``GET /rfqs/{id}/overview`` returns everything the detail page needs at once.
"""

from fastapi import APIRouter
from fastapi import Response
from typing import Any

from app.core.config import settings
from app.core.dependencies import CurrentUser
from app.core.dependencies import DBSession
from app.features.invitation.service import InvitationService
from app.features.rfq.schema import RFQCreate
from app.features.rfq.schema import RFQResponse
from app.features.rfq.schema import RFQUpdate
from app.features.rfq.service import RFQService
from app.features.supplier.schema import SupplierCreate
from app.features.supplier.service import SupplierService

router = APIRouter(
    prefix="/rfqs",
    tags=["RFQs"],
)


@router.get(
    "",
    response_model=list[RFQResponse],
)
def get_rfqs(
    user: CurrentUser,
    db: DBSession,
):
    rfqs = RFQService.get_all(db=db, user_id=user.id)

    counters = RFQService.counts(db, [rfq.id for rfq in rfqs])

    return [RFQService.to_response(rfq, counters.get(rfq.id)) for rfq in rfqs]


@router.get(
    "/{rfq_id}",
    response_model=RFQResponse,
)
def get_rfq(
    rfq_id: int,
    user: CurrentUser,
    db: DBSession,
):
    rfq = RFQService.get_by_id(db=db, rfq_id=rfq_id, user_id=user.id)

    return RFQService.to_response(rfq, RFQService.counts(db, [rfq_id]).get(rfq_id))


@router.post(
    "",
    response_model=RFQResponse,
    status_code=201,
)
def create_rfq(
    payload: RFQCreate,
    user: CurrentUser,
    db: DBSession,
):
    """Create an RFQ, optionally with its suppliers and invitations in one call."""

    rfq = RFQService.create(db=db, payload=payload, user_id=user.id)

    # The buyer's company is the form's branding; default it from their profile.
    if not rfq.buyer_company:
        rfq.buyer_company = user.company_name
        db.commit()
        db.refresh(rfq)

    supplier_ids: list[int] = list(payload.supplier_ids or [])

    for inline in payload.new_suppliers or []:
        supplier = SupplierService.create(
            db=db,
            user_id=user.id,
            payload=SupplierCreate(
                name=inline.name,
                contact_email=inline.contact_email,
                contact_name=inline.contact_name,
                country=inline.country,
                risk_rating=inline.risk_rating,
            ),
            reuse_existing=True,
        )
        supplier_ids.append(supplier.id)

    if supplier_ids:
        try:
            InvitationService.bulk_create(
                db=db,
                user_id=user.id,
                rfq_id=rfq.id,
                supplier_ids=supplier_ids,
                send_now=payload.send_invitations,
            )
        except Exception:  # noqa: BLE001 - a mail outage must not lose the RFQ
            # The RFQ and invitations exist; the links are visible in the dashboard
            # and can be resent. Failing the whole request would be worse.
            import logging

            logging.getLogger(__name__).exception(
                "RFQ %s created but invitations could not be sent", rfq.id
            )

    db.refresh(rfq)

    return RFQService.to_response(rfq, RFQService.counts(db, [rfq.id]).get(rfq.id))


@router.put(
    "/{rfq_id}",
    response_model=RFQResponse,
)
def update_rfq(
    rfq_id: int,
    payload: RFQUpdate,
    user: CurrentUser,
    db: DBSession,
):
    rfq = RFQService.update(
        db=db,
        rfq_id=rfq_id,
        payload=payload,
        user_id=user.id,
    )

    return RFQService.to_response(rfq, RFQService.counts(db, [rfq_id]).get(rfq_id))


@router.patch(
    "/{rfq_id}",
    response_model=RFQResponse,
)
def patch_rfq(
    rfq_id: int,
    payload: RFQUpdate,
    user: CurrentUser,
    db: DBSession,
):
    """Same as PUT, but only the supplied fields are changed."""

    rfq = RFQService.update(
        db=db,
        rfq_id=rfq_id,
        payload=payload,
        user_id=user.id,
    )

    return RFQService.to_response(rfq, RFQService.counts(db, [rfq_id]).get(rfq_id))


@router.delete(
    "/{rfq_id}",
    status_code=204,
)
def delete_rfq(
    rfq_id: int,
    user: CurrentUser,
    db: DBSession,
):
    RFQService.delete(
        db=db,
        rfq_id=rfq_id,
        user_id=user.id,
    )

    return Response(status_code=204)


@router.get(
    "/{rfq_id}/overview",
)
def get_rfq_overview(
    rfq_id: int,
    user: CurrentUser,
    db: DBSession,
) -> dict[str, Any]:
    """Everything the RFQ detail page needs, in one request.

    The dashboard otherwise fires five calls on open (RFQ, invitations, quotes,
    follow-ups, comparison) and has to render five loading states. One endpoint
    keeps the page fast on a cold-starting free-tier backend.
    """

    from app.features.comparison.repository import latest_for_rfq
    from app.features.comparison.service import ComparisonService
    from app.features.followup import repository as followup_repository

    rfq = RFQService.get_by_id(db=db, rfq_id=rfq_id, user_id=user.id)

    invitations = InvitationService.list_for_rfq(db=db, rfq_id=rfq_id)

    quotes = list(rfq.quotes)

    followups = followup_repository.list_for_rfq(db=db, rfq_id=rfq_id, limit=100)

    comparison = latest_for_rfq(db, rfq_id)

    return {
        "rfq": RFQService.to_response(
            rfq, RFQService.counts(db, [rfq_id]).get(rfq_id)
        ).model_dump(mode="json"),
        "invitations": [
            InvitationService.to_response(invitation, rfq, invitation.quote).model_dump(
                mode="json"
            )
            for invitation in invitations
        ],
        "quotes": [
            ComparisonService.quote_summary(quote).model_dump(mode="json")
            for quote in quotes
        ],
        "followups": [
            followup_repository.to_response(followup).model_dump(mode="json")
            for followup in followups
        ],
        "comparison": (
            ComparisonService.to_response(comparison).model_dump(mode="json")
            if comparison is not None
            else None
        ),
        "capabilities": {
            "auto_send_followups": settings.AUTO_SEND_FOLLOWUPS,
        },
    }
