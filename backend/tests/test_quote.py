from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.exceptions import NotFoundError
from app.features.quote.model import SupplierQuote
from app.features.quote.schema import QuoteCreate
from app.features.quote.schema import QuoteUpdate
from app.features.quote.service import QuoteService
from app.features.rfq.model import RFQ
from app.features.rfq.service import RFQService


def create_test_rfq(db_session):
    rfq = RFQ(
        item_name="Steel Bolt",
        specification="SS304",
        quantity=500,
        delivery_expectation=date(2026, 7, 15),
        notes="Test RFQ",
    )

    db_session.add(rfq)
    db_session.commit()
    db_session.refresh(rfq)

    return rfq


def test_create_quote(db_session):
    rfq = create_test_rfq(db_session)

    payload = QuoteCreate(
        supplier_name="ABC Metals",
        unit_price=Decimal("10.50"),
        currency="USD",
        lead_time=7,
        payment_terms="Net 30",
        remarks="High quality",
    )

    quote = QuoteService.create(
        db=db_session,
        rfq_id=rfq.id,
        payload=payload,
    )

    assert quote.id is not None
    assert quote.rfq_id == rfq.id
    assert quote.supplier_name == "ABC Metals"
    assert quote.unit_price == Decimal("10.50")


def test_get_all_quotes_for_rfq(db_session):
    rfq = create_test_rfq(db_session)

    QuoteService.create(
        db=db_session,
        rfq_id=rfq.id,
        payload=QuoteCreate(
            supplier_name="Supplier A",
            unit_price=Decimal("12.00"),
            currency="USD",
            lead_time=5,
        ),
    )

    QuoteService.create(
        db=db_session,
        rfq_id=rfq.id,
        payload=QuoteCreate(
            supplier_name="Supplier B",
            unit_price=Decimal("10.00"),
            currency="USD",
            lead_time=7,
        ),
    )

    quotes = QuoteService.get_all_for_rfq(
        db=db_session,
        rfq_id=rfq.id,
    )

    assert len(quotes) == 2

    # Sorted by lowest unit price
    assert quotes[0].supplier_name == "Supplier B"


def test_update_quote(db_session):
    rfq = create_test_rfq(db_session)

    quote = QuoteService.create(
        db=db_session,
        rfq_id=rfq.id,
        payload=QuoteCreate(
            supplier_name="ABC",
            unit_price=Decimal("10.00"),
            currency="USD",
            lead_time=5,
        ),
    )

    updated = QuoteService.update(
        db=db_session,
        quote_id=quote.id,
        payload=QuoteUpdate(
            unit_price=Decimal("9.50"),
            lead_time=3,
        ),
    )

    assert updated.unit_price == Decimal("9.50")
    assert updated.lead_time == 3


def test_delete_quote(db_session):
    rfq = create_test_rfq(db_session)

    quote = QuoteService.create(
        db=db_session,
        rfq_id=rfq.id,
        payload=QuoteCreate(
            supplier_name="ABC",
            unit_price=Decimal("10.00"),
            currency="USD",
            lead_time=5,
        ),
    )

    QuoteService.delete(
        db=db_session,
        quote_id=quote.id,
    )

    with pytest.raises(NotFoundError):
        QuoteService.get_by_id(
            db=db_session,
            quote_id=quote.id,
        )


def test_get_best_quote(db_session):
    rfq = create_test_rfq(db_session)

    QuoteService.create(
        db=db_session,
        rfq_id=rfq.id,
        payload=QuoteCreate(
            supplier_name="Supplier A",
            unit_price=Decimal("12.00"),
            currency="USD",
            lead_time=5,
        ),
    )

    QuoteService.create(
        db=db_session,
        rfq_id=rfq.id,
        payload=QuoteCreate(
            supplier_name="Supplier B",
            unit_price=Decimal("9.50"),
            currency="USD",
            lead_time=8,
        ),
    )

    best = QuoteService.get_best_quote(
        db=db_session,
        rfq_id=rfq.id,
    )

    assert best is not None
    assert best.supplier_name == "Supplier B"
    assert best.unit_price == Decimal("9.50")


def test_get_best_quote_empty(db_session):
    rfq = create_test_rfq(db_session)

    best = QuoteService.get_best_quote(db=db_session, rfq_id=rfq.id)

    assert best is None


def test_create_quote_rfq_not_found(db_session):
    with pytest.raises(NotFoundError) as exc_info:
        QuoteService.create(
            db=db_session,
            rfq_id=999,
            payload=QuoteCreate(
                supplier_name="ABC",
                unit_price=Decimal("10.00"),
                currency="USD",
                lead_time=5,
            ),
        )

    assert exc_info.value.status_code == 404


def test_get_quotes_rfq_not_found(db_session):
    with pytest.raises(NotFoundError) as exc_info:
        QuoteService.get_all_for_rfq(db=db_session, rfq_id=999)

    assert exc_info.value.status_code == 404


def test_delete_rfq_cascades_to_quotes(db_session):
    rfq = create_test_rfq(db_session)
    rfq_id = rfq.id

    QuoteService.create(
        db=db_session,
        rfq_id=rfq_id,
        payload=QuoteCreate(
            supplier_name="ABC",
            unit_price=Decimal("10.00"),
            currency="USD",
            lead_time=5,
        ),
    )

    RFQService.delete(db=db_session, rfq_id=rfq_id)

    remaining = db_session.scalars(
        select(SupplierQuote).where(SupplierQuote.rfq_id == rfq_id)
    ).all()

    assert remaining == []
