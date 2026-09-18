import csv
from decimal import Decimal
from io import StringIO

from fastapi import UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from app.features.quote.model import SupplierQuote
from app.features.quote.schema import QuoteCreate
from app.features.rfq.model import RFQ


class CSVImportService:
    @staticmethod
    async def import_quotes(
        db: Session,
        rfq_id: int,
        file: UploadFile,
    ) -> dict:
        rfq = db.get(RFQ, rfq_id)

        if rfq is None:
            raise NotFoundError("RFQ not found")

        if not file.filename.lower().endswith(".csv"):
            raise BadRequestError("Only CSV files are supported")

        contents = await file.read()

        decoded = contents.decode("utf-8")

        reader = csv.DictReader(StringIO(decoded))

        imported = 0

        failed = 0

        errors: list[dict] = []

        for index, row in enumerate(
            reader,
            start=2,
        ):
            try:
                payload = QuoteCreate(
                    supplier_name=row.get("supplier_name"),
                    unit_price=Decimal(row.get("unit_price", "")),
                    currency=row.get("currency"),
                    lead_time=int(row.get("lead_time", 0)),
                    payment_terms=row.get("payment_terms"),
                    remarks=row.get("remarks"),
                )

                quote = SupplierQuote(
                    rfq_id=rfq_id,
                    **payload.model_dump(),
                )

                db.add(quote)

                imported += 1

            except (
                ValidationError,
                ValueError,
                ArithmeticError,
            ) as exc:
                failed += 1

                errors.append(
                    {
                        "row": index,
                        "error": str(exc),
                    }
                )

        db.commit()

        return {
            "imported": imported,
            "failed": failed,
            "errors": errors,
        }
