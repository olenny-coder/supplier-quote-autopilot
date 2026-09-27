"""Supplier router."""

from fastapi import APIRouter
from fastapi import File
from fastapi import Response
from fastapi import UploadFile

from app.core.dependencies import CurrentUser
from app.core.dependencies import DBSession
from app.core.exceptions import BadRequestError
from app.features.supplier.importer import parse_supplier_csv
from app.features.supplier.schema import SupplierCreate
from app.features.supplier.schema import SupplierImportRequest
from app.features.supplier.schema import SupplierImportResponse
from app.features.supplier.schema import SupplierImportRowError
from app.features.supplier.schema import SupplierResponse
from app.features.supplier.schema import SupplierStats
from app.features.supplier.schema import SupplierUpdate
from app.features.supplier.service import SupplierService

router = APIRouter(
    prefix="/suppliers",
    tags=["Suppliers"],
)

#: A directory export is a text file; 2 MB is a few hundred thousand rows, far more
#: than any facilities team has contractors. The cap exists so a mistyped upload of
#: a database dump is refused rather than parsed.
MAX_IMPORT_BYTES = 2 * 1024 * 1024


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
    "/import",
    response_model=SupplierImportResponse,
)
def import_suppliers(
    payload: SupplierImportRequest,
    user: CurrentUser,
    db: DBSession,
):
    """Add many suppliers from a list of rows.

    Row-level results: a bad row is reported with its position and does not stop the
    rest. See :meth:`SupplierService.import_many` for why the default on a duplicate
    email is to skip rather than overwrite.
    """

    if not payload.suppliers:
        raise BadRequestError("There is nothing to import.")

    return SupplierService.import_many(
        db,
        user.id,
        payload.suppliers,
        on_duplicate=payload.on_duplicate,
    )


@router.post(
    "/import/csv",
    response_model=SupplierImportResponse,
)
async def import_suppliers_csv(
    user: CurrentUser,
    db: DBSession,
    file: UploadFile = File(...),
    on_duplicate: str = "skip",
):
    """Add many suppliers from an uploaded CSV — the spreadsheet they already have.

    A CSV rather than a bespoke template because the buyer's list is almost always
    already in one, and making them reshape it first is the friction that stops a
    directory being populated at all.
    """

    raw = await file.read()

    if not raw:
        raise BadRequestError("That file is empty.")

    if len(raw) > MAX_IMPORT_BYTES:
        raise BadRequestError(
            f"That file is larger than {MAX_IMPORT_BYTES // (1024 * 1024)} MB. "
            f"Import it in parts."
        )

    try:
        # `utf-8-sig` strips the byte-order mark a Windows spreadsheet writes; left
        # in place it becomes part of the first header and nothing matches.
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise BadRequestError(
            "That file is not UTF-8 text. Re-export the spreadsheet as CSV UTF-8 "
            "and try again."
        )

    parsed = parse_supplier_csv(text)

    problems = [
        SupplierImportRowError(row=problem.row, email=problem.email, name=problem.name, reason=problem.reason)
        for problem in parsed.problems
    ]

    if not parsed.suppliers:
        detail = problems[0].reason if problems else "No supplier rows found in that file."

        raise BadRequestError(detail)

    result = SupplierService.import_many(
        db,
        user.id,
        parsed.suppliers,
        on_duplicate=on_duplicate,
        rows=parsed.rows,
    )

    # Parsing problems and import problems are both row-level, so they are merged
    # into one list. A buyer fixes a spreadsheet in one pass, not two.
    result.errors = problems + result.errors
    result.failed = len(result.errors)
    result.total = result.created + result.updated + result.skipped + result.failed
    result.message = SupplierService.import_message(
        result.created, result.updated, result.skipped, result.failed
    )

    return result


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
