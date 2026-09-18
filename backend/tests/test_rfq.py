from datetime import date

import pytest

from app.core.exceptions import NotFoundError
from app.features.rfq.schema import RFQCreate
from app.features.rfq.schema import RFQUpdate
from app.features.rfq.service import RFQService


def test_create_rfq(db_session):
    payload = RFQCreate(
        item_name="Steel Bolt M10",
        specification="SS304",
        quantity=500,
        delivery_expectation=date(2026, 7, 15),
        notes="Anti-rust coating",
    )

    rfq = RFQService.create(
        db=db_session,
        payload=payload,
    )

    assert rfq.id is not None
    assert rfq.item_name == "Steel Bolt M10"
    assert rfq.quantity == 500


def test_get_all_rfqs(db_session):
    RFQService.create(
        db=db_session,
        payload=RFQCreate(
            item_name="Bolt",
            specification="SS304",
            quantity=500,
            delivery_expectation=date(2026, 7, 15),
        ),
    )

    RFQService.create(
        db=db_session,
        payload=RFQCreate(
            item_name="Nut",
            specification="SS316",
            quantity=200,
            delivery_expectation=date(2026, 7, 20),
        ),
    )

    rfqs = RFQService.get_all(db_session)

    assert len(rfqs) == 2
    # Most recently created RFQ is returned first
    assert rfqs[0].item_name == "Nut"
    assert rfqs[1].item_name == "Bolt"


def test_get_rfq_by_id(db_session):
    created = RFQService.create(
        db=db_session,
        payload=RFQCreate(
            item_name="Washer",
            specification="Steel",
            quantity=100,
            delivery_expectation=date(2026, 7, 15),
        ),
    )

    fetched = RFQService.get_by_id(
        db=db_session,
        rfq_id=created.id,
    )

    assert fetched.id == created.id
    assert fetched.item_name == "Washer"


def test_update_rfq(db_session):
    created = RFQService.create(
        db=db_session,
        payload=RFQCreate(
            item_name="Bolt",
            specification="SS304",
            quantity=500,
            delivery_expectation=date(2026, 7, 15),
        ),
    )

    updated = RFQService.update(
        db=db_session,
        rfq_id=created.id,
        payload=RFQUpdate(
            quantity=1000,
            notes="Updated quantity",
        ),
    )

    assert updated.quantity == 1000
    assert updated.notes == "Updated quantity"


def test_delete_rfq(db_session):
    created = RFQService.create(
        db=db_session,
        payload=RFQCreate(
            item_name="Bolt",
            specification="SS304",
            quantity=500,
            delivery_expectation=date(2026, 7, 15),
        ),
    )

    RFQService.delete(
        db=db_session,
        rfq_id=created.id,
    )

    with pytest.raises(NotFoundError):
        RFQService.get_by_id(
            db=db_session,
            rfq_id=created.id,
        )


def test_get_rfq_not_found(db_session):
    with pytest.raises(NotFoundError) as exc_info:
        RFQService.get_by_id(db=db_session, rfq_id=999)

    assert exc_info.value.status_code == 404
