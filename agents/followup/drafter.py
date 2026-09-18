"""Follow-up drafting — LLM when available, a good template when not.

The template path is not a stub. It runs whenever there is no ``LLM_API_KEY``, or
the free-tier quota is spent, or the provider is down — which on a free tier is a
routine event, not an incident. Both paths produce copy that respects the same
rules (see ``prompts.py``), so the product never sends a worse message because the
LLM was unavailable; it just sends a less personalised one.
"""

from typing import Any
from typing import Protocol

from agents.followup.prompts import SYSTEM_PROMPT
from agents.followup.prompts import build_user_prompt
from agents.followup.prompts import template_for
from agents.followup.schemas import FollowUpDecision
from agents.followup.schemas import FollowUpDraft
from agents.followup.schemas import InvitationSnapshot


class JsonCompleter(Protocol):
    async def __call__(self, system: str, user: str) -> dict[str, Any] | None: ...


#: Naive phrases a follow-up must never contain — they imply a commercial
#: judgement the follow-up agent is not entitled to make.
FORBIDDEN_PHRASES = (
    "your quote is competitive",
    "you are winning",
    "you are the lowest",
    "we will award",
    "congratulations",
    "your price is too high",
    "we have a better offer",
)


def contains_forbidden_claim(body: str) -> str | None:
    lowered = (body or "").lower()

    for phrase in FORBIDDEN_PHRASES:
        if phrase in lowered:
            return phrase

    return None


def _deadline_text(snapshot: InvitationSnapshot) -> str | None:
    if snapshot.deadline is None:
        return None

    return snapshot.deadline.date().strftime("%d %b %Y")


async def draft_followup(
    snapshot: InvitationSnapshot,
    decision: FollowUpDecision,
    *,
    llm: JsonCompleter | None = None,
    total_sequences: int = 3,
    allow_llm: bool = True,
) -> FollowUpDraft:
    """Write the message for an actionable decision.

    Falls back to the template on any model failure, and rejects model output that
    makes a commercial claim the follow-up agent is not allowed to make.
    """

    kind = decision.kind
    requested_labels = decision.requested_labels or []
    deadline_text = _deadline_text(snapshot)

    template = template_for(kind)

    if kind == "incomplete_quote":
        subject, body = template(
            supplier_name=snapshot.supplier_name,
            contact_name=snapshot.contact_name,
            rfq_number=snapshot.rfq_number,
            item_name=snapshot.item_name,
            buyer_company=snapshot.buyer_company,
            buyer_contact_name=snapshot.buyer_contact_name,
            form_link=snapshot.form_link,
            requested_labels=requested_labels,
            sequence=decision.sequence,
        )
    elif kind == "deadline_warning":
        subject, body = template(
            supplier_name=snapshot.supplier_name,
            contact_name=snapshot.contact_name,
            rfq_number=snapshot.rfq_number,
            item_name=snapshot.item_name,
            buyer_company=snapshot.buyer_company,
            buyer_contact_name=snapshot.buyer_contact_name,
            form_link=snapshot.form_link,
            deadline_text=deadline_text or "the deadline",
        )
    else:
        subject, body = template(
            supplier_name=snapshot.supplier_name,
            contact_name=snapshot.contact_name,
            rfq_number=snapshot.rfq_number,
            item_name=snapshot.item_name,
            buyer_company=snapshot.buyer_company,
            buyer_contact_name=snapshot.buyer_contact_name,
            form_link=snapshot.form_link,
            deadline_text=deadline_text,
            sequence=decision.sequence,
            never_viewed=snapshot.view_count == 0,
        )

    draft = FollowUpDraft(
        subject=subject,
        body=body,
        kind=kind,
        requested_fields=list(decision.requested_fields),
        requested_labels=requested_labels,
        llm_generated=False,
        to_email=snapshot.contact_email,
        to_name=snapshot.contact_name,
    )

    if llm is None or not allow_llm:
        return draft

    try:
        payload = await llm(
            SYSTEM_PROMPT,
            build_user_prompt(
                supplier_name=snapshot.supplier_name,
                contact_name=snapshot.contact_name,
                rfq_number=snapshot.rfq_number,
                item_name=snapshot.item_name,
                buyer_company=snapshot.buyer_company,
                buyer_contact_name=snapshot.buyer_contact_name,
                kind=kind,
                reason=decision.reason,
                requested_labels=requested_labels,
                form_link=snapshot.form_link,
                deadline_text=deadline_text,
                has_submitted=snapshot.quote_completeness is not None,
                sequence=decision.sequence,
                total_sequences=total_sequences,
            ),
        )
    except Exception:  # noqa: BLE001 - the LLM is optional by design
        return draft

    if not isinstance(payload, dict):
        return draft

    subject_value = str(payload.get("subject") or "").strip()
    body_value = str(payload.get("body") or "").strip()

    if not subject_value or not body_value:
        return draft

    forbidden = contains_forbidden_claim(body_value)

    if forbidden:
        # A model that volunteered a commercial claim has gone off-brief; the
        # deterministic copy is safer than editing its output.
        return draft

    if requested_labels:
        # The model must actually ask for the outstanding items, or it has not
        # done the one job it was given.
        lowered = body_value.lower()
        if not any(label.lower() in lowered for label in requested_labels):
            return draft

    return FollowUpDraft(
        subject=subject_value[:512],
        body=body_value[:8000],
        kind=kind,
        requested_fields=list(decision.requested_fields),
        requested_labels=requested_labels,
        llm_generated=True,
        to_email=snapshot.contact_email,
        to_name=snapshot.contact_name,
    )
