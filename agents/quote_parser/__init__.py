"""Quote-parsing agent.

Turns a supplier's web-form submission (plus free-text notes) into a normalized,
typed quote, and reports which required fields are still missing.

    >>> from agents.quote_parser import parse_form_values, evaluate_completeness
    >>> parsed = parse_form_values({"unit_price": "USD 2.50", "lead_time": "3 weeks"})
    >>> parsed.unit_price, parsed.lead_time_days
    (Decimal('2.50'), 21)

Three layers, applied strongest-evidence-first (see ``parser.py``):

1. structured form values — what the supplier typed into a labelled field
2. LLM extraction — verbatim-or-null, prompts in ``prompts.py``
3. deterministic labelled-line extraction — the always-available fallback

The package has no network access and no provider SDK: an LLM is injected as a
plain async callable, so everything here is testable offline.
"""

from agents.quote_parser import completeness
from agents.quote_parser import heuristic
from agents.quote_parser import normalize
from agents.quote_parser.classify import classify_text
from agents.quote_parser.classify import extract_question
from agents.quote_parser.completeness import FIELD_LABELS
from agents.quote_parser.completeness import evaluate
from agents.quote_parser.completeness import label_for
from agents.quote_parser.completeness import next_question_for
from agents.quote_parser.heuristic import extract_fields
from agents.quote_parser.heuristic import heuristic_parse
from agents.quote_parser.parser import JsonCompleter
from agents.quote_parser.parser import evaluate_completeness
from agents.quote_parser.parser import merge_parsed
from agents.quote_parser.parser import missing_field_labels
from agents.quote_parser.parser import parse_form_values
from agents.quote_parser.parser import parse_submission
from agents.quote_parser.schemas import PARSABLE_FIELDS
from agents.quote_parser.schemas import CompletenessReport
from agents.quote_parser.schemas import ParsedQuote

__all__ = [
    "FIELD_LABELS",
    "PARSABLE_FIELDS",
    "CompletenessReport",
    "JsonCompleter",
    "ParsedQuote",
    "classify_text",
    "completeness",
    "evaluate",
    "evaluate_completeness",
    "extract_fields",
    "extract_question",
    "heuristic",
    "heuristic_parse",
    "label_for",
    "merge_parsed",
    "missing_field_labels",
    "next_question_for",
    "normalize",
    "parse_form_values",
    "parse_submission",
]
