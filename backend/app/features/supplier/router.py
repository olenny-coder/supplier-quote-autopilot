"""Supplier router."""

from fastapi import APIRouter
from fastapi import Response

from app.core.dependencies import CurrentUser
from app.core.dependencies import DBSession
from app.features.supplier.schema import SupplierCreate
from app.features.supplier.schema import SupplierResponse
from app.features.supplier.schema import SupplierStats
from app.features.supplier.schema import SupplierUpdate
from app.features.supplier.service import SupplierService

router = APIRouter(
    prefix="/suppliers",
    tags=["Suppliers"],
)


@router.get(
    "",
    response_model=list[SupplierStats],
)
def get_suppliers(
    user: CurrentUser,
    db: DBSession,
):
    """The buyer's supplier directory, with response statistics."""

    suppliers = SupplierService.get_all(db=db, user_id=user.id)

    return [
        SupplierStats(
            **SupplierResponse.model_validate(supplier).model_dump(),
            **SupplierService.stats(db=db, user_id=user.id, supplier_id=supplier.id),
        )
        for supplier in suppliers
    ]


@router.post(
    "",
    response_model=SupplierResponse,
    status_code=201,
)
def create_supplier(
    payload: SupplierCreate,
    user: CurrentUser,
    db: DBSession,
):
    return SupplierService.create(db=db, user_id=user.id, payload=payload)


@router.get(
    "/{supplier_id}",
    response_model=SupplierStats,
)
def get_supplier(
    supplier_id: int,
    user: CurrentUser,
    db: DBSession,
):
    supplier = SupplierService.get_by_id(db=db, user_id=user.id, supplier_id=supplier_id)

    return SupplierStats(
        **SupplierResponse.model_validate(supplier).model_dump(),
        **SupplierService.stats(db=db, user_id=user.id, supplier_id=supplier_id),
    )


@router.patch(
    "/{supplier_id}",
    response_model=SupplierResponse,
)
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    user: CurrentUser,
    db: DBSession,
):
    return SupplierService.update(
        db=db,
        user_id=user.id,
        supplier_id=supplier_id,
        payload=payload,
    )


@router.delete(
    "/{supplier_id}",
    status_code=204,
)
def delete_supplier(
    supplier_id: int,
    user: CurrentUser,
    db: DBSession,
):
    SupplierService.delete(db=db, user_id=user.id, supplier_id=supplier_id)

    return Response(status_code=204)
