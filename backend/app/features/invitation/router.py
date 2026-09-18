"""Invitation router — buyer-facing management of supplier form links."""

from fastapi import APIRouter
from fastapi import Response

from app.core.dependencies import CurrentUser
from app.core.dependencies import DBSession
from app.core.exceptions import BadRequestError
from app.features.invitation.schema import InvitationResponse
from app.features.invitation.schema import InvitationsBulkCreate
from app.features.invitation.schema import ResendResponse
from app.features.invitation.service import InvitationService
from app.features.followup.repository import followup_label

router = APIRouter(
    tags=["Invitations"],
)


@router.get(
    "/rfqs/{rfq_id}/invitations",
    response_model=list[InvitationResponse],
)
def list_invitations(
    rfq_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Every invited supplier and where they stand: pending, submitted, incomplete, expired."""

    rfq = InvitationService.get_rfq(db=db, user_id=user.id, rfq_id=rfq_id)

    invitations = InvitationService.list_for_rfq(db=db, rfq_id=rfq_id)

    return [
        InvitationService.to_response(invitation, rfq, invitation.quote)
        for invitation in invitations
    ]


@router.post(
    "/rfqs/{rfq_id}/invitations",
    response_model=list[InvitationResponse],
    status_code=201,
)
def create_invitations(
    rfq_id: int,
    payload: InvitationsBulkCreate,
    user: CurrentUser,
    db: DBSession,
):
    """Invite one or more suppliers; optionally email the links immediately."""

    rfq = InvitationService.get_rfq(db=db, user_id=user.id, rfq_id=rfq_id)

    invitations = InvitationService.bulk_create(
        db=db,
        user_id=user.id,
        rfq_id=rfq_id,
        supplier_ids=payload.supplier_ids,
        send_now=payload.send_now,
    )

    return [
        InvitationService.to_response(invitation, rfq, invitation.quote)
        for invitation in invitations
    ]


@router.get(
    "/invitations/{invitation_id}",
    response_model=InvitationResponse,
)
def get_invitation(
    invitation_id: int,
    user: CurrentUser,
    db: DBSession,
):
    invitation = InvitationService.get_by_id(
        db=db, user_id=user.id, invitation_id=invitation_id
    )

    return InvitationService.to_response(invitation)


@router.post(
    "/invitations/{invitation_id}/resend",
    response_model=ResendResponse,
)
def resend_invitation(
    invitation_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Manually resend the form link. Logged as a FollowUp of kind ``manual``."""

    invitation = InvitationService.get_by_id(
        db=db, user_id=user.id, invitation_id=invitation_id
    )

    followup = InvitationService.resend(db=db, user_id=user.id, invitation_id=invitation_id)

    return ResendResponse(
        invitation_id=invitation.id,
        status=followup.status,
        sent_to=followup.to_email,
        message=followup_label(followup),
        followup_id=followup.id,
    )


@router.post(
    "/invitations/{invitation_id}/cancel",
    response_model=InvitationResponse,
)
def cancel_invitation(
    invitation_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Withdraw an invitation. The token stops working immediately."""

    from app.core.mixins import utcnow

    invitation = InvitationService.get_by_id(
        db=db, user_id=user.id, invitation_id=invitation_id
    )

    if invitation.quote is not None:
        raise BadRequestError(
            "This supplier has already submitted a quote, so the invitation "
            "cannot be withdrawn. Delete the quote instead if it was sent in error."
        )

    invitation.status = "cancelled"
    invitation.cancelled_at = utcnow()

    db.commit()
    db.refresh(invitation)

    return InvitationService.to_response(invitation)


@router.delete(
    "/invitations/{invitation_id}",
    status_code=204,
)
def delete_invitation(
    invitation_id: int,
    user: CurrentUser,
    db: DBSession,
):
    invitation = InvitationService.get_by_id(
        db=db, user_id=user.id, invitation_id=invitation_id
    )

    db.delete(invitation)
    db.commit()

    return Response(status_code=204)
