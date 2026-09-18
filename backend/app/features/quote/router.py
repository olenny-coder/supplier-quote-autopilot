"""Quote router.

Extended in place. Route paths and verbs are unchanged; what changed is that they
are now authenticated and return the richer :class:`QuoteSummary` projection
(normalized cost, completeness, risk flags, attachments) instead of the base
codebase's seven-field response.

The manual-entry and CSV/PDF import paths still work exactly as before, and manual
quotes now get the same completeness assessment and normalization that form
submissions do — otherwise a hand-entered quote would silently skip the comparison
pipeline.
"""

from fastapi import APIRouter
from fastapi import File
from fastapi import Response
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.dependencies import CurrentUser
from app.core.dependencies import DBSession
from app.core.exceptions import BadRequestError
from app.features.comparison.schema import QuoteSummary
from app.features.comparison.service import ComparisonService
from app.features.invitation.service import InvitationService
from app.features.quote.importers import CSVImportService
from app.features.quote.importers import PDFImportService
from app.features.quote.model import SupplierQuote
from app.features.quote.schema import QuoteCreate
from app.features.quote.schema import QuoteUpdate
from app.features.quote.service import QuoteService
from app.features.rfq.model import RFQ

router = APIRouter(
    tags=["Quotes"],
)

MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB


def build_quote_response(quote: SupplierQuote) -> QuoteSummary:
    """ORM row -> API projection, including the RFQ quantity for totals."""

    return ComparisonService.quote_summary(quote)


def _apply_completeness(db: Session, rfq: RFQ, quote: SupplierQuote) -> None:
    """Assess a manually entered or imported quote against the RFQ's contract."""

    fields = {
        "unit_price": quote.unit_price,
        "currency": quote.currency,
        "unit": quote.unit,
        "lead_time_days": quote.lead_time,
        "moq": quote.moq,
        "payment_terms": quote.payment_terms,
        "incoterms": quote.incoterms,
        "validity_date": quote.validity_date,
        "warranty_months": quote.warranty_months,
        "shipping_cost": quote.shipping_cost,
        "duties": quote.duties,
        "taxes": quote.taxes,
        "discount": quote.discount,
    }

    from agents.quote_parser import evaluate

    report = evaluate(fields, rfq.required_field_list, raw_text=quote.remarks)

    quote.completeness = report.status
    quote.missing_fields = list(report.missing)
    quote.risk_flags = (
        ["Complete submission."]
        if report.is_complete
        else ["Missing required field(s): " + ", ".join(report.missing_labels)]
    )

    db.commit()
    db.refresh(quote)


@router.get(
    "/rfqs/{rfq_id}/quotes",
    response_model=list[QuoteSummary],
)
def get_quotes(
    rfq_id: int,
    user: CurrentUser,
    db: DBSession,
):
    """Quotes for this RFQ, cheapest unit price first (base codebase ordering)."""

    rfq = InvitationService.get_rfq(db=db, user_id=user.id, rfq_id=rfq_id)

    quotes = QuoteService.get_all_for_rfq(db=db, rfq_id=rfq.id)

    return [build_quote_response(quote) for quote in quotes]


@router.post(
    "/rfqs/{rfq_id}/quotes",
    response_model=QuoteSummary,
    status_code=201,
)
def create_quote(
    rfq_id: int,
    payload: QuoteCreate,
    user: CurrentUser,
    db: DBSession,
):
    """Manually record a quote (e.g. one that arrived by phone or email)."""

    rfq = InvitationService.get_rfq(db=db, user_id=user.id, rfq_id=rfq_id)

    quote = QuoteService.create(
        db=db,
        rfq_id=rfq.id,
        payload=payload,
    )

    _apply_completeness(db, rfq, quote)

    return build_quote_response(quote)


@router.post(
    "/rfqs/{rfq_id}/quotes/import",
)
async def import_quotes(
    rfq_id: int,
    user: CurrentUser,
    db: DBSession,
    file: UploadFile = File(...),
):
    """Bulk import from CSV (parsed directly) or PDF (vision LLM)."""

    rfq = InvitationService.get_rfq(db=db, user_id=user.id, rfq_id=rfq_id)

    contents = await file.read()

    if len(contents) > MAX_FILE_SIZE:
        raise BadRequestError("File size cannot exceed 2 MB.")

    await file.seek(0)

    filename = (file.filename or "").lower()

    if filename.endswith(".csv"):
        result = await CSVImportService.import_quotes(
            db=db,
            rfq_id=rfq.id,
            file=file,
        )
    elif filename.endswith(".pdf"):
        result = await PDFImportService.import_quotes(
            db=db,
            rfq_id=rfq.id,
            file=file,
        )
    else:
        raise BadRequestError("Only CSV and PDF files are supported.")

    # Imported quotes must go through the same completeness + normalization pass as
    # every other source, or the dashboard would show them without a landed cost.
    for quote in rfq.quotes:
        if quote.completeness is None or quote.missing_fields is None:
            _apply_completeness(db, rfq, quote)

    if rfq.quotes:
        try:
            ComparisonService.recompute(db, rfq, use_llm=False)
        except Exception:  # noqa: BLE001 - import succeeded; normalization is best-effort
            import logging

            logging.getLogger(__name__).exception(
                "Imported quotes for RFQ %s could not be normalized", rfq.id
            )

    return result


@router.get(
    "/quotes/{quote_id}",
    response_model=QuoteSummary,
)
def get_quote(
    quote_id: int,
    user: CurrentUser,
    db: DBSession,
):
    quote = QuoteService.get_by_id(db=db, quote_id=quote_id)

    InvitationService.get_rfq(db=db, user_id=user.id, rfq_id=quote.rfq_id)

    return build_quote_response(quote)


@router.put(
    "/quotes/{quote_id}",
    response_model=QuoteSummary,
)
def update_quote(
    quote_id: int,
    payload: QuoteUpdate,
    user: CurrentUser,
    db: DBSession,
):
    existing = QuoteService.get_by_id(db=db, quote_id=quote_id)

    rfq = InvitationService.get_rfq(
        db=db, user_id=user.id, rfq_id=existing.rfq_id
    )

    quote = QuoteService.update(
        db=db,
        quote_id=quote_id,
        payload=payload,
    )

    _apply_completeness(db, rfq, quote)

    try:
        ComparisonService.recompute(db, rfq, use_llm=False)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception(
            "Quote %s updated but normalization failed", quote.id
        )

    db.refresh(quote)

    return build_quote_response(quote)


@router.delete(
    "/quotes/{quote_id}",
    status_code=204,
)
def delete_quote(
    quote_id: int,
    user: CurrentUser,
    db: DBSession,
):
    quote = QuoteService.get_by_id(db=db, quote_id=quote_id)

    InvitationService.get_rfq(db=db, user_id=user.id, rfq_id=quote.rfq_id)

    QuoteService.delete(
        db=db,
        quote_id=quote_id,
    )

    return Response(
        status_code=204,
    )
