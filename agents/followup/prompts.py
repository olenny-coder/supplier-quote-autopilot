"""Follow-up writing rules.

Adapted from ForgeFlow's ``prompts/reply_agent.txt`` and ``prompts/response.txt``
(MIT, Copyright (c) 2026 JayleeBot) — see NOTICE. The writing guidance is carried
over because it encodes a procurement professional's judgement, not just style:

* thank them once, without flattery
* name each outstanding item in the **supplier's own vocabulary** — "minimum order
  quantity", never the internal field name ``moq``
* never re-ask something already answered; ForgeFlow calls that the single most
  damaging thing you can do to a supplier relationship
* never invent a deadline the buyer did not set
* never recommend a commercial outcome in a follow-up — surfacing a decision to
  the buyer is a different message to a different audience
* four to eight lines

The templates below are the deterministic fallback used when no LLM is configured
or the free-tier quota is exhausted, so the copy quality bar applies to them too.
"""

from agents.quote_parser.completeness import label_for

SYSTEM_PROMPT = """\
You write email for a procurement team. The coordinator hands you a brief saying
which supplier to write to and exactly what is outstanding. You write the message
and return it as JSON.

The coordinator has already decided what is outstanding. Do not second-guess that
list, do not add items to it, and do not go looking for more.

<rules>
  - Greet the contact by first name when the brief gives one; otherwise use a
    neutral "Hello,".
  - Thank them for the quote once, briefly, without flattery. If they have not
    submitted anything yet, do not thank them for a quote.
  - Ask for the outstanding items as a short list, in the supplier's own
    vocabulary: "minimum order quantity", "payment terms", "production lead
    time", "quote validity date", "delivery terms". Never use an internal field
    name such as "moq", "validity_date", or "lead_time_days".
  - When a field is outstanding because it was left blank on a form they already
    submitted, say so plainly and ask only for that.
  - Never restate their pricing back at them.
  - Never invent a deadline the buyer did not set. If the brief gives a deadline,
    you may state it once, factually.
  - Never recommend, hint at, or promise a commercial outcome. Do not say their
    quote is competitive, winning, or being considered — you do not know.
  - Do not re-ask anything the brief does not list.
  - Four to eight lines of body. No preamble before the greeting. Sign off with
    the buyer's company name given in the brief.
  - Plain text only. No markdown, no bullet characters other than a simple "- ".
</rules>

Return exactly one JSON object and nothing else:

{"subject": "<short, specific subject line>", "body": "<full plain-text body>"}
"""


def build_user_prompt(
    *,
    supplier_name: str,
    contact_name: str | None,
    rfq_number: str,
    item_name: str,
    buyer_company: str,
    buyer_contact_name: str | None,
    kind: str,
    reason: str,
    requested_labels: list[str],
    form_link: str,
    deadline_text: str | None,
    has_submitted: bool,
    sequence: int,
    total_sequences: int,
) -> str:
    """Assemble the brief the model writes from."""

    lines = [
        "<supplier>",
        f"  company: {supplier_name}",
        f"  contact: {contact_name or '(unknown — use a neutral greeting)'}",
        f"  has_submitted_a_quote: {'yes' if has_submitted else 'no'}",
        "</supplier>",
        "",
        "<rfq>",
        f"  reference: {rfq_number}",
        f"  item: {item_name}",
        f"  submission_deadline: {deadline_text or '(none set)'}",
        "</rfq>",
        "",
        "<buyer>",
        f"  company: {buyer_company}",
        f"  signer: {buyer_contact_name or buyer_company}",
        "</buyer>",
        "",
        "<outstanding>",
        f"  situation: {kind}",
        f"  coordinator_reason: {reason}",
    ]

    if requested_labels:
        lines.append("  items_to_request (request these and NOTHING else):")
        for label in requested_labels:
            lines.append(f"    - {label}")
    else:
        lines.append(
            "  items_to_request: (none — this is a reminder that no quote has been "
            "received yet)"
        )

    lines += [
        "</outstanding>",
        "",
        "<reminder_sequence>",
        f"  this_is_reminder: {sequence} of {total_sequences}",
        "</reminder_sequence>",
        "",
        "<form_link>",
        f"  {form_link or '(no link — do not mention one)'}",
        "</form_link>",
        "",
        "Write the message now. Return only the JSON object.",
    ]

    return "\n".join(lines)


# ----------------------------------------------------------- deterministic copy
def _greeting(contact_name: str | None, supplier_name: str) -> str:
    if contact_name:
        first = contact_name.strip().split()[0]
        return f"Hello {first},"
    return f"Hello {supplier_name} team,"


def _signature(company: str, contact_name: str | None) -> str:
    if contact_name:
        return f"Best regards,\n{contact_name}\n{company}"
    return f"Best regards,\n{company}"


def build_reminder_email(
    *,
    supplier_name: str,
    contact_name: str | None,
    rfq_number: str,
    item_name: str,
    buyer_company: str,
    buyer_contact_name: str | None,
    form_link: str,
    deadline_text: str | None,
    sequence: int,
    never_viewed: bool = False,
) -> tuple[str, str]:
    """Reminder for a supplier who has not submitted anything.

    Deliberately short and non-accusatory: a first reminder that reads like a
    dunning notice gets ignored, and a second one damages the relationship.
    """

    subject = f"Reminder: quote requested for {item_name} ({rfq_number})"

    if sequence > 1:
        subject = f"Second reminder: quote for {item_name} ({rfq_number})"

    lines = [
        _greeting(contact_name, supplier_name),
        "",
        f"We are still collecting quotes for {item_name} under our reference "
        f"{rfq_number}, and we have not received one from you yet.",
        "",
        "You can submit your quotation directly through this link — it takes about "
        "two minutes and needs no account:",
        form_link,
    ]

    if deadline_text:
        lines += ["", f"We are closing this request on {deadline_text}."]

    lines += [
        "",
        "If you would rather not quote this time, a one-line reply is genuinely "
        "useful — it lets us stop chasing you.",
        "",
        _signature(buyer_company, buyer_contact_name),
    ]

    return subject, "\n".join(lines)


def build_missing_fields_email(
    *,
    supplier_name: str,
    contact_name: str | None,
    rfq_number: str,
    item_name: str,
    buyer_company: str,
    buyer_contact_name: str | None,
    form_link: str,
    requested_labels: list[str],
    sequence: int,
) -> tuple[str, str]:
    """Targeted follow-up asking only for the fields that are actually missing."""

    subject = f"One detail needed on your quote for {item_name} ({rfq_number})"

    if sequence > 1:
        subject = (
            f"Following up: {len(requested_labels)} detail(s) still needed on "
            f"{rfq_number}"
        )

    if len(requested_labels) == 1:
        ask = f"we are still missing the {requested_labels[0]}"
        closing = (
            "Everything else on your submission is complete — this is the only item "
            "we still need."
        )
    else:
        listed = ", ".join(requested_labels[:-1]) + f" and {requested_labels[-1]}"
        ask = f"we are still missing the {listed}"
        closing = (
            "Everything else on your submission is complete — these are the only "
            "items we still need."
        )

    lines = [
        _greeting(contact_name, supplier_name),
        "",
        f"Thank you for sending your quote for {item_name} ({rfq_number}).",
        "",
        f"To be able to compare it against the others on equal terms, {ask}.",
        "",
        "You can add it through the same link:",
        form_link,
        "",
        closing,
        "",
        _signature(buyer_company, buyer_contact_name),
    ]

    return subject, "\n".join(lines)


def build_deadline_email(
    *,
    supplier_name: str,
    contact_name: str | None,
    rfq_number: str,
    item_name: str,
    buyer_company: str,
    buyer_contact_name: str | None,
    form_link: str,
    deadline_text: str,
) -> tuple[str, str]:
    subject = f"Closing soon: {item_name} ({rfq_number})"

    body = "\n".join(
        [
            _greeting(contact_name, supplier_name),
            "",
            f"We are closing the request for {item_name} ({rfq_number}) on "
            f"{deadline_text} and have not received your quotation yet.",
            "",
            "If you intend to quote, this link is the fastest route:",
            form_link,
            "",
            "If you would rather pass on this one, just say so and we will take you "
            "off the list for it.",
            "",
            _signature(buyer_company, buyer_contact_name),
        ]
    )

    return subject, body


def template_for(kind: str):
    """Pick the plain-text template for a decision kind."""

    if kind == "incomplete_quote":
        return build_missing_fields_email
    if kind == "deadline_warning":
        return build_deadline_email
    return build_reminder_email


def field_labels(fields: list[str]) -> list[str]:
    """Supplier-facing labels for internal field names."""

    return [label_for(field) for field in fields]
