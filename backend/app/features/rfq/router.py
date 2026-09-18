from fastapi import APIRouter
from fastapi import Response

from app.core.dependencies import DBSession
from app.features.rfq.schema import RFQCreate
from app.features.rfq.schema import RFQResponse
from app.features.rfq.schema import RFQUpdate
from app.features.rfq.service import RFQService

router = APIRouter(
    prefix="/rfqs",
    tags=["RFQs"],
)


@router.get(
    "",
    response_model=list[RFQResponse],
)
def get_rfqs(
    db: DBSession,
):
    return RFQService.get_all(db)


@router.get(
    "/{rfq_id}",
    response_model=RFQResponse,
)
def get_rfq(
    rfq_id: int,
    db: DBSession,
):
    return RFQService.get_by_id(
        db=db,
        rfq_id=rfq_id,
    )


@router.post(
    "",
    response_model=RFQResponse,
    status_code=201,
)
def create_rfq(
    payload: RFQCreate,
    db: DBSession,
):
    return RFQService.create(
        db=db,
        payload=payload,
    )


@router.put(
    "/{rfq_id}",
    response_model=RFQResponse,
)
def update_rfq(
    rfq_id: int,
    payload: RFQUpdate,
    db: DBSession,
):
    return RFQService.update(
        db=db,
        rfq_id=rfq_id,
        payload=payload,
    )


@router.delete(
    "/{rfq_id}",
    status_code=204,
)
def delete_rfq(
    rfq_id: int,
    db: DBSession,
):
    RFQService.delete(
        db=db,
        rfq_id=rfq_id,
    )

    return Response(status_code=204)
