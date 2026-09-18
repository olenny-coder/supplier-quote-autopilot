"""Invitation email copy.

Plain text, written to be read on a phone, with the link on its own line so it is
tappable everywhere. The buyer's company name is the sender identity — suppliers
need to know who is asking before they will spend time quoting.
"""


def build_invitation_email(
    *,
    supplier_name: str,
    contact_name: str | None,
    rfq_number: str,
    item_name: str,
    specification: str,
    quantity: int,
    unit: str,
    delivery_expectation: str,
    deadline_text: str | None,
    buyer_company: str,
    buyer_contact_name: str | None,
    buyer_contact_email: str | None,
    form_link: str,
    notes: str | None = None,
) -> tuple[str, str]:
    """Return ``(subject, body)`` for the initial quote request."""

    greeting = f"Hello {contact_name.split()[0]}," if contact_name else f"Hello {supplier_name} team,"

    subject = f"Quote request: {item_name} ({rfq_number})"

    lines = [
        greeting,
        "",
        f"{buyer_company} would like a quotation for the following:",
        "",
        f"  Item:       {item_name}",
        f"  Spec:       {specification}",
        f"  Quantity:   {quantity:,} {unit}",
        f"  Required by: {delivery_expectation}",
    ]

    if notes:
        lines += ["", f"Additional requirements: {notes.strip()}"]

    lines += [
        "",
        "Submit your quote here — no account or sign-up needed:",
        form_link,
        "",
        "Please include your unit price, currency, production lead time, minimum "
        "order quantity, payment terms, delivery terms, and how long the quote "
        "stays valid. You can attach a spec sheet or brochure on the same page.",
    ]

    if deadline_text:
        lines += ["", f"We would appreciate your quote by {deadline_text}."]

    lines += [""]

    if buyer_contact_email:
        lines += [
            f"If anything is unclear, reply to this email or write to "
            f"{buyer_contact_email}.",
            "",
        ]

    lines.append(
        "Best regards,\n"
        + (buyer_contact_name + "\n" if buyer_contact_name else "")
        + buyer_company
    )

    return subject, "\n".join(lines)
