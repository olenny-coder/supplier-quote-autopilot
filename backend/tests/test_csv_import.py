from datetime import date

from io import BytesIO

import pytest
from fastapi import UploadFile

from app.features.quote.importers import CSVImportService
from app.features.rfq.model import RFQ


@pytest.mark.asyncio
async def test_import_quotes_success(db_session):
    """
    Verifies that a valid CSV imports successfully.
    """

    rfq = RFQ(
        item_name="Steel Bolt",
        specification="SS304",
        quantity=500,
        delivery_expectation=date(2026, 7, 15),
    )

    db_session.add(rfq)
    db_session.commit()
    db_session.refresh(rfq)

    csv_content = (
        "supplier_name,unit_price,currency,lead_time,payment_terms,remarks\n"
        "ABC Metals,10.50,USD,7,Net 30,High quality\n"
        "XYZ Industries,9.75,USD,10,Advance,Fast delivery\n"
    )

    upload = UploadFile(
        filename="quotes.csv",
        file=BytesIO(csv_content.encode("utf-8")),
    )

    result = await CSVImportService.import_quotes(
        db=db_session,
        rfq_id=rfq.id,
        file=upload,
    )

    assert result["imported"] == 2
    assert result["failed"] == 0
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_import_quotes_partial_failure(db_session):
    """
    Verifies invalid rows are skipped while valid rows import.
    """

    rfq = RFQ(
        item_name="Steel Bolt",
        specification="SS304",
        quantity=500,
        delivery_expectation=date(2026, 9, 22),
    )

    db_session.add(rfq)
    db_session.commit()
    db_session.refresh(rfq)

    csv_content = (
        "supplier_name,unit_price,currency,lead_time,payment_terms,remarks\n"
        "ABC Metals,10.50,USD,7,Net 30,Valid\n"
        "Broken Supplier,,USD,5,Net 30,Missing price\n"
    )

    upload = UploadFile(
        filename="quotes.csv",
        file=BytesIO(csv_content.encode("utf-8")),
    )

    result = await CSVImportService.import_quotes(
        db=db_session,
        rfq_id=rfq.id,
        file=upload,
    )

    assert result["imported"] == 1
    assert result["failed"] == 1
    assert len(result["errors"]) == 1


@pytest.mark.asyncio
async def test_reject_non_csv_file(db_session):
    """
    Verifies non-CSV uploads are rejected.
    """

    rfq = RFQ(
        item_name="Steel Bolt",
        specification="SS304",
        quantity=500,
        delivery_expectation=date(2026, 6, 20),
    )

    db_session.add(rfq)
    db_session.commit()
    db_session.refresh(rfq)

    upload = UploadFile(
        filename="quotes.txt",
        file=BytesIO(b"hello world"),
    )

    with pytest.raises(Exception):
        await CSVImportService.import_quotes(
            db=db_session,
            rfq_id=rfq.id,
            file=upload,
        )
