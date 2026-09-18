"""Seed the database with a realistic demo workspace.

    uv run python -m scripts.seed_demo            # create / refresh the demo data
    uv run python -m scripts.seed_demo --reset    # delete the demo buyer first
    uv run python -m scripts.seed_demo --run-scheduler

Why a script rather than fixtures: it drives the *real* services, including the
public-form ingestion pipeline, so the seeded quotes have genuine normalized costs,
completeness assessments, and risk flags. Fixtures that bypass that pipeline would
produce a demo whose numbers do not match what the product actually computes.

The scenario is deliberately imperfect. One supplier submits a complete quote,
one submits a partial one, one quotes in a foreign currency on DDP terms, and one
never responds — so the dashboard shows every state the product handles, and the
comparison has a genuine trade-off in it rather than an obvious winner.

Safe to re-run: everything is keyed off the demo buyer's email address.
"""

import argparse
import asyncio
import sys
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path

# Allow `python -m scripts.seed_demo` from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app import models  # noqa: F401,E402 - registers every table
from app.core.database import Base  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.database import engine  # noqa: E402
from app.core.mixins import utcnow  # noqa: E402
from app.features.auth.model import User  # noqa: E402
from app.features.auth.schema import RegisterRequest  # noqa: E402
from app.features.auth.service import AuthService  # noqa: E402
from app.features.comparison.service import ComparisonService  # noqa: E402
from app.features.followup.model import FollowUp  # noqa: E402
from app.features.followup.service import run_scheduler  # noqa: E402
from app.features.invitation.model import Invitation  # noqa: E402
from app.features.invitation.service import InvitationService  # noqa: E402
from app.features.public_form.schema import PublicQuoteSubmit  # noqa: E402
from app.features.public_form.service import PublicFormService  # noqa: E402
from app.features.rfq.model import RFQ  # noqa: E402
from app.features.rfq.schema import RFQCreate  # noqa: E402
from app.features.rfq.service import RFQService  # noqa: E402
from app.features.supplier.model import Supplier  # noqa: E402
from app.features.supplier.schema import SupplierCreate  # noqa: E402
from app.features.supplier.service import SupplierService  # noqa: E402

DEMO_EMAIL = "buyer@demo-autopilot.example.com"
DEMO_PASSWORD = "demo-password-123"

SUPPLIERS = [
    {
        "name": "Nova Metals S.L.",
        "contact_name": "Ana Ruiz",
        "contact_email": "ana.ruiz@nova-metals.example.com",
        "country": "Spain",
        "city": "Valencia",
        "risk_rating": "low",
        "external_ref": "VEND-1042",
    },
    {
        "name": "Halcyon Fasteners Ltd",
        "contact_name": "Ben Okafor",
        "contact_email": "ben.okafor@halcyon.example.com",
        "country": "Vietnam",
        "city": "Hai Phong",
        "risk_rating": "medium",
        "external_ref": "VEND-2088",
    },
    {
        "name": "Ironbridge Supply Sp. z o.o.",
        "contact_name": "Cara Lindqvist",
        "contact_email": "cara@ironbridge.example.com",
        "country": "Poland",
        "city": "Wroclaw",
        "risk_rating": "high",
        "external_ref": "VEND-3311",
    },
    {
        "name": "Meridian Components GmbH",
        "contact_name": "DieterSchmidt",
        "contact_email": "d.schmidt@meridian.example.com",
        "country": "Germany",
        "city": "Stuttgart",
        "risk_rating": "low",
        "external_ref": "VEND-1177",
    },
]

#: keyed by supplier name -> the submission that supplier makes. Ironbridge is
#: absent on purpose: a non-responder is what the follow-up engine exists for.
SUBMISSIONS = {
    "Nova Metals S.L.": PublicQuoteSubmit(
        supplier_name="Nova Metals S.L.",
        contact_email="ana.ruiz@nova-metals.example.com",
        currency="USD",
        unit_price="2.48",
        unit="pcs",
        lead_time="3 weeks",
        moq="500",
        payment_terms="Net 30",
        incoterms="FOB Valencia",
        validity_date="2026-12-31",
        warranty_months="12",
        shipping_cost="180",
        notes=(
            "Zinc plating included. Price holds for orders above 500 pcs. "
            "Smaller runs are possible but carry a setup charge we would need to quote."
        ),
    ),
    "Halcyon Fasteners Ltd": PublicQuoteSubmit(
        supplier_name="Halcyon Fasteners Ltd",
        contact_email="ben.okafor@halcyon.example.com",
        currency="USD",
        unit_price="2.19",
        unit="pcs",
        lead_time="8 weeks",
        # Deliberately incomplete: no MOQ, no payment terms, no validity date.
        incoterms="FOB Hai Phong",
        notes=(
            "Quoted ex-stock from the Hai Phong plant. Our finance team is still "
            "confirming the payment terms for new accounts."
        ),
    ),
    "Meridian Components GmbH": PublicQuoteSubmit(
        supplier_name="Meridian Components GmbH",
        contact_email="d.schmidt@meridian.example.com",
        currency="EUR",
        unit_price="2.85",
        unit="pcs",
        lead_time="18 days",
        moq="250",
        payment_terms="Net 45",
        incoterms="DDP Hamburg",
        validity_date="2026-11-15",
        warranty_months="24",
        notes=(
            "Delivered duty paid to your Hamburg warehouse. Fastest option; the "
            "unit price reflects the delivered terms."
        ),
    ),
}


def reset(db) -> None:
    """Remove the demo buyer and everything cascading from it."""

    user = AuthService.get_by_email(db, DEMO_EMAIL)

    if user is None:
        print("  (nothing to reset)")
        return

    db.delete(user)
    db.commit()

    print(f"  removed demo buyer {DEMO_EMAIL} and all related data")


def create_buyer(db) -> User:
    user = AuthService.get_by_email(db, DEMO_EMAIL)

    if user is not None:
        print(f"  reusing buyer {DEMO_EMAIL}")
        return user

    user = AuthService.register(
        db=db,
        payload=RegisterRequest(
            email=DEMO_EMAIL,
            password=DEMO_PASSWORD,
            full_name="Dana Whitfield",
            company_name="Acme Industrial Supply",
            contact_email="procurement@acme-industrial.example.com",
            contact_phone="+1 555 0142",
        ),
    )

    print(f"  created buyer {DEMO_EMAIL} / {DEMO_PASSWORD}")

    return user


def create_suppliers(db, user: User) -> list[Supplier]:
    created: list[Supplier] = []

    for spec in SUPPLIERS:
        existing = SupplierService.get_by_email(db, user.id, spec["contact_email"])

        if existing is not None:
            created.append(existing)
            continue

        created.append(
            SupplierService.create(
                db=db,
                user_id=user.id,
                payload=SupplierCreate(**spec),
            )
        )

    print(f"  {len(created)} suppliers in the directory")

    return created


def create_rfq(db, user: User) -> RFQ:
    """Create the demo RFQ unless one already exists for this buyer."""

    existing = db.scalar(
        select(RFQ).where(
            RFQ.user_id == user.id,
            RFQ.item_name == "Hex Bolt M10x60 SS304",
        )
    )

    if existing is not None:
        print(f"  reusing RFQ {existing.rfq_number}")
        return existing

    rfq = RFQService.create(
        db=db,
        user_id=user.id,
        payload=RFQCreate(
            item_name="Hex Bolt M10x60 SS304",
            specification="DIN 933, A2-70 stainless, zinc-plated, full thread",
            quantity=5000,
            unit="pcs",
            currency="USD",
            incoterms="FOB",
            delivery_expectation=date.today() + timedelta(days=75),
            deadline=utcnow() + timedelta(days=10),
            category="Fasteners",
            notes=(
                "Anti-rust coating required. Batch certificates (EN 10204 3.1) must "
                "accompany each delivery. Annual volume is roughly 60,000 pcs."
            ),
            buyer_company=user.company_name,
            required_fields=[
                "unit_price",
                "currency",
                "lead_time",
                "moq",
                "payment_terms",
                "incoterms",
                "validity_date",
            ],
        ),
    )

    print(f"  created RFQ {rfq.rfq_number} ({rfq.quantity:,} {rfq.unit})")

    return rfq


def invite(db, user: User, rfq: RFQ, suppliers: list[Supplier]) -> list[Invitation]:
    invitations = InvitationService.bulk_create(
        db=db,
        user_id=user.id,
        rfq_id=rfq.id,
        supplier_ids=[supplier.id for supplier in suppliers],
        # Console/logged delivery in dev; the emails are still recorded in the log.
        send_now=True,
    )

    print(f"  {len(invitations)} tokenized form links issued")

    return invitations


def submit_quotes(db, invitations: list[Invitation]) -> int:
    """Drive the real public-form ingestion path for each responding supplier."""

    submitted = 0

    for invitation in invitations:
        payload = SUBMISSIONS.get(invitation.supplier.name)

        if payload is None:
            print(f"  {invitation.supplier.name}: no response (intentional)")
            continue

        # `load_invitation` records the view, exactly as a real visit does.
        PublicFormService.load_invitation(db=db, token=invitation.token)

        confirmation = asyncio.run(
            PublicFormService.submit(
                db=db,
                invitation=invitation,
                rfq=invitation.rfq,
                payload=payload,
            )
        )

        print(
            f"  {invitation.supplier.name}: submitted ({confirmation.completeness}) "
            f"reference {confirmation.reference_number}"
        )

        submitted += 1

    return submitted


def backdate_sends(db, invitations: list[Invitation], hours: int = 100) -> None:
    """Age the invitations so the reminder intervals have elapsed.

    Without this the demo would show nothing to chase, because the default first
    interval is 72 hours and everything was just sent.
    """

    moment = datetime.now(UTC) - timedelta(hours=hours)

    for invitation in invitations:
        invitation.sent_at = moment
        invitation.last_sent_at = moment

    db.commit()

    print(f"  sends backdated by {hours}h so reminders are due")


def report(db, user: User, rfq: RFQ) -> None:
    from app.features.comparison.repository import latest_for_rfq
    from app.features.rfq.service import RFQService as _RFQService

    counters = _RFQService.counts(db, [rfq.id]).get(rfq.id, {})

    comparison = latest_for_rfq(db, rfq.id)

    drafts = db.scalars(
        select(FollowUp).where(FollowUp.rfq_id == rfq.id, FollowUp.status == "draft")
    ).all()

    print()
    print("  " + "-" * 66)
    print(f"  RFQ            {rfq.rfq_number} — {rfq.item_name}")
    print(f"  Invited        {counters.get('invitation_count', 0)}")
    print(f"  Responded      {counters.get('responded_count', 0)}")
    print(f"  Incomplete     {counters.get('incomplete_count', 0)}")
    print(f"  No response    {counters.get('pending_count', 0)}")
    print(f"  Quotes         {counters.get('quote_count', 0)}")

    if comparison is not None:
        winner = None

        for result in comparison.results or []:
            if result.get("quote_id") == comparison.recommended_quote_id:
                winner = result
                break

        if winner:
            print(
                f"  Recommended    {winner.get('supplier_name')} "
                f"(score {winner.get('composite_score')}, "
                f"{winner.get('total_base')} {comparison.base_currency} landed)"
            )

        print(f"  Conclusive     {bool(comparison.is_conclusive)}")

    print(f"  Drafts waiting {len(drafts)}")
    print("  " + "-" * 66)
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="delete the demo buyer and all related data first",
    )
    parser.add_argument(
        "--run-scheduler",
        action="store_true",
        help="run one follow-up sweep after seeding, so drafts appear immediately",
    )
    parser.add_argument(
        "--skip-compare",
        action="store_true",
        help="do not compute a comparison (submissions still normalize their quotes)",
    )
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        print()
        print("Seeding Supplier Quote Autopilot demo data")
        print("=" * 70)

        if args.reset:
            reset(db)

        user = create_buyer(db)
        suppliers = create_suppliers(db, user)
        rfq = create_rfq(db, user)

        # Move the RFQ deadline several days out so the demo does not expire.
        rfq.deadline = datetime.now(UTC) + timedelta(days=10)
        db.commit()

        invitations = invite(db, user, rfq, suppliers)

        print()
        print("Public form links (send these to the suppliers):")
        for invitation in invitations:
            print(
                f"  {invitation.supplier.name:<34} "
                f"{InvitationService.to_response(invitation).form_link}"
            )
        print()

        submit_quotes(db, invitations)

        backdate_sends(db, invitations)

        if args.run_scheduler:
            print()
            print("Running one follow-up sweep...")
            summary = run_scheduler(db)
            print(
                f"  scanned={summary.scanned} drafted={summary.drafted} "
                f"sent={summary.sent} queued={summary.queued_for_approval} "
                f"skipped={summary.skipped} llm_calls={summary.llm_calls}"
            )

        if not args.skip_compare and rfq.quotes:
            print()
            print("Computing the comparison...")
            comparison = ComparisonService.recompute(db, rfq, use_llm=False)
            print(
                f"  recommended quote id {comparison.recommended_quote_id}, "
                f"backup {comparison.backup_quote_id}, "
                f"{len(comparison.results or [])} quotes scored"
            )

        db.refresh(rfq)
        report(db, user, rfq)

        print("Demo data ready.")
        print()
        print("  Buyer dashboard  ->  sign in as " + DEMO_EMAIL)
        print("  Password         ->  " + DEMO_PASSWORD)
        print("  Supplier form    ->  one of the links printed above")
        print()

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
