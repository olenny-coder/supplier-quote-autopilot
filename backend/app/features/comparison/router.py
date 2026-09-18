"""Comparison router — scoring, recommendation, export, and award approval."""

from fastapi import APIRouter
from fastapi import Response

from app.core.dependencies import CurrentUser
from app.core.dependencies import DBSession
from app.core.exceptions import NotFoundError
from app.features.comparison import repository
from app.features.comparison.schema import ApprovalRequest
from app.features.comparison.schema import ApprovalResponse
from app.features.comparison.schema import ComparisonListItem
from app.features.comparison.schema import ComparisonResponse
from app.features.comparison.schema import ComparisonRunRequest
from app.features.comparison.service import ComparisonService
from app.features.invitation.service import InvitationService

router = APIRouter(
    tags=["Comparison"],
)


@router.get(
    "/rfqs/{rfq_id}/comparison",
    response_model=ComparisonResponse,
)
def get_comparison(
    rfq_id: int,
    user: CurrentUser,
    db: DBSession,
    recompute: bool = False,
    use_llm: bool = False,
):
    """The current comparison for this RFQ.

    Computes one on demand when none exists yet, so the button never dead-ends.
    ``recompute=true`` forces a fresh run — use it after a new quote arrives.
    """

    rfq = InvitationService.get_rfq(db=db, user_id=user.id, rfq_id=rfq_id)

    if not rfq.quotes:
        raise NotFoundError(
            "No quotes have been received for this RFQ yet, so there is nothing "
            "to compare."
        )

    comparison = None if recompute else repository.latest_for_rfq(db, rfq_id)

    if comparison is None:
        comparison = ComparisonService.recompute(db, rfq, use_llm=use_llm)

    return ComparisonService.to_response(
        comparison, repository.latest_approval_for_rfq(db, rfq_id)
    )


@router.post(
    "/rfqs/{rfq_id}/comparison",
    response_model=ComparisonResponse,
    status_code=201,
)
def run_comparison(
    rfq_id: int,
    payload: ComparisonRunRequest,
    user: CurrentUser,
    db: DBSession,
):
    """Score the quotes and store a new snapshot. Optionally override the weights."""

    rfq = InvitationService.get_rfq(db=db, user_id=user.id, rfq_id=rfq_id)

    if not rfq.quotes:
        raise NotFoundError("No quotes have been received for this RFQ yet.")

    comparison = ComparisonService.recompute(
        db,
        rfq,
        weights=payload.weights,
        use_llm=payload.use_llm,
    )

    return ComparisonService.to_response(
        comparison, repository.latest_approval_for_rfq(db, rfq_id)
    )


@router.get(
    "/rfqs/{rfq_id}/comparison/history",
    response_model=list[ComparisonListItem],
)
def comparison_history(
    rfq_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Past scoring runs, kept because weights and FX rates change over time."""

    rfq = InvitationService.get_rfq(db=db, user_id=user.id, rfq_id=rfq_id)

    items: list[ComparisonListItem] = []

    for comparison in repository.list_for_rfq(db, rfq_id):
        name = None

        for result in comparison.results or []:
            if result.get("quote_id") == comparison.recommended_quote_id:
                name = result.get("supplier_name")
                break

        best = None

        if comparison.recommended_quote_id is not None:
            for result in comparison.results or []:
                if result.get("quote_id") == comparison.recommended_quote_id:
                    best = result.get("total_base")
                    break

        items.append(
            ComparisonListItem(
                id=comparison.id,
                rfq_id=comparison.rfq_id,
                rfq_number=rfq.rfq_number,
                item_name=rfq.item_name,
                recommended_quote_id=comparison.recommended_quote_id,
                recommended_supplier=name,
                best_total_cost=str(best) if best is not None else None,
                base_currency=comparison.base_currency,
                is_conclusive=bool(comparison.is_conclusive),
                created_at=comparison.created_at,
            )
        )

    return items


@router.get(
    "/rfqs/{rfq_id}/comparison/export.csv",
)
def export_comparison_csv(
    rfq_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Download the comparison as CSV, including the rationale and every caveat."""

    rfq = InvitationService.get_rfq(db=db, user_id=user.id, rfq_id=rfq_id)

    comparison = repository.latest_for_rfq(db, rfq_id)

    if comparison is None:
        if not rfq.quotes:
            raise NotFoundError("No quotes have been received for this RFQ yet.")

        comparison = ComparisonService.recompute(db, rfq, use_llm=False)

    csv_text = ComparisonService.export_csv(db, rfq, comparison)

    filename = f"comparison-{rfq.rfq_number or rfq.id}.csv"

    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/rfqs/{rfq_id}/comparison/approve",
    response_model=ApprovalResponse,
    status_code=201,
)
def approve_quote(
    rfq_id: int,
    payload: ApprovalRequest,
    user: CurrentUser,
    db: DBSession,
):
    """Record the buyer's award decision.

    The recommendation above is advisory. This endpoint is the only way an RFQ
    becomes awarded, and a rejection or deferral is logged just as explicitly as an
    approval — including when the buyer overrides the recommendation.
    """

    rfq = InvitationService.get_rfq(db=db, user_id=user.id, rfq_id=rfq_id)

    approval = ComparisonService.approve(
        db,
        rfq,
        user,
        quote_id=payload.quote_id,
        decision=payload.decision,
        note=payload.note,
    )

    return ComparisonService.approval_response(approval)


@router.get(
    "/rfqs/{rfq_id}/approvals",
    response_model=list[ApprovalResponse],
)
def list_approvals(
    rfq_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """The award audit trail for this RFQ, newest first."""

    InvitationService.get_rfq(db=db, user_id=user.id, rfq_id=rfq_id)

    return [
        ComparisonService.approval_response(approval)
        for approval in repository.list_approvals(db, rfq_id)
    ]
