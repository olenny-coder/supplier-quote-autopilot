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
from agents.quote_parser.schemas import carries_value

#: Internal field name -> how a procurement professional says it to a supplier.
#: Follow-up copy must use the right-hand side, never the left.
#:
#: This is the single label table for the whole system: the API schemas, the
#: dashboard, the public form, and the follow-up emails all read it. A second table
#: anywhere else would eventually disagree with this one.
#:
#: The wording here is the **base** vocabulary. Where a field genuinely means
#: something different for a service than for goods — a minimum order quantity is
#: not a minimum callout, and a production lead time is not a mobilisation time —
#: the type-specific wording lives in :data:`SERVICE_LABEL_OVERRIDES` and is applied
#: by :func:`label_for` when the procurement type is known. Keeping the override in
#: this module rather than in the domain taxonomy is deliberate: a label table split
#: across two modules is exactly the drift this table exists to prevent.
FIELD_LABELS: dict[str, str] = {
    # ---- price and basis -------------------------------------------------
    "unit_price": "unit price",
    "currency": "currency",
    "unit": "unit of measure",
    # ---- speed -----------------------------------------------------------
    "response_time": "response time (SLA)",
    "response_time_hours": "response time (SLA)",
    "lead_time": "lead time",
    "lead_time_days": "production lead time",
    # ---- commercial ------------------------------------------------------
    "payment_terms": "payment terms",
    "validity_date": "quote validity date",
    "moq": "minimum order quantity",
    "callout_charge": "callout / attendance charge",
    "labour_rate": "labour rate per hour",
    "materials_markup": "materials markup",
    "materials_markup_pct": "materials markup",
    # ---- quality and compliance ------------------------------------------
    "defect_liability": "defect liability period",
    "warranty_months": "warranty period",
    "compliance": "accreditations and licences",
    "compliance_accreditations": "accreditations and licences",
    # ---- money -----------------------------------------------------------
    "shipping_cost": "freight or delivery",
    "duties": "duty and clearance cost",
    "taxes": "tax amount",
    "gst_rate": "GST rate",
    "discount": "discount",
    # ---- goods -----------------------------------------------------------
    "incoterms": "delivery terms (Incoterms)",
    # ---- identity --------------------------------------------------------
    "supplier_name": "company name",
    "contact_email": "contact email address",
    "notes": "notes",
}

#: Fields whose meaning changes with what is being bought. A plumbing contractor
#: reading "minimum order quantity" would be puzzled; a supplier of bolts reading
#: "minimum callout" would be more so.
SERVICE_LABEL_OVERRIDES: dict[str, str] = {
    "unit_price": "rate",
    "unit": "rate basis",
    "lead_time": "mobilisation time",
    "lead_time_days": "mobilisation time",
    "moq": "minimum callout charge",
    "validity_date": "rates valid until",
    "warranty_months": "defect liability period",
    "defect_liability": "defect liability period",
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
    # Services. These are scored when present and never chased when absent, but a
    # buyer still wants to see "no callout charge was stated" on the dashboard —
    # an unstated callout is how a cheap-looking maintenance quote turns expensive.
    "callout_charge",
    "labour_rate",
    "materials_markup_pct",
    "compliance_accreditations",
    "gst_rate",
}

#: Fields where an explicit "none" in the free text is a real answer even though the
#: structured field is empty ("no callout charge", "no minimum"). Chasing one of
#: these re-asks a question the supplier has already answered.
DECLINABLE_FIELDS = {
    "moq",
    "warranty_months",
    "shipping_cost",
    "duties",
    "taxes",
    "discount",
    "callout_charge",
    "labour_rate",
    "materials_markup_pct",
    "compliance",
    "compliance_accreditations",
    "gst_rate",
}


def label_for(field: str, procurement_type: str | None = None) -> str:
    """Supplier-facing label. Unknown fields fall back to a de-underscored form.

    Pass ``procurement_type`` whenever it is known. The type only changes the wording
    of a handful of fields, but those are the ones a supplier would otherwise read as
    a question about the wrong thing.
    """

    if procurement_type == "service":
        override = SERVICE_LABEL_OVERRIDES.get(field)

        if override:
            return override

    return FIELD_LABELS.get(field, field.replace("_", " "))


def _has_value(value: object) -> bool:
    """A field is answered when it carries a concrete, non-declined value."""

    if isinstance(value, str) and is_negative(value):
        return False

    return carries_value(value)


def evaluate(
    fields: dict[str, object],
    required_fields: list[str] | None,
    *,
    blocking_question: str | None = None,
    raw_text: str | None = None,
    procurement_type: str | None = None,
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
        "defect_liability": "warranty_months",
        "price": "unit_price",
        # The RFQ asks for a "response time"; the parser records it in hours. Without
        # this alias a services RFQ would mark EVERY submission incomplete for a
        # field the supplier did answer, and the follow-up agent would then chase it
        # indefinitely — asking a supplier for the SLA they had already given.
        "response_time": "response_time_hours",
        "compliance": "compliance_accreditations",
        "materials_markup": "materials_markup_pct",
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
        if raw_text and is_declined(raw_text) and parser_field in DECLINABLE_FIELDS:
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
            missing_labels=[label_for(f, procurement_type) for f in missing],
            declined=declined,
            missing_optional=missing_optional,
            summary=(
                "The supplier is waiting on the buyer before these can be settled: "
                + ", ".join(label_for(f, procurement_type) for f in missing)
                + ". Resolve the supplier's question instead of sending a reminder."
            ),
        )

    labels = [label_for(f, procurement_type) for f in missing]

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
    procurement_type: str | None = None,
) -> str | None:
    """One-line description of what happens next, for the buyer's dashboard."""

    if blocking_question:
        return f"Waiting on the buyer: {blocking_question}"

    if report.is_complete:
        return "No action needed — the quote is complete."

    labels = report.missing_labels or [
        label_for(field, procurement_type) for field in report.missing
    ]

    return "Send a targeted reminder asking only for: " + ", ".join(labels) + "."
