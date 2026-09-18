from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.features.rfq.model import RFQ
from app.features.rfq.schema import RFQCreate
from app.features.rfq.schema import RFQUpdate


class RFQService:
    @staticmethod
    def get_all(db: Session) -> list[RFQ]:
        stmt = select(RFQ).order_by(RFQ.id.desc())
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_by_id(
        db: Session,
        rfq_id: int,
    ) -> RFQ:
        rfq = db.get(RFQ, rfq_id)

        if rfq is None:
            raise NotFoundError("RFQ not found")

        return rfq

    @staticmethod
    def create(
        db: Session,
        payload: RFQCreate,
    ) -> RFQ:
        rfq = RFQ(
            **payload.model_dump(),
        )

        db.add(rfq)

        db.commit()

        db.refresh(rfq)

        return rfq

    @staticmethod
    def update(
        db: Session,
        rfq_id: int,
        payload: RFQUpdate,
    ) -> RFQ:
        rfq = RFQService.get_by_id(
            db=db,
            rfq_id=rfq_id,
        )

        update_data = payload.model_dump(
            exclude_unset=True,
        )

        for key, value in update_data.items():
            setattr(
                rfq,
                key,
                value,
            )

        db.commit()

        db.refresh(rfq)

        return rfq

    @staticmethod
    def delete(
        db: Session,
        rfq_id: int,
    ) -> None:
        rfq = RFQService.get_by_id(
            db=db,
            rfq_id=rfq_id,
        )

        db.delete(rfq)

        db.commit()
