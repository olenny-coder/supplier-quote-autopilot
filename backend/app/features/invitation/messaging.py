"""Invitation email copy.

Plain text, written to be read on a phone, with the link on its own line so it is
tappable everywhere. The buyer's company name is the sender identity — suppliers
need to know who is asking before they will spend time quoting.

The list of what to include is built from the RFQ's *own* required-field contract
and its type-aware labels, never from a fixed sentence. A hard-coded sentence asked
every maintenance contractor for a "production lead time" and a "minimum order
quantity" — two fields a services RFQ does not even collect, while never mentioning
the response time it does require. Copy that names the wrong fields is worse than no
copy: it produces a quote missing exactly what the buyer needs.
"""


def _join_phrases(items: list[str]) -> str:
    """Oxford-comma list: ``a``, ``a and b``, ``a, b, and c``."""

    if not items:
        return ""

    if len(items) == 1:
        return items[0]

    if len(items) == 2:
        return f"{items[0]} and {items[1]}"

    return ", ".join(items[:-1]) + f", and {items[-1]}"


#: What a supplier may usefully attach, phrased for what is being bought.
ATTACHMENT_HINTS = {
    "service": (
        "You can attach your quotation, a method statement, or copies of your "
        "licences on the same page."
    ),
    "goods": "You can attach a spec sheet or brochure on the same page.",
}


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
    procurement_type: str = "goods",
    required_field_labels: list[str] | None = None,
    site_text: str | None = None,
    required_response_hours: int | None = None,
    required_accreditations: list[str] | None = None,
    tax_note: str | None = None,
) -> tuple[str, str]:
    """Return ``(subject, body)`` for the initial quote request."""

    greeting = f"Hello {contact_name.split()[0]}," if contact_name else f"Hello {supplier_name} team,"

    subject = f"Quote request: {item_name} ({rfq_number})"

    is_service = procurement_type == "service"

    lines = [
        greeting,
        "",
        f"{buyer_company} would like a quotation for the following:",
        "",
        f"  Item:       {item_name}",
        f"  Spec:       {specification}",
        # "Quantity" is the goods word. A services RFQ counts points, visits or
        # hours, so calling it a quantity reads as a request for a part count.
        f"  {'Scope' if is_service else 'Quantity':<10}  {quantity:,} {unit}",
        f"  Required by: {delivery_expectation}",
    ]

    if is_service and site_text:
        lines.append(f"  Site:       {site_text}")

    if is_service and required_response_hours is not None:
        lines.append(
            f"  Attendance: within {required_response_hours} hours of a call-out"
        )

    if notes:
        lines += ["", f"Additional requirements: {notes.strip()}"]

    if is_service and required_accreditations:
        lines += [
            "",
            "We require the following to be current for this work: "
            + _join_phrases([str(item) for item in required_accreditations])
            + ".",
        ]

    lines += [
        "",
        "Submit your quote here — no account or sign-up needed:",
        form_link,
    ]

    labels = [label for label in (required_field_labels or []) if label and label.strip()]

    if labels:
        lines += [
            "",
            "Please include your "
            + _join_phrases(labels)
            + ". "
            + ATTACHMENT_HINTS.get(procurement_type, ATTACHMENT_HINTS["goods"]),
        ]
    else:
        lines += ["", ATTACHMENT_HINTS.get(procurement_type, ATTACHMENT_HINTS["goods"])]

    if tax_note:
        lines += ["", tax_note]

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
