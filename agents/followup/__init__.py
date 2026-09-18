"""Follow-up agent.

Decides who to chase, what to ask for, and writes the message.

    >>> from agents.followup import InvitationSnapshot, decide
    >>> decision = decide(snapshot, now=..., intervals_hours=[72, 168],
    ...                   max_followups=3, max_incomplete_reminders=2)
    >>> decision.action
    'remind'

The decision order is inherited from ForgeFlow (MIT, Copyright (c) 2026 JayleeBot)
— see NOTICE — and the important part of it is that **escalating to the buyer
beats chasing the supplier**. A supplier who is waiting on the buyer for a spec
cannot be reminded into answering.

Nothing in this package performs I/O. The scheduler in
``backend/app/features/followup`` owns the database and the email transport and
calls in here for the judgement.
"""

from agents.followup.drafter import JsonCompleter
from agents.followup.drafter import contains_forbidden_claim
from agents.followup.drafter import draft_followup
from agents.followup.policy import TERMINAL_STATUSES
from agents.followup.policy import decide
from agents.followup.policy import next_reminder_due_at
from agents.followup.schemas import DecisionAction
from agents.followup.schemas import ExpirySummary
from agents.followup.schemas import FollowUpDecision
from agents.followup.schemas import FollowUpDraft
from agents.followup.schemas import FollowUpKind
from agents.followup.schemas import InvitationSnapshot
from agents.followup.schemas import SchedulerSummary

__all__ = [
    "TERMINAL_STATUSES",
    "DecisionAction",
    "ExpirySummary",
    "FollowUpDecision",
    "FollowUpDraft",
    "FollowUpKind",
    "InvitationSnapshot",
    "JsonCompleter",
    "SchedulerSummary",
    "contains_forbidden_claim",
    "decide",
    "draft_followup",
    "next_reminder_due_at",
]
