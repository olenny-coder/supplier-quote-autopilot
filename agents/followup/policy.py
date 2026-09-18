"""Follow-up policy — decides whether to chase, ask for fields, or do nothing.

Adapted from ForgeFlow's action-ordering discipline (``prompts/response.txt``,
MIT, Copyright (c) 2026 JayleeBot) — see NOTICE.

ForgeFlow's rule is "take the FIRST tool that applies, in this order", and the
important consequence is that *flagging the buyer beats chasing the supplier*. If
a supplier is waiting on the buyer for a spec or a volume before they can price,
sending them a reminder asks for something they have already said they cannot
give. It produces no answer, annoys the supplier, and hides the fact that the
buyer is the blocker.

The same ordering is preserved here:

    1. nothing to do          → skip  (already complete, cancelled, declined)
    2. deadline passed        → skip  (the window is closed)
    3. supplier blocked on us → skip, escalate to buyer
    4. quote incomplete       → request_missing_fields
    5. not submitted          → remind
    6. not due yet            → skip

Everything is a pure function of an :class:`InvitationSnapshot` and a clock, so a
scheduler run is fully testable without a database or a network.
"""

from datetime import datetime

from agents.followup.schemas import FollowUpDecision
from agents.followup.schemas import InvitationSnapshot

#: Statuses that end the conversation entirely.
TERMINAL_STATUSES = {"submitted", "cancelled", "declined", "expired"}

#: Additional reminders granted to a high-risk supplier: a higher-risk source is
#: the one you most want a second quote from.
HIGH_RISK_BONUS = 1


def decide(
    snapshot: InvitationSnapshot,
    *,
    now: datetime,
    intervals_hours: list[int],
    max_followups: int,
    max_incomplete_reminders: int,
    before_deadline_hours: int = 48,
) -> FollowUpDecision:
    """Decide what to do about one invitation right now."""

    # ---- 1. terminal states ------------------------------------------------
    if snapshot.invitation_status == "submitted":
        return FollowUpDecision(
            action="skip",
            reason="The quote is complete — nothing to chase.",
        )

    if snapshot.invitation_status == "cancelled":
        return FollowUpDecision(
            action="skip",
            reason="The buyer cancelled this invitation.",
        )

    if snapshot.invitation_status == "declined":
        return FollowUpDecision(
            action="skip",
            reason="The supplier declined to quote.",
        )

    if snapshot.invitation_status == "expired":
        return FollowUpDecision(
            action="skip",
            reason="The invitation has already been expired.",
        )

    # ---- 2. deadline ------------------------------------------------------
    if snapshot.deadline is not None and now >= snapshot.deadline:
        return FollowUpDecision(
            action="skip",
            reason=(
                "The RFQ deadline has passed "
                f"({snapshot.deadline.date().isoformat()}); follow-ups are stopped."
            ),
        )

    # ---- 3. the supplier is blocked on the buyer ---------------------------
    if snapshot.blocking_question:
        return FollowUpDecision(
            action="skip",
            escalate_to_buyer=True,
            reason=(
                "The supplier is waiting on the buyer before they can finalize: "
                f"\"{snapshot.blocking_question}\". Chasing them would ask for "
                "something they have already said they cannot give."
            ),
        )

    # ---- 4. an incomplete quote exists -------------------------------------
    if snapshot.quote_completeness == "incomplete" or snapshot.invitation_status == "incomplete":
        if not snapshot.missing_fields:
            return FollowUpDecision(
                action="skip",
                reason=(
                    "The submission is marked incomplete but no missing fields "
                    "were recorded — review it manually."
                ),
            )

        if snapshot.incomplete_reminder_count >= max_incomplete_reminders:
            return FollowUpDecision(
                action="skip",
                reason=(
                    f"Already asked {snapshot.incomplete_reminder_count} time(s) for the "
                    f"missing field(s); stopping rather than nagging."
                ),
            )

        labels = snapshot.missing_field_labels or snapshot.missing_fields

        return FollowUpDecision(
            action="request_missing_fields",
            kind="incomplete_quote",
            sequence=snapshot.incomplete_reminder_count + 1,
            requested_fields=list(snapshot.missing_fields),
            requested_labels=list(labels),
            reason=(
                "The supplier submitted a quote but left these required field(s) "
                "blank: " + ", ".join(labels) + "."
            ),
        )

    # ---- 5/6. not submitted yet -------------------------------------------
    allowance = max_followups + (
        HIGH_RISK_BONUS if (snapshot.supplier_risk or "").lower() == "high" else 0
    )

    if snapshot.reminder_count >= allowance:
        return FollowUpDecision(
            action="skip",
            reason=(
                f"Already sent {snapshot.reminder_count} reminder(s), which is the "
                f"configured maximum of {allowance}."
            ),
        )

    reference = snapshot.last_sent_at or snapshot.sent_at

    if reference is None:
        return FollowUpDecision(
            action="skip",
            reason=(
                "The invitation has never been sent, so there is nothing to "
                "follow up. Send the form link first."
            ),
        )

    if snapshot.link_expires_at is not None and now >= snapshot.link_expires_at:
        return FollowUpDecision(
            action="skip",
            reason=(
                "The supplier's form link expired on "
                f"{snapshot.link_expires_at.date().isoformat()}."
            ),
        )

    intervals = sorted(intervals_hours) or [72]

    sequence = min(snapshot.reminder_count + 1, len(intervals))
    threshold_hours = intervals[sequence - 1]

    elapsed_hours = (now - reference).total_seconds() / 3600.0

    # A deadline that is close overrides the normal interval: a reminder that
    # arrives after the cut-off is worthless.
    deadline_soon = (
        snapshot.deadline is not None
        and (snapshot.deadline - now).total_seconds() / 3600.0 <= before_deadline_hours
    )

    if elapsed_hours < threshold_hours and not deadline_soon:
        due_in = threshold_hours - elapsed_hours
        return FollowUpDecision(
            action="skip",
            reason=(
                f"Next reminder is due in {due_in:.0f}h "
                f"(interval {threshold_hours}h after the last message)."
            ),
        )

    kind = "deadline_warning" if deadline_soon and elapsed_hours < threshold_hours else "no_response"

    if kind == "deadline_warning":
        reason = (
            f"The RFQ deadline is within {before_deadline_hours}h and no quote has "
            f"arrived."
        )
    elif snapshot.view_count > 0:
        reason = (
            f"No quote after {elapsed_hours:.0f}h, but the supplier has opened the "
            f"form {snapshot.view_count} time(s) without submitting."
        )
    else:
        reason = f"No response {elapsed_hours:.0f}h after the link was sent."

    return FollowUpDecision(
        action="remind",
        kind=kind,
        sequence=sequence,
        reason=reason,
    )


def next_reminder_due_at(
    snapshot: InvitationSnapshot,
    *,
    intervals_hours: list[int],
    max_followups: int,
) -> datetime | None:
    """When the next automated reminder would fire — shown on the dashboard."""

    from datetime import timedelta

    if snapshot.invitation_status in TERMINAL_STATUSES:
        return None

    if snapshot.reminder_count >= max_followups:
        return None

    reference = snapshot.last_sent_at or snapshot.sent_at

    if reference is None:
        return None

    intervals = sorted(intervals_hours) or [72]
    index = min(snapshot.reminder_count, len(intervals) - 1)

    return reference + timedelta(hours=intervals[index])
