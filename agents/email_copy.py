"""House style for every email this product sends to a supplier.

One module so the invitation, the reminders and the chase for missing fields cannot
drift apart. Before this, each template wrote its own sign-off, so the same
supplier could receive an invitation signed by the buyer's company and a reminder
signed by something else — which reads as an automated system pretending to be a
person.

The position taken here: **the product sends, the buyer is the counterparty.** Every
email names the buyer in the first sentence and in the sign-off, tells the supplier
where a reply actually goes, and signs off as the product. That is honest about who
is asking and who is writing, and a supplier always knows which organisation they
are quoting to.
"""

PRODUCT_NAME = "Quote Autopilot"

#: Where a supplier's quotation goes and who can see it. Said once, on the first
#: contact, because "who else sees my price?" is the natural question and leaving it
#: unanswered is how a supplier decides not to bid.
PRIVACY_NOTE = (
    "Your quotation is private to you. No other supplier sees your pricing, and the "
    "buyer sees only what you submit."
)


def introduction(item_name: str, rfq_number: str, buyer_company: str) -> str:
    """The opening sentence of a first contact.

    Introduces the product without hiding the buyer, and says plainly that the tool
    is collecting the quotes so a supplier does not wonder who is really asking.
    """

    return (
        f"{buyer_company} has asked us to collect quotations for {item_name} "
        f"(reference {rfq_number}) through {PRODUCT_NAME}."
    )


def follow_up_context(item_name: str, rfq_number: str, buyer_company: str) -> str:
    """The equivalent of :func:`introduction` for a message that is not the first.

    A reminder is normally the second thing a supplier sees, so it does not repeat
    the full introduction. But it can still be the *first* message that actually
    lands — a bounced invitation, a spam folder, or a thread forwarded to a
    colleague who has never heard of the buyer — so it names the buyer and the
    product in one clause rather than assuming the earlier email was read.
    """

    return (
        f"{PRODUCT_NAME} is collecting quotations for {buyer_company} for "
        f"{item_name} (reference {rfq_number})"
    )


def signature(buyer_company: str) -> str:
    """The sign-off: the product, with the buyer named beneath it.

    Not the buyer's signature alone, because the message was written and sent by the
    system; and not the product alone, because the supplier has to know which
    organisation the quotation is for. Both, in that order.
    """

    return f"Best regards,\n{PRODUCT_NAME}\non behalf of {buyer_company}"


def reply_note(
    buyer_contact_name: str | None,
    buyer_company: str,
    buyer_contact_email: str | None = None,
) -> str:
    """Tell the supplier where a reply lands.

    A monitoring address that nobody reads is worse than no address at all: a
    supplier with a question simply gives up. `reply_to` on the message is already
    the buyer, so this only has to say so.
    """

    who = (
        f"{buyer_contact_name} at {buyer_company}"
        if buyer_contact_name
        else buyer_company
    )

    note = f"Reply to this email to reach {who} directly."

    if buyer_contact_email:
        note += f" Or write to {buyer_contact_email}."

    return note


__all__ = [
    "PRIVACY_NOTE",
    "PRODUCT_NAME",
    "follow_up_context",
    "introduction",
    "reply_note",
    "signature",
]
