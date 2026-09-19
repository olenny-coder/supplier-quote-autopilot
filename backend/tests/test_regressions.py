"""Regression tests for bugs found while building the app.

Each test here exists because a specific defect was observed, not because a line of
code needed covering. The docstrings record what actually went wrong, so a future
refactor that reintroduces the bug fails loudly with the explanation attached.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta

from sqlalchemy import select

from app.core.mixins import utcnow
from app.features.auth.schema import RegisterRequest
from app.features.auth.service import AuthService
from app.features.comparison.service import ComparisonService
from app.features.followup.service import run_scheduler
from app.features.invitation.model import Invitation
from app.features.invitation.service import InvitationService
from app.features.public_form.schema import PublicQuoteSubmit
from app.features.public_form.service import PublicFormService
from app.features.rfq.schema import RFQCreate
from app.features.rfq.service import RFQService
from app.features.supplier.schema import SupplierCreate
from app.features.supplier.service import SupplierService


def _seed_rfq_with_suppliers(db, count: int = 3):
    """A buyer, an RFQ, and ``count`` invited suppliers."""

    user = AuthService.register(
        db=db,
        payload=RegisterRequest(
            email="regression@acme.example.com",
            password="correct-horse-battery",
            company_name="Acme",
            full_name="Dana Buyer",
        ),
    )

    rfq = RFQService.create(
        db=db,
        user_id=user.id,
        payload=RFQCreate(
            item_name="Bolt",
            specification="SS304",
            quantity=1000,
            delivery_expectation=date.today() + timedelta(days=60),
            deadline=utcnow() + timedelta(days=10),
            currency="USD",
            incoterms="FOB",
            # A goods RFQ, explicitly. The application default is `service`, and these
            # regressions are about quotes that carry Incoterms and an MOQ.
            procurement_type="goods",
            buyer_company="Acme",
        ),
    )

    suppliers = [
        SupplierService.create(
            db=db,
            user_id=user.id,
            payload=SupplierCreate(
                name=f"Supplier {index}",
                contact_email=f"sales{index}@supplier{index}.example.com",
                contact_name=f"Contact {index}",
            ),
        )
        for index in range(count)
    ]

    invitations = InvitationService.bulk_create(
        db=db,
        user_id=user.id,
        rfq_id=rfq.id,
        supplier_ids=[supplier.id for supplier in suppliers],
        send_now=False,
    )

    return user, rfq, suppliers, invitations


def test_comparison_sees_every_quote_created_in_the_same_session(db_session):
    """A scoring run must not miss quotes inserted earlier in the same session.

    The defect: the comparison read ``rfq.quotes``, a relationship collection
    cached on the instance. With ``expire_on_commit=False`` the cached list was
    never refreshed after an insert, so a run inside the same session scored only
    the quotes it already knew about. In the demo seed that produced a comparison
    ranking one quote out of three, and a backup recommendation of ``None``.
    """

    _, rfq, _, invitations = _seed_rfq_with_suppliers(db_session, count=3)

    for index, invitation in enumerate(invitations):
        PublicFormService.load_invitation(db=db_session, token=invitation.token)

        import asyncio

        asyncio.run(
            PublicFormService.submit(
                db=db_session,
                invitation=invitation,
                rfq=rfq,
                payload=PublicQuoteSubmit(
                    supplier_name=f"Supplier {index}",
                    contact_email=f"sales{index}@supplier{index}.example.com",
                    currency="USD",
                    unit_price=str(10 + index),
                    unit="pcs",
                    lead_time="3 weeks",
                    moq="100",
                    payment_terms="Net 30",
                    incoterms="FOB",
                    validity_date=(date.today() + timedelta(days=120)).isoformat(),
                ),
            )
        )

    comparison = ComparisonService.recompute(db_session, rfq, use_llm=False)

    assert len(comparison.results) == 3, (
        "all three quotes must be scored; a shorter list means a quote was "
        "silently dropped from the comparison"
    )
    assert comparison.recommended_quote_id is not None
    assert comparison.backup_quote_id is not None

    ranked = [r for r in comparison.results if r.get("rank") is not None]
    assert len(ranked) == 3
    assert {r["rank"] for r in ranked} == {1, 2, 3}


def test_scheduler_chases_an_incomplete_quote_created_in_the_same_session(db_session):
    """An incomplete submission must trigger a targeted follow-up immediately.

    The defect: the snapshot read ``invitation.quote``. When the quote had been
    created moments earlier in the same session, that relationship was still cached
    as ``None``, so the snapshot reported "no answer" and no missing fields. The
    policy then saw an invitation marked incomplete with nothing listed as missing
    and skipped it — the supplier who most needed chasing got nothing.
    """

    _, rfq, _, invitations = _seed_rfq_with_suppliers(db_session, count=2)

    target = invitations[0]

    PublicFormService.load_invitation(db=db_session, token=target.token)

    import asyncio

    confirmation = asyncio.run(
        PublicFormService.submit(
            db=db_session,
            invitation=target,
            rfq=rfq,
            payload=PublicQuoteSubmit(
                supplier_name="Supplier 0",
                currency="USD",
                unit_price="4.20",
                unit="pcs",
                lead_time="30 days",
                # moq, payment_terms, incoterms and validity_date deliberately absent
            ),
        )
    )

    assert confirmation.completeness == "incomplete"

    # Make the interval elapse.
    for invitation in db_session.scalars(select(Invitation)).all():
        invitation.sent_at = datetime.now(UTC) - timedelta(hours=100)
        invitation.last_sent_at = invitation.sent_at

    db_session.commit()

    summary = run_scheduler(db_session)

    kinds = {action.get("kind") for action in summary.actions}

    assert "incomplete_quote" in kinds, (
        "the supplier who left required fields blank must get a targeted "
        "follow-up, not silence"
    )

    action = next(
        action for action in summary.actions if action.get("kind") == "incomplete_quote"
    )

    assert action["requested"], "the follow-up must name the outstanding fields"
    # moq, payment_terms, incoterms and validity_date were left blank.
    assert len(action["requested"]) == 4


def test_incomplete_responses_are_counted_as_responded_and_as_incomplete(db_session):
    """``responded_count`` and ``incomplete_count`` answer different questions.

    The defect: the counters bucketed each invitation into exactly one of
    responded / incomplete / pending, so a supplier who sent a partial quote made
    "Incomplete" read zero on the dashboard. Incomplete is a *subset* of responded:
    they did reply, and they still owe something.
    """

    _, rfq, _, invitations = _seed_rfq_with_suppliers(db_session, count=3)

    import asyncio

    # One complete quote.
    PublicFormService.load_invitation(db=db_session, token=invitations[0].token)
    asyncio.run(
        PublicFormService.submit(
            db=db_session,
            invitation=invitations[0],
            rfq=rfq,
            payload=PublicQuoteSubmit(
                supplier_name="Supplier 0",
                currency="USD",
                unit_price="5.00",
                unit="pcs",
                lead_time="2 weeks",
                moq="100",
                payment_terms="Net 30",
                incoterms="FOB",
                validity_date=(date.today() + timedelta(days=90)).isoformat(),
            ),
        )
    )

    # One incomplete quote.
    PublicFormService.load_invitation(db=db_session, token=invitations[1].token)
    asyncio.run(
        PublicFormService.submit(
            db=db_session,
            invitation=invitations[1],
            rfq=rfq,
            payload=PublicQuoteSubmit(
                supplier_name="Supplier 1",
                currency="USD",
                unit_price="4.50",
                unit="pcs",
                lead_time="30 days",
            ),
        )
    )

    # One supplier never responds.

    counters = RFQService.counts(db_session, [rfq.id])[rfq.id]

    assert counters["invitation_count"] == 3
    assert counters["responded_count"] == 2
    assert counters["incomplete_count"] == 1, (
        "an incomplete quote is a response AND an outstanding item"
    )
    assert counters["pending_count"] == 1
    assert counters["quote_count"] == 2
    assert counters["complete_priced_quotes"] == 1


def test_expired_invitations_are_neither_pending_nor_responded(db_session):
    """An expired invitation must leave neither bucket, or the counts never settle."""

    _, rfq, _, invitations = _seed_rfq_with_suppliers(db_session, count=2)

    for invitation in invitations:
        invitation.expires_at = datetime.now(UTC) - timedelta(days=1)

    db_session.commit()

    run_scheduler(db_session)

    db_session.refresh(rfq)

    counters = RFQService.counts(db_session, [rfq.id])[rfq.id]

    assert counters["pending_count"] == 0
    assert counters["responded_count"] == 0
    assert counters["incomplete_count"] == 0
    assert counters["invitation_count"] == 2, "expired invitations still exist"

    statuses = {invitation.status for invitation in db_session.scalars(select(Invitation)).all()}
    assert statuses == {"expired"}


def test_a_complete_quote_created_later_stops_the_chase(db_session):
    """The scheduler must not chase a supplier whose quote arrived after a draft.

    Guards against a stale-snapshot regression in the opposite direction: a draft
    queued before the submission must not be followed by more chasing.
    """

    _, rfq, _, invitations = _seed_rfq_with_suppliers(db_session, count=1)

    target = invitations[0]
    target.sent_at = datetime.now(UTC) - timedelta(hours=100)
    target.last_sent_at = target.sent_at
    db_session.commit()

    first = run_scheduler(db_session)
    assert first.drafted == 1

    import asyncio

    PublicFormService.load_invitation(db=db_session, token=target.token)
    asyncio.run(
        PublicFormService.submit(
            db=db_session,
            invitation=target,
            rfq=rfq,
            payload=PublicQuoteSubmit(
                supplier_name="Supplier 0",
                currency="USD",
                unit_price="5.00",
                unit="pcs",
                lead_time="2 weeks",
                moq="100",
                payment_terms="Net 30",
                incoterms="FOB",
                validity_date=(date.today() + timedelta(days=90)).isoformat(),
            ),
        )
    )

    second = run_scheduler(db_session)

    assert second.drafted == 0, "a complete quote ends the chase"
    assert second.scanned == 0, "a submitted invitation is no longer open"
