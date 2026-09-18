"""Completeness checking — what a submission is still missing.

Adapted from ForgeFlow's missing-field rules (MIT, Copyright (c) 2026 JayleeBot) —
see NOTICE. ForgeFlow splits gaps into ``per_part`` and ``quote_level`` because it
parses multi-part email threads; MVP quotes here carry a single line item, so the
per-part dimension collapses and the rule set that matters is preserved instead:

* **"Explicitly none" is an answer.** "No MOQ at this stage" is complete. Chasing
  it re-asks a question the supplier already answered, which ForgeFlow identifies
  as the single most damaging thing you can do to a supplier relationship.
* **"TBD" is not an answer.** Neither is a promise to send something later.
* **Fields the buyer never asked for are never chased.** A gap is only a gap
  relative to the RFQ's own required-field contract.
* **A blocking question is escalated, not chased.** If the supplier is waiting on
  the buyer, no reminder can produce the value.
"""

from agents.quote_parser.normalize import is_declined
from agents.quote_parser.normalize import is_negative
from agents.quote_parser.schemas import CompletenessReport

#: Internal field name -> how a procurement professional says it to a supplier.
#: Follow-up copy must use the right-hand side, never the left.
FIELD_LABELS: dict[str, str] = {
    "unit_price": "unit price",
    "currency": "currency",
    "unit": "unit of measure",
    "lead_time": "production lead time",
    "lead_time_days": "production lead time",
    "moq": "minimum order quantity",
    "payment_terms": "payment terms",
    "incoterms": "delivery terms (Incoterms)",
    "validity_date": "quote validity date",
    "warranty_months": "warranty period",
    "shipping_cost": "freight cost",
    "duties": "duty and clearance cost",
    "taxes": "tax amount",
    "discount": "discount",
    "supplier_name": "supplier name",
    "contact_email": "contact email address",
}

#: Fields the platform itself can always infer, so they are reported as optional
#: even if the RFQ lists them.
DEFAULT_OPTIONAL_FIELDS = {
    "shipping_cost",
    "duties",
    "taxes",
    "discount",
    "warranty_months",
    "notes",
    "supplier_name",
    "contact_email",
    "unit",
}


def label_for(field: str) -> str:
    """Supplier-facing label. Unknown fields fall back to a de-underscored form."""

    return FIELD_LABELS.get(field, field.replace("_", " "))


def _has_value(value: object) -> bool:
    """A field is answered when it carries a concrete, non-declined value."""

    if value is None:
        return False

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return False
        # "TBD" and friends are not answers.
        if is_negative(text):
            return False
        return True

    return True


def evaluate(
    fields: dict[str, object],
    required_fields: list[str] | None,
    *,
    blocking_question: str | None = None,
    raw_text: str | None = None,
) -> CompletenessReport:
    """Compare a parsed quote against the RFQ's required-field contract.

    ``fields`` uses the parser's field names; ``required_fields`` uses the RFQ's
    (which speak of ``lead_time`` where the parser produces ``lead_time_days``).
    The alias map reconciles the two.
    """

    if not required_fields:
        required_fields = []

    aliases = {
        "lead_time": "lead_time_days",
        "validity": "validity_date",
        "warranty": "warranty_months",
        "price": "unit_price",
    }

    satisfied: list[str] = []
    missing: list[str] = []
    declined: list[str] = []

    for field in required_fields:
        parser_field = aliases.get(field, field)
        value = fields.get(parser_field)

        if _has_value(value):
            satisfied.append(field)
            continue

        # An explicit "none" written in the notes is an answer even when the
        # structured field is empty.
        if raw_text and is_declined(raw_text) and parser_field in {"moq", "warranty_months", "shipping_cost", "duties", "taxes", "discount"}:
            declined.append(field)
            satisfied.append(field)
            continue

        missing.append(field)

    missing_optional = [
        field
        for field in DEFAULT_OPTIONAL_FIELDS
        if field not in {aliases.get(f, f) for f in required_fields}
        and not _has_value(fields.get(field))
    ]

    # A supplier who is blocked on the buyer cannot answer these fields; chasing
    # them would ask for something they already said they cannot give.
    if blocking_question and missing:
        return CompletenessReport(
            is_complete=False,
            status="incomplete",
            missing=missing,
            satisfied=satisfied,
            missing_labels=[label_for(f) for f in missing],
            declined=declined,
            missing_optional=missing_optional,
            summary=(
                "The supplier is waiting on the buyer before these can be settled: "
                + ", ".join(label_for(f) for f in missing)
                + ". Resolve the supplier's question instead of sending a reminder."
            ),
        )

    labels = [label_for(f) for f in missing]

    if not missing:
        summary = "Every required field is answered."
    else:
        summary = "Missing required field(s): " + ", ".join(labels) + "."

    return CompletenessReport(
        is_complete=not missing,
        status="incomplete" if missing else "complete",
        missing=missing,
        satisfied=satisfied,
        missing_labels=labels,
        declined=declined,
        missing_optional=missing_optional,
        summary=summary,
    )


def next_question_for(
    report: CompletenessReport,
    blocking_question: str | None = None,
) -> str | None:
    """One-line description of what happens next, for the buyer's dashboard."""

    if blocking_question:
        return f"Waiting on the buyer: {blocking_question}"

    if report.is_complete:
        return "No action needed — the quote is complete."

    return "Send a targeted reminder asking only for: " + ", ".join(report.missing_labels) + "."
