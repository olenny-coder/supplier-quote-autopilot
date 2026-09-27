"""Supplier service — buyer-scoped CRUD."""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.core.exceptions import NotFoundError
from app.features.invitation.model import Invitation
from app.features.quote.model import SupplierQuote
from app.features.supplier.model import Supplier
from app.features.supplier.schema import SupplierCreate
from app.features.supplier.schema import SupplierImportResponse
from app.features.supplier.schema import SupplierImportRowError
from app.features.supplier.schema import SupplierResponse
from app.features.supplier.schema import SupplierUpdate


class SupplierService:
    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def get_all(db: Session, user_id: int) -> list[Supplier]:
        stmt = (
            select(Supplier)
            .where(Supplier.user_id == user_id)
            .order_by(Supplier.name.asc())
        )

        return list(db.scalars(stmt).all())

    @staticmethod
    def get_by_id(db: Session, user_id: int, supplier_id: int) -> Supplier:
        """Always scoped by ``user_id`` — a supplier id from another tenant 404s."""

        supplier = db.get(Supplier, supplier_id)

        if supplier is None or supplier.user_id != user_id:
            raise NotFoundError("Supplier not found")

        return supplier

    @staticmethod
    def get_by_email(db: Session, user_id: int, email: str) -> Supplier | None:
        stmt = select(Supplier).where(
            Supplier.user_id == user_id,
            Supplier.contact_email == SupplierService.normalize_email(email),
        )

        return db.scalar(stmt)

    @staticmethod
    def create(
        db: Session,
        user_id: int,
        payload: SupplierCreate,
        *,
        reuse_existing: bool = False,
    ) -> Supplier:
        email = SupplierService.normalize_email(str(payload.contact_email))

        if reuse_existing:
            existing = SupplierService.get_by_email(db, user_id, email)

            if existing is not None:
                return existing

        if SupplierService.get_by_email(db, user_id, email) is not None:
            raise ConflictError(
                f"A supplier with the email {email} already exists in your directory."
            )

        supplier = Supplier(
            user_id=user_id,
            name=payload.name.strip(),
            contact_name=(payload.contact_name or "").strip() or None,
            contact_email=email,
            phone=payload.phone,
            website=payload.website,
            country=payload.country,
            city=payload.city,
            notes=payload.notes,
            risk_rating=payload.risk_rating,
            external_ref=payload.external_ref,
        )

        db.add(supplier)
        db.commit()
        db.refresh(supplier)

        return supplier

    # ------------------------------------------------------------------ import
    @staticmethod
    def import_many(
        db: Session,
        user_id: int,
        payloads,
        *,
        on_duplicate: str = "skip",
        rows: list[int] | None = None,
    ) -> SupplierImportResponse:
        """Add many suppliers, reporting per row rather than failing the batch.

        Deliberately not all-or-nothing. A directory export of 300 contractors with
        four malformed addresses should import 296 and name the four — refusing the
        whole file over one typo is how a bulk upload becomes useless, and it gives
        the buyer no way to find the typo either.

        ``on_duplicate="skip"`` is the default so that re-importing an updated
        spreadsheet does not overwrite the notes, risk rating and reference code the
        buyer curated by hand. It is the normal case, not the exception.

        ``rows`` is parallel to ``payloads`` and carries the source row number, so an
        error points at the line in the buyer's spreadsheet rather than at an index
        in a list they cannot see.
        """

        errors: list[SupplierImportRowError] = []
        imported: list[Supplier] = []

        created = 0
        updated = 0
        skipped = 0

        for index, payload in enumerate(payloads):
            row = rows[index] if rows and index < len(rows) else index + 1

            email = SupplierService.normalize_email(str(payload.contact_email))

            existing = SupplierService.get_by_email(db, user_id, email)

            try:
                if existing is None:
                    supplier = SupplierService.create(db, user_id, payload)
                    created += 1
                elif on_duplicate == "update":
                    supplier = SupplierService.update(
                        db,
                        user_id,
                        existing.id,
                        SupplierUpdate(**payload.model_dump()),
                    )
                    updated += 1
                else:
                    skipped += 1
                    imported.append(existing)
                    continue
            except (ConflictError, ValueError) as exc:
                errors.append(
                    SupplierImportRowError(
                        row=row,
                        email=email,
                        name=payload.name,
                        reason=str(exc)[:300],
                    )
                )
                continue

            imported.append(supplier)

        total = created + updated + skipped + len(errors)

        return SupplierImportResponse(
            created=created,
            updated=updated,
            skipped=skipped,
            failed=len(errors),
            total=total,
            errors=errors,
            imported=[
                SupplierResponse.model_validate(supplier) for supplier in imported
            ],
            message=SupplierService.import_message(created, updated, skipped, len(errors)),
        )

    @staticmethod
    def import_message(created: int, updated: int, skipped: int, failed: int) -> str:
        """One sentence a buyer can act on, with the counts that matter first."""

        parts: list[str] = []

        if created:
            parts.append(f"{created} added")
        if updated:
            parts.append(f"{updated} updated")
        if skipped:
            parts.append(f"{skipped} already in your directory")
        if failed:
            parts.append(f"{failed} could not be imported")

        summary = ", ".join(parts) if parts else "Nothing to import"

        if failed and not created and not updated:
            return f"{summary}. Check the row numbers below."

        return summary + "."

    @staticmethod
    def update(
        db: Session,
        user_id: int,
        supplier_id: int,
        payload: SupplierUpdate,
    ) -> Supplier:
        supplier = SupplierService.get_by_id(db, user_id, supplier_id)

        data = payload.model_dump(exclude_unset=True)

        if data.get("contact_email"):
            data["contact_email"] = SupplierService.normalize_email(
                str(data["contact_email"])
            )

            clash = SupplierService.get_by_email(db, user_id, data["contact_email"])

            if clash is not None and clash.id != supplier.id:
                raise ConflictError(
                    f"A supplier with the email {data['contact_email']} already exists."
                )

        for key, value in data.items():
            setattr(supplier, key, value)

        db.commit()
        db.refresh(supplier)

        return supplier

    @staticmethod
    def delete(db: Session, user_id: int, supplier_id: int) -> None:
        supplier = SupplierService.get_by_id(db, user_id, supplier_id)

        db.delete(supplier)
        db.commit()

    # ------------------------------------------------------------------ stats
    @staticmethod
    def stats(db: Session, user_id: int, supplier_id: int) -> dict:
        """Activity summary used by the supplier list and the dashboard."""

        invitations_total = db.scalar(
            select(func.count(Invitation.id))
            .join(Supplier, Supplier.id == Invitation.supplier_id)
            .where(Supplier.user_id == user_id, Invitation.supplier_id == supplier_id)
        ) or 0

        responded = db.scalar(
            select(func.count(Invitation.id))
            .join(Supplier, Supplier.id == Invitation.supplier_id)
            .where(
                Supplier.user_id == user_id,
                Invitation.supplier_id == supplier_id,
                Invitation.responded_at.is_not(None),
            )
        ) or 0

        quotes_total = db.scalar(
            select(func.count(SupplierQuote.id)).where(
                SupplierQuote.supplier_id == supplier_id
            )
        ) or 0

        pairs = db.execute(
            select(Invitation.sent_at, Invitation.responded_at)
            .join(Supplier, Supplier.id == Invitation.supplier_id)
            .where(
                Supplier.user_id == user_id,
                Invitation.supplier_id == supplier_id,
                Invitation.sent_at.is_not(None),
                Invitation.responded_at.is_not(None),
            )
        ).all()

        hours = [
            (responded_at - sent_at).total_seconds() / 3600.0
            for sent_at, responded_at in pairs
            if isinstance(sent_at, datetime) and isinstance(responded_at, datetime)
        ]

        return {
            "invitations_total": invitations_total,
            "invitations_responded": responded,
            "quotes_total": quotes_total,
            "average_response_hours": round(sum(hours) / len(hours), 1) if hours else None,
        }
