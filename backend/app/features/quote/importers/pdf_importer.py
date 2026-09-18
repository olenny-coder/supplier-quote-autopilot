from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.ai.agents.quote_extraction import quote_extraction_graph
from app.core.exceptions import BadRequestError, NotFoundError
from app.features.quote.model import SupplierQuote
from app.features.quote.schema import QuoteCreate
from app.features.rfq.model import RFQ


class PDFImportService:
    @staticmethod
    async def import_quotes(
        db: Session,
        rfq_id: int,
        file: UploadFile,
    ) -> dict:
        rfq = db.get(
            RFQ,
            rfq_id,
        )

        if rfq is None:
            raise NotFoundError("RFQ not found")

        if not file.filename.lower().endswith(".pdf"):
            raise BadRequestError("Only PDF files are supported.")

        contents = await file.read()

        result = await quote_extraction_graph.ainvoke(
            {
                "pdf_bytes": contents,
                "extracted_quotes": None,
            }
        )

        extracted_quotes = result[
            "extracted_quotes"
        ]

        imported = 0

        failed = 0

        errors = []

        for extracted in extracted_quotes.quotes:
            try:
                payload = QuoteCreate(**extracted.model_dump())

                quote = SupplierQuote(
                    rfq_id=rfq_id,
                    **payload.model_dump(),
                )

                db.add(quote)

                imported += 1

            except Exception as exc:
                failed += 1

                errors.append(
                    {
                        "supplier": extracted.supplier_name,
                        "error": str(exc),
                    }
                )

        db.commit()

        return {
            "imported": imported,
            "failed": failed,
            "errors": errors,
        }
