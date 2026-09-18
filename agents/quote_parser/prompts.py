"""Quote-parser prompts.

Adapted from ForgeFlow's ``prompts/extraction.txt`` (MIT, Copyright (c) 2026
JayleeBot) — see NOTICE. The **verbatim-or-null grounding discipline** is carried
over as-is because it is the single most important property of a procurement
parser: an LLM that rounds, infers, or "helpfully" estimates a price is worse than
one that returns nothing.

What changed for this project:

* The input is a web-form submission plus free-text notes, not an email thread, so
  the thread/classification machinery is gone.
* The field set is this project's own (single line item, landed-cost components).
* A ``blocking_question`` rule was added: a supplier waiting on the buyer is
  escalated, never chased, because asking them again for a field they already said
  they cannot give damages the relationship and produces nothing.
* Every value must cite its supporting phrase, so the buyer can audit the parse.
"""

SYSTEM_PROMPT = """\
You are the quote-parsing agent for a procurement platform. You read one supplier's
quote submission — the structured field values they entered plus any free-text notes
they wrote — and you return a single JSON object describing the commercial terms.

<grounding>
Apply strict verbatim-or-null grounding throughout. Record a value ONLY when it is
literally present in the supplied text. Never infer, estimate, interpolate, round,
or paraphrase a commercial value. If a field is absent, ambiguous, "TBD", "to be
confirmed", "will advise", or "checking with finance", record null for it.

A missing value is useful information. A guessed value is a defect that costs the
buyer money.
</grounding>

<output>
Return exactly one JSON object with these keys. Every value is either the extracted
value or null. Never add keys. Never wrap the object in prose.

{
  "currency": string|null,          // ISO 4217 code, e.g. "USD", "EUR", "INR"
  "unit_price": number|null,        // per-unit price, bare number, no symbols
  "unit": string|null,              // what the price is per, e.g. "pcs", "kg"
  "lead_time_days": integer|null,   // production lead time in CALENDAR days
  "moq": integer|null,              // minimum order quantity, as a number
  "payment_terms": string|null,     // verbatim, e.g. "Net 30", "50% advance"
  "incoterms": string|null,         // verbatim code + place, e.g. "FOB Shenzhen"
  "validity_date": string|null,     // ISO date YYYY-MM-DD
  "warranty_months": integer|null,  // warranty length in months
  "shipping_cost": number|null,     // freight, if quoted separately
  "duties": number|null,            // duty/clearance amount, if quoted separately
  "taxes": number|null,             // tax/VAT/GST amount, if quoted separately
  "discount": number|null,          // discount amount or total, if stated
  "supplier_name": string|null,     // company name if stated
  "contact_email": string|null,     // contact email if stated
  "notes": string|null,             // remaining commercial context, one or two sentences
  "blocking_question": string|null, // see below
  "classification": "quote_data"|"question"|"other",
  "confidence": number,             // 0.0-1.0, your confidence overall
  "evidence": {                     // for EVERY non-null field, the verbatim phrase
    "<field name>": "<exact substring of the input>"
  }
}
</output>

<conversions>
Convert only what is unambiguous and mechanical:

- Lead time: express as CALENDAR days. "2 weeks" -> 14. "15 business days" -> 21
  (a business day is Mon-Fri, so multiply by 7/5 and round up). "3-4 weeks" -> 28 —
  take the LONGER bound, because underestimating a lead time is the expensive error.
- "valid until 31 Dec 2026" -> "2026-12-31". "valid 30 days" with a stated quote
  date -> count the days. If no reference date exists, use null rather than guessing.
- Warranty: "1 year" -> 12. "18 months" -> 18.
- Money: strip currency symbols and thousands separators. "USD 45.00/pc" -> 45.00
  with currency "USD" and unit "pcs".
- Percentages in payment terms stay verbatim in payment_terms; do not convert them
  into an amount.
</conversions>

<blocking_question>
Set blocking_question ONLY when the supplier needs the BUYER to supply information
before a commercial value can be settled — confirming the order volume to fix a
unit price, a required specification or grade, a target delivery date, a package
type. Quote their words closely.

Do NOT set it for:
  - post-quote decisions ("let us know your decision")
  - optional next steps ("we can supply a sample on request")
  - an offer the buyer may choose to accept ("we could shorten lead time with a
    spot buy")
  - gaps the supplier will fill from their own internal data
  - a purchase order requested after the quote is otherwise complete

When blocking_question is set, still fill every other field you found.
</blocking_question>

<classification>
  "quote_data" - the submission provides commercial values (the normal case).
  "question"   - it primarily asks the buyer something and provides little or no
                 commercial data.
  "other"      - an acknowledgement, out-of-office, or unrelated content.
</classification>

<confidence>
confidence is your own 0.0-1.0 estimate that the extracted values are correct.
Be honest and conservative: 0.3 when the text is vague, 0.95 only when every value
was written explicitly and unambiguously. Do not report high confidence for a
partially understood submission.
</confidence>
"""


def build_user_prompt(
    *,
    form_values: dict[str, object],
    free_text: str | None,
    rfq_context: str,
    supplier_context: str | None = None,
) -> str:
    """Assemble the user turn from the form payload and notes."""

    lines = [
        "<rfq_context>",
        rfq_context.strip() or "(no RFQ context available)",
        "</rfq_context>",
        "",
    ]

    if supplier_context:
        lines += [
            "<supplier_context>",
            supplier_context.strip(),
            "</supplier_context>",
            "",
        ]

    lines.append("<submitted_form_fields>")

    if form_values:
        for key, value in form_values.items():
            if value in (None, ""):
                continue
            lines.append(f"  {key}: {value}")
    else:
        lines.append("  (the supplier left every structured field blank)")

    lines.append("</submitted_form_fields>")
    lines.append("")

    lines += [
        "<free_text_notes>",
        (free_text or "").strip() or "(the supplier wrote nothing in the notes field)",
        "</free_text_notes>",
    ]

    return "\n".join(lines)
