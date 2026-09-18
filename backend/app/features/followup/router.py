"""Follow-up router — the buyer's communication log, plus the cron tick endpoint."""

from fastapi import APIRouter
from fastapi import Header
from fastapi import Request

from app.core.config import settings
from app.core.dependencies import CurrentUser
from app.core.dependencies import DBSession
from app.core.exceptions import ForbiddenError
from app.features.followup import repository
from app.features.followup.schema import FollowUpActionResponse
from app.features.followup.schema import FollowUpRejectRequest
from app.features.followup.schema import FollowUpResponse
from app.features.followup.schema import FollowUpUpdate
from app.features.followup.schema import ManualFollowUpRequest
from app.features.followup.schema import SchedulerTickResponse
from app.features.followup.service import FollowUpService
from app.features.followup.service import run_scheduler
from app.features.invitation.service import InvitationService

router = APIRouter(
    tags=["Follow-ups"],
)

internal_router = APIRouter(
    prefix="/internal",
    tags=["Internal"],
)


# ------------------------------------------------------------------- buyer API
@router.get(
    "/rfqs/{rfq_id}/follow-ups",
    response_model=list[FollowUpResponse],
)
def list_follow_ups(
    rfq_id: int,
    user: CurrentUser,
    db: DBSession,
    status: str | None = None,
):
    """Every message sent or drafted for this RFQ — the communication log."""

    InvitationService.get_rfq(db=db, user_id=user.id, rfq_id=rfq_id)

    followups = repository.list_for_rfq(db=db, rfq_id=rfq_id, status=status)

    return [repository.to_response(followup) for followup in followups]


@router.get(
    "/follow-ups",
    response_model=list[FollowUpResponse],
)
def list_pending_follow_ups(
    user: CurrentUser,
    db: DBSession,
    status: str = "draft",
):
    """Workspace-wide queue, defaulting to drafts awaiting the buyer's approval."""

    if status == "draft":
        followups = repository.list_pending_drafts(db=db, user_id=user.id)
    else:
        from sqlalchemy import select

        from app.features.followup.model import FollowUp
        from app.features.rfq.model import RFQ

        stmt = (
            select(FollowUp)
            .join(RFQ, RFQ.id == FollowUp.rfq_id)
            .where(FollowUp.status == status, RFQ.user_id == user.id)
            .order_by(FollowUp.created_at.desc())
            .limit(200)
        )

        followups = list(db.scalars(stmt).all())

    return [repository.to_response(followup) for followup in followups]


@router.get(
    "/follow-ups/{followup_id}",
    response_model=FollowUpResponse,
)
def get_follow_up(
    followup_id: int,
    user: CurrentUser,
    db: DBSession,
):
    return repository.to_response(
        FollowUpService.get_for_user(db=db, user_id=user.id, followup_id=followup_id)
    )


@router.patch(
    "/follow-ups/{followup_id}",
    response_model=FollowUpResponse,
)
def update_follow_up(
    followup_id: int,
    payload: FollowUpUpdate,
    user: CurrentUser,
    db: DBSession,
):
    """Edit a draft's copy before approving it."""

    followup = FollowUpService.get_for_user(db=db, user_id=user.id, followup_id=followup_id)

    if payload.subject:
        followup.subject = payload.subject
    if payload.body:
        followup.body = payload.body

    db.commit()
    db.refresh(followup)

    return repository.to_response(followup)


@router.post(
    "/follow-ups/{followup_id}/approve",
    response_model=FollowUpActionResponse,
)
def approve_follow_up(
    followup_id: int,
    payload: FollowUpUpdate,
    user: CurrentUser,
    db: DBSession,
):
    """Approve (and optionally edit) a queued draft, then send it."""

    followup, message = FollowUpService.approve(
        db=db,
        user_id=user.id,
        followup_id=followup_id,
        subject=payload.subject,
        body=payload.body,
    )

    return FollowUpActionResponse(
        followup=repository.to_response(followup),
        message=message,
    )


@router.post(
    "/follow-ups/{followup_id}/reject",
    response_model=FollowUpActionResponse,
)
def reject_follow_up(
    followup_id: int,
    payload: FollowUpRejectRequest,
    user: CurrentUser,
    db: DBSession,
):
    followup = FollowUpService.reject(
        db=db,
        user_id=user.id,
        followup_id=followup_id,
        reason=payload.reason,
    )

    return FollowUpActionResponse(
        followup=repository.to_response(followup),
        message="Draft discarded — no email was sent.",
    )


@router.post(
    "/follow-ups/manual",
    response_model=FollowUpActionResponse,
    status_code=201,
)
def create_manual_follow_up(
    payload: ManualFollowUpRequest,
    user: CurrentUser,
    db: DBSession,
):
    """Send a reminder right now, bypassing the configured reminder intervals."""

    followup = FollowUpService.create_manual(
        db=db,
        user_id=user.id,
        invitation_id=payload.invitation_id,
        mode=payload.mode,
        subject=payload.subject,
        body=payload.body,
        send_now=payload.send_now,
    )

    return FollowUpActionResponse(
        followup=repository.to_response(followup),
        message=repository.followup_label(followup),
    )


# ------------------------------------------------------------ cron tick (cron)
@internal_router.post(
    "/scheduler/tick",
    response_model=SchedulerTickResponse,
)
def scheduler_tick(
    db: DBSession,
    request: Request,
    x_scheduler_secret: str | None = Header(default=None, alias="X-Scheduler-Secret"),
):
    """Run one follow-up sweep.

    Authenticated by a shared secret rather than a buyer token, because the caller
    is a cron. When ``SCHEDULER_SECRET`` is unset the endpoint is refused outright:
    an open, unauthenticated endpoint that sends email is not an acceptable
    default, even in development.
    """

    if not settings.SCHEDULER_SECRET:
        raise ForbiddenError(
            "Set SCHEDULER_SECRET to enable POST /internal/scheduler/tick."
        )

    import hmac

    provided = x_scheduler_secret or request.headers.get("x-scheduler-secret") or ""

    if not hmac.compare_digest(provided, settings.SCHEDULER_SECRET):
        raise ForbiddenError("Invalid scheduler secret.")

    summary = run_scheduler(db)

    return SchedulerTickResponse(
        status="ok",
        scanned=summary.scanned,
        drafted=summary.drafted,
        sent=summary.sent,
        queued_for_approval=summary.queued_for_approval,
        skipped=summary.skipped,
        expired=summary.expired,
        failed=summary.failed,
        llm_calls=summary.llm_calls,
        auto_send_enabled=summary.auto_send_enabled,
        llm_available=summary.llm_available,
        run_at=summary.run_at,
        actions=summary.actions,
    )


@internal_router.post(
    "/expire",
    response_model=SchedulerTickResponse,
)
def expire_tick(
    db: DBSession,
    request: Request,
    x_scheduler_secret: str | None = Header(default=None, alias="X-Scheduler-Secret"),
):
    """Expire overdue invitations and close stale RFQs without drafting anything."""

    if not settings.SCHEDULER_SECRET:
        raise ForbiddenError("Set SCHEDULER_SECRET to enable this endpoint.")

    import hmac

    provided = x_scheduler_secret or request.headers.get("x-scheduler-secret") or ""

    if not hmac.compare_digest(provided, settings.SCHEDULER_SECRET):
        raise ForbiddenError("Invalid scheduler secret.")

    from app.features.followup.service import expire_overdue

    count = expire_overdue(db)

    return SchedulerTickResponse(status="ok", expired=count)
