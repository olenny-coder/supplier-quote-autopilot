"""Quote parser — turns a supplier submission into a normalized quote.

Three layers, strongest evidence first:

1. **Form values.** What the supplier typed into a labelled field of the web form.
   Unambiguous, so it always wins.
2. **LLM extraction** over the form values plus free-text notes. Follows the
   verbatim-or-null prompt in :mod:`agents.quote_parser.prompts`.
3. **Heuristic labelled-line extraction** (``heuristic.py``). Always runs, and is
   the only path used when no LLM is configured.

The merge is **field-wise and additive**: a value from an earlier layer is never
overwritten by a later one, and a later layer only fills gaps. A null from the LLM
can never erase a field the supplier explicitly filled in.

Claude/api framing is deliberately absent — the caller injects a JSON-completing
callable, so this package has no HTTP, no provider SDK, and no configuration. That
is what makes the whole parser testable offline.
"""

from datetime import date
from typing import Any
from typing import Protocol

from agents.quote_parser.classify import classify_text
from agents.quote_parser.classify import extract_question
from agents.quote_parser.completeness import evaluate
from agents.quote_parser.completeness import label_for
from agents.quote_parser.heuristic import heuristic_parse
from agents.quote_parser.normalize import clean_text
from agents.quote_parser.normalize import normalize_incoterms
from agents.quote_parser.normalize import normalize_payment_terms
from agents.quote_parser.normalize import normalize_unit_text
from agents.quote_parser.normalize import parse_currency
from agents.quote_parser.normalize import parse_date
from agents.quote_parser.normalize import parse_int
from agents.quote_parser.normalize import parse_lead_time_days
from agents.quote_parser.normalize import parse_money
from agents.quote_parser.normalize import parse_moq
from agents.quote_parser.normalize import parse_validity_date
from agents.quote_parser.normalize import parse_warranty_months
from agents.quote_parser.prompts import SYSTEM_PROMPT
from agents.quote_parser.prompts import build_user_prompt
from agents.quote_parser.schemas import CompletenessReport
from agents.quote_parser.schemas import ParsedQuote

#: field name -> coercion. Applied to LLM output so a model returning "USD 2.50"
#: is normalized identically to the heuristic path.
COERCIONS: dict[str, object] = {
    "currency": parse_currency,
    "unit_price": parse_money,
    "shipping_cost": parse_money,
    "duties": parse_money,
    "taxes": parse_money,
    "discount": parse_money,
    "unit": normalize_unit_text,
    "lead_time_days": parse_lead_time_days,
    # parse_moq, not parse_int: it understands "MOQ: 500", "minimum order 1000",
    # "no MOQ" (an explicit 0, i.e. an answer) and "TBD" (a gap). parse_int would
    # record None for a declined MOQ, which then scores *worse* than naming a small
    # minimum — penalising the supplier who answered.
    "moq": parse_moq,
    "warranty_months": parse_warranty_months,
    "payment_terms": normalize_payment_terms,
    "incoterms": normalize_incoterms,
}


class JsonCompleter(Protocol):
    """Minimal contract the parser needs from an LLM client.

    The backend satisfies this with
    :meth:`app.core.llm_client.LLMClient.chat_json`, which keeps this package free
    of anything provider-specific.
    """

    async def __call__(self, system: str, user: str) -> dict[str, Any] | None: ...


# ---------------------------------------------------------------- form payload
FORM_FIELD_ALIASES: dict[str, str] = {
    "supplier_name": "supplier_name",
    "supplier": "supplier_name",
    "company": "supplier_name",
    "contact_email": "contact_email",
    "email": "contact_email",
    "currency": "currency",
    "unit_price": "unit_price",
    "price": "unit_price",
    "unit": "unit",
    "uom": "unit",
    "lead_time": "lead_time_days",
    "lead_time_days": "lead_time_days",
    "moq": "moq",
    "payment_terms": "payment_terms",
    "incoterms": "incoterms",
    "validity_date": "validity_date",
    "warranty_months": "warranty_months",
    "shipping_cost": "shipping_cost",
    "duties": "duties",
    "taxes": "taxes",
    "discount": "discount",
    "notes": "notes",
}

DATE_FIELDS = {"validity_date"}


def parse_form_values(
    values: dict[str, Any],
    *,
    reference_date: date | None = None,
) -> ParsedQuote:
    """Normalize a raw form payload into a :class:`ParsedQuote`.

    Unknown keys are ignored, but their non-empty values are appended to
    ``unparsed`` so nothing a supplier typed is silently dropped.
    """

    parsed = ParsedQuote(source="form")
    leftovers: list[str] = []

    for key, raw in (values or {}).items():
        if raw in (None, ""):
            continue

        field = FORM_FIELD_ALIASES.get(str(key).strip().lower())

        if field is None:
            if key != "free_text":
                leftovers.append(f"{key}: {raw}")
            continue

        if field == "notes":
            parsed.notes = clean_text(raw)
            parsed.field_sources["notes"] = "form"
            continue

        if field == "supplier_name":
            parsed.supplier_name = clean_text(raw)
            parsed.field_sources["supplier_name"] = "form"
            continue

        if field == "contact_email":
            parsed.contact_email = clean_text(raw)
            parsed.field_sources["contact_email"] = "form"
            continue

        if field in DATE_FIELDS:
            value = parse_date(raw, reference_date)
        else:
            coerce = COERCIONS.get(field)
            value = coerce(raw) if coerce else clean_text(raw)

        if value is None:
            leftovers.append(f"{key}: {raw}")
            continue

        setattr(parsed, field, value)
        parsed.field_sources[field] = "form"
        parsed.evidence[field] = f"{key}={raw}"

    if leftovers:
        parsed.unparsed = "\n".join(leftovers)[:4000]

    parsed.confidence = _confidence(parsed) + 0.35 if parsed.provided_fields() else 0.0
    parsed.confidence = round(min(1.0, parsed.confidence), 2)

    return parsed


# ----------------------------------------------------------------- merge logic
def merge_parsed(*layers: ParsedQuote) -> ParsedQuote:
    """Merge parsed layers field-wise, earliest layer winning."""

    merged = ParsedQuote()
    contributors: list[str] = []

    for layer in layers:
        if layer is None:
            continue

        contributed = False

        for field, value in layer.provided_fields().items():
            if getattr(merged, field, None) in (None, ""):
                setattr(merged, field, value)
                contributed = True

        for field, source in layer.field_sources.items():
            merged.field_sources.setdefault(field, source)

        for field, snippet in layer.evidence.items():
            merged.evidence.setdefault(field, snippet)

        merged.notes = merged.notes or layer.notes
        merged.unparsed = merged.unparsed or layer.unparsed
        merged.blocking_question = merged.blocking_question or layer.blocking_question
        merged.confidence = max(merged.confidence, layer.confidence)

        # A layer's classification is only adopted when the layer actually decided.
        # `ParsedQuote.classification` defaults to None precisely so this line can
        # tell "the classifier said quote_data" apart from "nobody has classified
        # this yet".
        if merged.classification is None and layer.classification is not None:
            merged.classification = layer.classification
            contributed = True

        if contributed:
            contributors.append(layer.source)

    # Provenance: name the combination when more than one layer contributed, rather
    # than reporting whichever layer happened to run last.
    unique = [name for name in dict.fromkeys(contributors) if name != "merged"]

    if not unique:
        merged.source = "form"
    elif len(unique) == 1:
        merged.source = unique[0]
    else:
        merged.source = "merged"

    return merged


def _confidence(parsed: ParsedQuote) -> float:
    """Coverage-based confidence over the fields that matter commercially."""

    key_fields = (
        "unit_price",
        "currency",
        "lead_time_days",
        "moq",
        "payment_terms",
        "incoterms",
        "validity_date",
    )

    present = sum(1 for field in key_fields if getattr(parsed, field, None) is not None)

    return round(present / len(key_fields), 2)


def coerce_llm_payload(payload: dict[str, Any], reference_date: date | None) -> ParsedQuote:
    """Turn raw model JSON into a validated :class:`ParsedQuote`."""

    parsed = ParsedQuote(source="llm")

    for field, raw in (payload or {}).items():
        if field in {"evidence", "confidence", "classification", "blocking_question"}:
            continue

        if field not in ParsedQuote.model_fields or raw in (None, ""):
            continue

        if field in DATE_FIELDS:
            value = parse_validity_date(raw, reference_date)
        else:
            coerce = COERCIONS.get(field)
            value = coerce(raw) if coerce else clean_text(raw)

        if value is None:
            continue

        setattr(parsed, field, value)
        parsed.field_sources[field] = "llm"

    evidence = payload.get("evidence")

    if isinstance(evidence, dict):
        parsed.evidence = {
            str(key): str(value)[:400]
            for key, value in evidence.items()
            if isinstance(key, str)
        }

    question = payload.get("blocking_question")

    if isinstance(question, str) and question.strip():
        parsed.blocking_question = question.strip()[:500]

    classification = payload.get("classification")

    if classification in {"quote_data", "question", "other"}:
        parsed.classification = classification

    try:
        parsed.confidence = max(0.0, min(1.0, float(payload.get("confidence", 0.0))))
    except (TypeError, ValueError):
        parsed.confidence = 0.0

    return parsed


# -------------------------------------------------------------------- top level
async def parse_submission(
    *,
    form_values: dict[str, Any] | None = None,
    free_text: str | None = None,
    llm: JsonCompleter | None = None,
    reference_date: date | None = None,
    rfq_context: str = "",
    supplier_context: str | None = None,
) -> tuple[ParsedQuote, CompletenessReport]:
    """Parse a submission and report what it is still missing.

    Returns ``(parsed_quote, completeness_report)``. Never raises for a bad model
    response — a failed LLM call degrades to the heuristic layer.
    """

    reference = reference_date or date.today()

    form_layer = parse_form_values(form_values or {}, reference_date=reference)

    heuristic_layer = heuristic_parse(
        free_text,
        reference_date=reference,
    )

    llm_layer: ParsedQuote | None = None

    if llm is not None and (free_text or form_values):
        try:
            payload = await llm(
                SYSTEM_PROMPT,
                build_user_prompt(
                    form_values=form_values or {},
                    free_text=free_text,
                    rfq_context=rfq_context,
                    supplier_context=supplier_context,
                ),
            )
        except Exception:  # noqa: BLE001 - the LLM is optional by design
            payload = None

        if payload:
            llm_layer = coerce_llm_payload(payload, reference)

    parsed = merge_parsed(form_layer, llm_layer, heuristic_layer)

    # Whoever is left, the classification must be decided before escalation logic
    # runs. A question-only message with no LLM configured is the case this
    # protects: without it, the missing classification defaulted to "quote_data"
    # and a supplier waiting on the buyer got chased instead of escalated.
    if parsed.classification is None:
        parsed.classification = classify_text(free_text) if free_text else "quote_data"

    if not parsed.blocking_question and free_text and parsed.classification == "question":
        question = extract_question(free_text)

        if question:
            parsed.blocking_question = question

    return parsed, evaluate(
        parsed.model_dump(),
        [],
        blocking_question=parsed.blocking_question,
        raw_text=free_text,
    )


def evaluate_completeness(
    parsed: ParsedQuote,
    required_fields: list[str],
    *,
    raw_text: str | None = None,
) -> CompletenessReport:
    """Check a parsed quote against an RFQ's required-field contract."""

    return evaluate(
        parsed.model_dump(),
        required_fields,
        blocking_question=parsed.blocking_question,
        raw_text=raw_text,
    )


def missing_field_labels(fields: list[str]) -> list[str]:
    """Expose the supplier-facing labels, for follow-up copy and the dashboard."""

    return [label_for(field) for field in fields]


__all__ = [
    "JsonCompleter",
    "evaluate_completeness",
    "merge_parsed",
    "missing_field_labels",
    "parse_form_values",
    "parse_submission",
]
