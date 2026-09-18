"""Deterministic, offline extraction from free-text supplier notes.

The fallback path. It exists so the product keeps working when:

* no ``LLM_API_KEY`` is configured (a fresh clone, a CI run, a demo),
* the free-tier quota for the day is exhausted (Groq: 14,400 requests/day),
* the provider is down.

It is intentionally a **labelled-line extractor**, not a general NLP system: it
looks for ``<label>: <value>`` pairs, which is how suppliers actually fill in a
"Notes" box when answering an RFQ. Anything it cannot match is preserved verbatim
in ``unparsed`` rather than discarded.

Values found here are treated as high confidence — they are literal substrings of
what the supplier wrote, which is exactly the grounding the LLM path is instructed
to imitate.
"""

import re
from datetime import date

from agents.quote_parser.normalize import clean_text
from agents.quote_parser.normalize import normalize_incoterms
from agents.quote_parser.normalize import normalize_payment_terms
from agents.quote_parser.normalize import normalize_unit_text
from agents.quote_parser.normalize import parse_currency
from agents.quote_parser.normalize import parse_int
from agents.quote_parser.normalize import parse_lead_time_days
from agents.quote_parser.normalize import parse_money
from agents.quote_parser.normalize import parse_validity_date
from agents.quote_parser.normalize import parse_warranty_months
from agents.quote_parser.schemas import ParsedQuote

#: label pattern -> (parser field, coercion function)
LABELLED_FIELDS: list[tuple[str, str, object]] = [
    (r"unit\s*price|price\s*(?:per|/)\s*\w+|price|rate", "unit_price", parse_money),
    (r"currency|ccy", "currency", parse_currency),
    (r"unit\s*of\s*measure|uom|per\b", "unit", normalize_unit_text),
    (r"lead\s*time|delivery\s*time|production\s*time|leadtime", "lead_time_days", parse_lead_time_days),
    (r"moq|minimum\s*(?:order\s*)?(?:quantity|qty)", "moq", parse_int),
    (r"payment\s*terms|terms\s*of\s*payment|payment", "payment_terms", normalize_payment_terms),
    (r"incoterms?|delivery\s*terms|trade\s*terms", "incoterms", normalize_incoterms),
    (r"valid(?:ity)?(?:\s*(?:until|till|thru|to|date))?|expir\w*", "validity_date", parse_validity_date),
    (r"warranty|guarantee", "warranty_months", parse_warranty_months),
    (r"shipping|freight|carriage", "shipping_cost", parse_money),
    (r"dut(?:y|ies)|customs", "duties", parse_money),
    (r"tax(?:es)?|vat|gst", "taxes", parse_money),
    (r"discount|rebate", "discount", parse_money),
    (r"company|supplier\s*name|vendor", "supplier_name", clean_text),
    (r"e-?mail|contact", "contact_email", clean_text),
]

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

#: "3.50 USD" / "$3.50" / "3.50/pc"
BARE_PRICE_RE = re.compile(
    r"(?:([$€£¥₹])\s*)?(\d[\d,]*(?:\.\d+)?)\s*(?:(USD|EUR|GBP|INR|JPY|CNY|VND|THB|MXN|BRL)\b)?"
    r"\s*(?:/|per\s+)\s*(pc|pcs|piece|pieces|kg|unit|set|box)",
    re.IGNORECASE,
)


def _iter_labelled_lines(text: str):
    """Yield ``(label, value)`` for every ``label: value`` pair in the text."""

    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("-*•").strip()

        if not line:
            continue

        # Accept ":", "=", or " - " as the separator.
        parts = re.split(r"\s*[:=]\s*|\s+[-–]\s+", line, maxsplit=1)

        if len(parts) != 2:
            continue

        label, value = parts[0].strip(), parts[1].strip()

        if label and value:
            yield label, value


def extract_fields(raw_text: str | None, reference_date: date | None = None) -> dict[str, object]:
    """Pull labelled values out of free text. Only literally-present values."""

    if not raw_text:
        return {}

    found: dict[str, object] = {}
    evidence: dict[str, str] = {}

    for label, value in _iter_labelled_lines(raw_text):
        lowered = label.lower()

        for pattern, field, coerce in LABELLED_FIELDS:
            if field in found:
                continue
            if not re.search(rf"\b(?:{pattern})\b", lowered, re.IGNORECASE):
                continue

            if field == "validity_date":
                parsed = coerce(value, reference_date) if coerce is parse_validity_date else coerce(value)
            else:
                parsed = coerce(value)

            if parsed is None:
                continue

            found[field] = parsed
            evidence[field] = f"{label}: {value}"
            break

    # ---- unlabelled recoveries -------------------------------------------
    if "contact_email" not in found:
        match = EMAIL_RE.search(raw_text)
        if match:
            found["contact_email"] = match.group(0)
            evidence["contact_email"] = match.group(0)

    if "unit_price" not in found:
        match = BARE_PRICE_RE.search(raw_text)
        if match:
            price = parse_money(match.group(2))
            if price is not None:
                found["unit_price"] = price
                evidence["unit_price"] = match.group(0).strip()
                if "currency" not in found:
                    currency = parse_currency(match.group(3) or match.group(1))
                    if currency:
                        found["currency"] = currency
                        evidence["currency"] = match.group(0).strip()
                if "unit" not in found:
                    unit = normalize_unit_text(match.group(4))
                    if unit:
                        found["unit"] = unit
                        evidence["unit"] = match.group(0).strip()

    if "currency" not in found:
        currency = parse_currency(raw_text)
        if currency:
            found["currency"] = currency
            evidence["currency"] = currency

    if "lead_time_days" not in found:
        # Only accept a bare lead-time phrase when the text mentions lead/delivery,
        # so a random "30" elsewhere is not promoted into a commercial value.
        if re.search(r"\b(lead|delivery|production)\b", raw_text, re.IGNORECASE):
            days = parse_lead_time_days(raw_text)
            if days is not None:
                found["lead_time_days"] = days
                evidence["lead_time_days"] = "inferred from a stated lead-time phrase"

    found["_evidence"] = evidence

    return found


def heuristic_parse(
    raw_text: str | None,
    *,
    reference_date: date | None = None,
    base: ParsedQuote | None = None,
) -> ParsedQuote:
    """Build a :class:`ParsedQuote` from free text alone."""

    parsed = base.model_copy(deep=True) if base else ParsedQuote()

    extracted = extract_fields(raw_text, reference_date)
    evidence = extracted.pop("_evidence", {})

    for field, value in extracted.items():
        if getattr(parsed, field, None) in (None, ""):
            setattr(parsed, field, value)
            parsed.field_sources[field] = "heuristic"

    parsed.evidence.update(evidence)

    if raw_text and raw_text.strip():
        parsed.unparsed = raw_text.strip()[:4000]

    parsed.source = "heuristic"

    # Note: classification is deliberately NOT set here. This layer extracts values;
    # deciding whether the text is data, a question, or noise is
    # `classify_text`'s job, and claiming the default would override it.

    return parsed
