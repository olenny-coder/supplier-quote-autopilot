"""Follow-up policy — who to chase, what to ask for, and the message that goes out.

The policy is a pure function of an :class:`InvitationSnapshot` and an injected
clock, so every case is a plain deterministic test: ``now`` is always passed
explicitly and no test sleeps.

The rule that matters most, and the one these tests are built around, is the
escalation ordering: **never chase a supplier who is waiting on the buyer.**
A reminder cannot produce a value the supplier has already said they cannot give,
and sending one hides the fact that the buyer is the blocker. The rest of the
ordering (terminal states, deadline, incomplete quote, cap, interval) is
protected because each of those failures is a real one: nagging a supplier who
already declined, or reminding after the window closed.
"""

from datetime import datetime
from datetime import timedelta

import pytest

from agents.followup import FollowUpDecision
from agents.followup import InvitationSnapshot
from agents.followup import contains_forbidden_claim
from agents.followup import decide
from agents.followup import draft_followup
from agents.followup import next_reminder_due_at

#: Every test works relative to this instant; nothing reads the wall clock.
NOW = datetime(2026, 6, 1, 9, 0, 0)

INTERVALS = [72, 168]
MAX_FOLLOWUPS = 3
MAX_INCOMPLETE_REMINDERS = 2

FORM_LINK = "https://forms.example/quote/7/tok-123"


def _snapshot(**overrides) -> InvitationSnapshot:
    fields = {
        "invitation_id": 1,
        "rfq_id": 7,
        "supplier_name": "Acme Bearings",
        "contact_name": "Priya Sharma",
        "contact_email": "priya@acme.example",
        "rfq_number": "RFQ-2026-001",
        "item_name": "Bearing 6204",
        "rfq_quantity": 1000,
        "buyer_company": "Northwind Industrial",
        "buyer_contact_name": "Sam Okoye",
        "form_link": FORM_LINK,
        "sent_at": NOW,
    }
    fields.update(overrides)
    return InvitationSnapshot(**fields)


def _decide(snapshot: InvitationSnapshot, *, now: datetime = NOW, **overrides) -> FollowUpDecision:
    kwargs = {
        "intervals_hours": INTERVALS,
        "max_followups": MAX_FOLLOWUPS,
        "max_incomplete_reminders": MAX_INCOMPLETE_REMINDERS,
    }
    kwargs.update(overrides)
    return decide(snapshot, now=now, **kwargs)


def _incomplete_snapshot(**overrides) -> InvitationSnapshot:
    """A supplier who submitted, but left two required fields blank."""

    fields = {
        "invitation_status": "incomplete",
        "quote_completeness": "incomplete",
        "missing_fields": ["moq", "payment_terms"],
        "missing_field_labels": ["minimum order quantity", "payment terms"],
    }
    fields.update(overrides)
    return _snapshot(**fields)


# ------------------------------------------------------------------- timing
def test_nothing_is_due_before_the_first_interval():
    decision = _decide(_snapshot(), now=NOW + timedelta(hours=10))

    assert decision.action == "skip"
    assert decision.is_actionable() is False
    # The reason says how long is left, so the dashboard can show a countdown.
    assert "due in" in decision.reason
    assert "62h" in decision.reason
    assert "72h" in decision.reason


def test_a_due_reminder_is_a_no_response_reminder():
    decision = _decide(_snapshot(), now=NOW + timedelta(hours=100))

    assert decision.action == "remind"
    assert decision.kind == "no_response"
    assert decision.sequence == 1
    assert decision.escalate_to_buyer is False
    assert decision.requested_fields == []
    assert "100h" in decision.reason


def test_the_second_run_after_a_first_reminder_is_sequence_two():
    snapshot = _snapshot(reminder_count=1, last_sent_at=NOW + timedelta(hours=100))

    decision = _decide(snapshot, now=NOW + timedelta(hours=280))

    # 180h since the last message exceeds the second interval (168h).
    assert decision.action == "remind"
    assert decision.sequence == 2
    assert decision.kind == "no_response"


def test_a_view_without_a_submission_is_called_out_in_the_reason():
    decision = _decide(_snapshot(view_count=3), now=NOW + timedelta(hours=100))

    assert decision.action == "remind"
    assert "opened the form 3 time(s)" in decision.reason


def test_the_reminder_cap_stops_the_sequence_and_names_the_maximum():
    decision = _decide(_snapshot(reminder_count=3), now=NOW + timedelta(hours=400))

    assert decision.action == "skip"
    assert "configured maximum of 3" in decision.reason


def test_a_high_risk_supplier_gets_one_extra_reminder_allowance():
    timing = {"now": NOW + timedelta(hours=400)}
    normal = _decide(_snapshot(reminder_count=3), **timing)
    high_risk = _decide(_snapshot(reminder_count=3, supplier_risk="high"), **timing)

    assert normal.action == "skip"
    assert high_risk.action == "remind"
    assert high_risk.sequence == 2


def test_an_unparseable_interval_list_still_reminds():
    """A missing configuration must not silently disable every follow-up."""

    decision = _decide(_snapshot(), now=NOW + timedelta(hours=100), intervals_hours=[])

    assert decision.action == "remind"


# ----------------------------------------------------------------- deadline
def test_a_passed_deadline_stops_all_follow_up():
    snapshot = _snapshot(deadline=NOW + timedelta(hours=50))

    decision = _decide(snapshot, now=NOW + timedelta(hours=60))

    assert decision.action == "skip"
    assert "deadline has passed" in decision.reason


def test_a_close_deadline_warns_even_before_the_interval_elapsed():
    snapshot = _snapshot(deadline=NOW + timedelta(hours=30))

    decision = _decide(snapshot, now=NOW + timedelta(hours=10))

    assert decision.action == "remind"
    assert decision.kind == "deadline_warning"
    assert "deadline is within 48h" in decision.reason


def test_a_distant_deadline_does_not_override_the_interval():
    snapshot = _snapshot(deadline=NOW + timedelta(days=30))

    decision = _decide(snapshot, now=NOW + timedelta(hours=10))

    assert decision.action == "skip"
    assert decision.kind != "deadline_warning"


# ----------------------------------------------------------- terminal states
def test_a_submitted_quote_is_never_chased():
    decision = _decide(_snapshot(invitation_status="submitted"), now=NOW + timedelta(hours=200))

    assert decision.action == "skip"
    assert "complete" in decision.reason


def test_cancelled_and_declined_invitations_are_left_alone():
    cancelled = _decide(_snapshot(invitation_status="cancelled"), now=NOW + timedelta(hours=200))
    declined = _decide(_snapshot(invitation_status="declined"), now=NOW + timedelta(hours=200))

    assert cancelled.action == "skip"
    assert "cancelled" in cancelled.reason
    assert declined.action == "skip"
    assert "declined" in declined.reason


def test_an_already_expired_invitation_is_not_chased():
    decision = _decide(_snapshot(invitation_status="expired"), now=NOW + timedelta(hours=200))

    assert decision.action == "skip"
    assert "expired" in decision.reason


def test_an_expired_form_link_is_not_chased():
    """Reminding about a dead link wastes the supplier's goodwill."""

    snapshot = _snapshot(link_expires_at=NOW + timedelta(hours=90))

    decision = _decide(snapshot, now=NOW + timedelta(hours=100))

    assert decision.action == "skip"
    assert "expired" in decision.reason


def test_an_invitation_that_was_never_sent_is_not_followed_up():
    snapshot = _snapshot(sent_at=None, last_sent_at=None)

    decision = _decide(snapshot, now=NOW + timedelta(hours=200))

    assert decision.action == "skip"
    assert "never been sent" in decision.reason
    assert "Send the form link first" in decision.reason


# ------------------------------------------------------- incomplete quotes
def test_an_incomplete_quote_is_chased_for_exactly_the_missing_fields():
    decision = _decide(_incomplete_snapshot(), now=NOW + timedelta(hours=100))

    assert decision.action == "request_missing_fields"
    assert decision.kind == "incomplete_quote"
    assert decision.sequence == 1
    # Exactly the missing set — no more (never re-ask an answered question) and no
    # fewer (the reply must be actionable in one round trip).
    assert decision.requested_fields == ["moq", "payment_terms"]
    assert decision.requested_labels == ["minimum order quantity", "payment terms"]
    assert "minimum order quantity" in decision.reason
    assert decision.escalate_to_buyer is False


def test_incomplete_quote_reminders_stop_at_the_configured_maximum():
    snapshot = _incomplete_snapshot(incomplete_reminder_count=MAX_INCOMPLETE_REMINDERS)

    decision = _decide(snapshot, now=NOW + timedelta(hours=100))

    assert decision.action == "skip"
    assert "Already asked 2 time(s)" in decision.reason


def test_an_incomplete_submission_with_no_recorded_gaps_asks_for_manual_review():
    snapshot = _incomplete_snapshot(missing_fields=[], missing_field_labels=[])

    decision = _decide(snapshot, now=NOW + timedelta(hours=100))

    assert decision.action == "skip"
    assert "review it manually" in decision.reason


def test_an_incomplete_quote_sequence_advances_with_each_reminder():
    snapshot = _incomplete_snapshot(incomplete_reminder_count=1)

    decision = _decide(snapshot, now=NOW + timedelta(hours=100))

    assert decision.action == "request_missing_fields"
    assert decision.sequence == 2


def test_labels_are_always_supplier_facing_even_when_the_snapshot_omits_them():
    """Internal field names must never reach a supplier.

    Regression guard: the policy fell back to ``snapshot.missing_fields`` directly,
    so a snapshot assembled without labels made the email ask for "the moq and
    payment_terms". The backend fills labels today, so this was latent rather than
    live — but the drafting rules forbid internal vocabulary outright, and a silent
    fallback is exactly how such a rule gets broken later.
    """

    snapshot = _incomplete_snapshot(missing_field_labels=[])

    decision = _decide(snapshot, now=NOW + timedelta(hours=100))

    assert decision.requested_fields == ["moq", "payment_terms"]
    assert decision.requested_labels == ["minimum order quantity", "payment terms"]
    assert not any("_" in label for label in decision.requested_labels)


# ------------------------------------------------------- blocking questions
def test_a_supplier_waiting_on_the_buyer_is_escalated_and_never_chased():
    """The single most important rule in the policy."""

    question = "What volume should we price for?"
    snapshot = _snapshot(blocking_question=question)

    decision = _decide(snapshot, now=NOW + timedelta(hours=100))

    assert decision.action == "skip"
    assert decision.escalate_to_buyer is True
    # The reason quotes the supplier, so the buyer knows what to answer.
    assert question in decision.reason
    assert "waiting on the buyer" in decision.reason


def test_a_blocking_question_outranks_an_incomplete_quote():
    """Even a targeted field request must not be sent while the buyer blocks."""

    snapshot = _incomplete_snapshot(blocking_question="Which Incoterms do you need?")

    decision = _decide(snapshot, now=NOW + timedelta(hours=100))

    assert decision.action == "skip"
    assert decision.escalate_to_buyer is True
    assert decision.requested_fields == []
    assert "Which Incoterms do you need?" in decision.reason


def test_a_blocking_question_does_not_resurrect_a_passed_deadline():
    """The deadline ordering is preserved: a closed window is closed."""

    snapshot = _snapshot(
        blocking_question="What volume should we price for?",
        deadline=NOW + timedelta(hours=50),
    )

    decision = _decide(snapshot, now=NOW + timedelta(hours=60))

    assert decision.action == "skip"
    assert decision.escalate_to_buyer is False
    assert "deadline has passed" in decision.reason


# ------------------------------------------------------------ next due date
def test_next_reminder_due_at_is_the_first_interval_after_the_last_message():
    assert next_reminder_due_at(
        _snapshot(), intervals_hours=INTERVALS, max_followups=MAX_FOLLOWUPS
    ) == NOW + timedelta(hours=72)

    # After a first reminder the next one follows the second interval.
    assert next_reminder_due_at(
        _snapshot(reminder_count=1, last_sent_at=NOW + timedelta(hours=100)),
        intervals_hours=INTERVALS,
        max_followups=MAX_FOLLOWUPS,
    ) == NOW + timedelta(hours=100 + 168)


@pytest.mark.parametrize(
    "status", ["submitted", "cancelled", "declined", "expired"]
)
def test_next_reminder_due_at_is_none_for_terminal_statuses(status):
    assert (
        next_reminder_due_at(
            _snapshot(invitation_status=status),
            intervals_hours=INTERVALS,
            max_followups=MAX_FOLLOWUPS,
        )
        is None
    )


def test_next_reminder_due_at_is_none_when_nothing_can_be_sent():
    assert (
        next_reminder_due_at(
            _snapshot(sent_at=None), intervals_hours=INTERVALS, max_followups=MAX_FOLLOWUPS
        )
        is None
    )
    assert (
        next_reminder_due_at(
            _snapshot(reminder_count=MAX_FOLLOWUPS),
            intervals_hours=INTERVALS,
            max_followups=MAX_FOLLOWUPS,
        )
        is None
    )


# -------------------------------------------------------------- drafting
async def test_the_template_draft_is_complete_without_an_llm():
    decision = _decide(_snapshot(), now=NOW + timedelta(hours=100))

    draft = await draft_followup(_snapshot(), decision, llm=None)

    assert draft.llm_generated is False
    assert draft.subject.strip()
    assert draft.body.strip()
    assert draft.kind == "no_response"
    assert draft.to_email == "priya@acme.example"
    assert draft.to_name == "Priya Sharma"
    assert draft.as_log_entry()["subject"] == draft.subject


async def test_the_template_draft_greets_the_contact_by_first_name():
    snapshot = _snapshot()
    decision = _decide(snapshot, now=NOW + timedelta(hours=100))

    draft = await draft_followup(snapshot, decision)

    assert "Hello Priya," in draft.body
    assert "Northwind Industrial" in draft.body  # signed off by the buyer's company

    # With no contact name the greeting falls back to the supplier's team.
    anonymous = _snapshot(contact_name=None)
    fallback = await draft_followup(anonymous, _decide(anonymous, now=NOW + timedelta(hours=100)))
    assert "Hello Acme Bearings team," in fallback.body


async def test_the_template_draft_always_carries_the_form_link():
    snapshot = _snapshot()
    decision = _decide(snapshot, now=NOW + timedelta(hours=100))

    draft = await draft_followup(snapshot, decision)

    assert FORM_LINK in draft.body


async def test_the_template_draft_uses_supplier_vocabulary_not_field_names():
    """Internal names ("moq", "lead_time_days") must never reach a supplier."""

    snapshot = _incomplete_snapshot()
    decision = _decide(snapshot, now=NOW + timedelta(hours=100))

    draft = await draft_followup(snapshot, decision)

    lowered = draft.body.lower()
    assert "minimum order quantity" in lowered
    assert "payment terms" in lowered
    for internal in (
        "moq",
        "unit_price",
        "lead_time_days",
        "lead_time",
        "validity_date",
        "warranty_months",
        "payment_terms",
        "incoterms",
        "shipping_cost",
    ):
        assert internal not in lowered, internal
    # No snake_case identifier of any kind reached the supplier.
    assert "_" not in draft.body


async def test_the_missing_fields_draft_only_asks_for_the_missing_fields():
    snapshot = _incomplete_snapshot()
    decision = _decide(snapshot, now=NOW + timedelta(hours=100))

    draft = await draft_followup(snapshot, decision)

    assert draft.requested_fields == ["moq", "payment_terms"]
    assert draft.requested_labels == decision.requested_labels
    assert "One detail needed" in draft.subject


async def test_the_missing_fields_draft_claims_only_one_item_is_outstanding():
    # The copy must agree with the list above it. It used to hard-code "this is the
    # only item we still need" regardless of how many fields were outstanding, so a
    # supplier with two gaps was told there was one — a false statement they can see
    # through, sitting directly under the correct list.
    snapshot = _incomplete_snapshot()
    decision = _decide(snapshot, now=NOW + timedelta(hours=100))

    draft = await draft_followup(snapshot, decision)

    assert len(decision.requested_labels) == 2
    assert "minimum order quantity" in draft.body
    assert "payment terms" in draft.body
    assert "these are the only items we still need" in draft.body
    assert "this is the only item we still need" not in draft.body


async def test_a_single_missing_field_draft_says_one_item():
    """The singular wording is still used, and only when it is true."""

    snapshot = _incomplete_snapshot(
        missing_fields=["moq"], missing_field_labels=["minimum order quantity"]
    )
    decision = _decide(snapshot, now=NOW + timedelta(hours=100))
    draft = await draft_followup(snapshot, decision)

    assert len(decision.requested_labels) == 1
    assert "this is the only item we still need" in draft.body


async def test_a_deadline_warning_draft_states_the_deadline():
    snapshot = _snapshot(deadline=datetime(2026, 6, 2, 9, 0, 0))
    decision = _decide(snapshot, now=NOW + timedelta(hours=10))

    draft = await draft_followup(snapshot, decision)

    assert decision.kind == "deadline_warning"
    assert "02 Jun 2026" in draft.body


async def test_a_raising_llm_falls_back_to_the_template():
    snapshot = _snapshot()
    decision = _decide(snapshot, now=NOW + timedelta(hours=100))

    async def failing_llm(system, user):
        raise RuntimeError("simulated provider outage")

    draft = await draft_followup(snapshot, decision, llm=failing_llm)
    template = await draft_followup(snapshot, decision, llm=None)

    assert draft.llm_generated is False
    assert draft.body == template.body
    assert draft.subject == template.subject


async def test_llm_output_that_omits_the_requested_items_is_rejected():
    """A draft that does not ask for the outstanding items has failed its job."""

    snapshot = _incomplete_snapshot()
    decision = _decide(snapshot, now=NOW + timedelta(hours=100))

    async def unhelpful_llm(system, user):
        return {"subject": "Hello", "body": "Hello Priya,\nJust checking in.\nBest regards"}

    draft = await draft_followup(snapshot, decision, llm=unhelpful_llm)

    assert draft.llm_generated is False
    assert "minimum order quantity" in draft.body  # the template's ask, not the model's


async def test_llm_output_with_a_forbidden_commercial_claim_is_rejected():
    """The follow-up agent is not entitled to make a commercial judgement."""

    snapshot = _incomplete_snapshot()
    decision = _decide(snapshot, now=NOW + timedelta(hours=100))

    async def overreaching_llm(system, user):
        return {
            "subject": "Quick question",
            "body": (
                "Hello Priya,\nYour quote is competitive and you are winning.\n"
                "Please send the minimum order quantity.\nBest regards"
            ),
        }

    draft = await draft_followup(snapshot, decision, llm=overreaching_llm)

    assert draft.llm_generated is False
    assert "competitive" not in draft.body.lower()


async def test_llm_output_that_is_blank_is_rejected():
    snapshot = _snapshot()
    decision = _decide(snapshot, now=NOW + timedelta(hours=100))

    async def empty_llm(system, user):
        return {"subject": "", "body": "   "}

    draft = await draft_followup(snapshot, decision, llm=empty_llm)

    assert draft.llm_generated is False
    assert draft.body.strip()


async def test_a_compliant_llm_draft_is_used_and_flagged_as_generated():
    snapshot = _incomplete_snapshot()
    decision = _decide(snapshot, now=NOW + timedelta(hours=100))

    async def good_llm(system, user):
        return {
            "subject": "Two details for RFQ-2026-001",
            "body": (
                "Hello Priya,\nThank you for the quote. We are still missing the "
                "minimum order quantity and the payment terms.\n"
                f"You can add them here: {FORM_LINK}\nBest regards,\nNorthwind Industrial"
            ),
        }

    draft = await draft_followup(snapshot, decision, llm=good_llm)

    assert draft.llm_generated is True
    assert draft.subject == "Two details for RFQ-2026-001"
    assert FORM_LINK in draft.body


async def test_the_llm_is_not_called_when_drafting_is_disallowed():
    snapshot = _snapshot()
    decision = _decide(snapshot, now=NOW + timedelta(hours=100))
    calls = []

    async def recording_llm(system, user):
        calls.append(user)
        return {"subject": "x", "body": "y"}

    draft = await draft_followup(snapshot, decision, llm=recording_llm, allow_llm=False)

    assert calls == []
    assert draft.llm_generated is False


@pytest.mark.parametrize(
    "body, expected",
    [
        ("Your quote is competitive.", "your quote is competitive"),
        ("Congratulations, you are winning.", "you are winning"),
        ("We have a better offer on the table.", "we have a better offer"),
        ("Your price is too high.", "your price is too high"),
        ("Please confirm the delivery terms.", None),
        ("", None),
    ],
)
def test_contains_forbidden_claim(body, expected):
    assert contains_forbidden_claim(body) == expected
