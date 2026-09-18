"""Comparison queries."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.comparison.model import Approval
from app.features.comparison.model import Comparison


def latest_for_rfq(db: Session, rfq_id: int) -> Comparison | None:
    stmt = (
        select(Comparison)
        .where(Comparison.rfq_id == rfq_id, Comparison.is_current.is_(True))
        .order_by(Comparison.id.desc())
        .limit(1)
    )

    return db.scalar(stmt)


def get_by_id(db: Session, comparison_id: int) -> Comparison | None:
    return db.get(Comparison, comparison_id)


def list_for_rfq(db: Session, rfq_id: int, limit: int = 50) -> list[Comparison]:
    stmt = (
        select(Comparison)
        .where(Comparison.rfq_id == rfq_id)
        .order_by(Comparison.id.desc())
        .limit(limit)
    )

    return list(db.scalars(stmt).all())


def list_approvals(db: Session, rfq_id: int) -> list[Approval]:
    stmt = (
        select(Approval)
        .where(Approval.rfq_id == rfq_id)
        .order_by(Approval.id.desc())
    )

    return list(db.scalars(stmt).all())


def latest_approval_for_rfq(db: Session, rfq_id: int) -> Approval | None:
    stmt = (
        select(Approval)
        .where(Approval.rfq_id == rfq_id, Approval.decision == "approved")
        .order_by(Approval.id.desc())
        .limit(1)
    )

    return db.scalar(stmt)
