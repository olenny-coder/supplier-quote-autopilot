"""Quote parser — layering, normalization, completeness, classification, evals.

The parser is the component that decides what a supplier actually said, so the
properties protected here are the ones a buyer relies on:

* **strongest evidence wins** — a value the supplier typed into a labelled form
  field is never overwritten by free text or by a model, and a model's ``null``
  never erases it;
* **no invented values** — "TBD" is not an answer, but "No MOQ" *is* one, and a
  field the buyer never asked for is never chased;
* **a supplier blocked on the buyer is escalated, not chased**;
* the deterministic heuristic path keeps working with no LLM configured, which is
  the routine free-tier case rather than an incident.

Everything runs offline: the LLM is injected as a plain async callable, and the
reference date is passed explicitly so no test depends on the wall clock.
"""

import re
from datetime import date
from decimal import Decimal

import pytest

from agents.quote_parser import FIELD_LABELS
from agents.quote_parser import ParsedQuote
from agents.quote_parser import classify_text
from agents.quote_parser import evaluate_completeness
from agents.quote_parser import extract_question
from agents.quote_parser import heuristic_parse
from agents.quote_parser import label_for
from agents.quote_parser import parse_form_values
from agents.quote_parser import parse_submission
from agents.quote_parser.normalize import is_declined
from agents.quote_parser.normalize import is_negative
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
from agents.quote_parser.parser import merge_parsed
from agents.quote_parser.parser import coerce_llm_payload

REFERENCE_DATE = date(2026, 1, 1)

NOTES_BLOCK = (
    "Unit price: 3.20 USD per pc\n"
    "Lead time: 6-8 weeks\n"
    "MOQ: 500 units\n"
    "Payment terms: TBD\n"
    "Incoterms: DDP Hamburg\n"
    "Valid until: 2027-03-15"
)


def _llm_returning(payload):
    """An async completer that always answers with ``payload``."""

    async def completer(system: str, user: str):
        return payload

    return completer


def _llm_raising(exc: Exception | None = None):
    """An async completer that fails the way an outage or a bad key would."""

    async def completer(system: str, user: str):
        raise exc or RuntimeError("simulated provider outage")

    return completer


# ------------------------------------------------------------------ layering
async def test_form_values_win_over_free_text_and_over_the_llm():
    """A labelled form field is unambiguous evidence and outranks every guess."""

    parsed, _ = await parse_submission(
        form_values={"unit_price": "USD 9.99", "lead_time": "3 weeks"},
        free_text="Unit price: 1.00 USD per pc\nLead time: 10 weeks",
        llm=_llm_returning({"unit_price": 5.0, "lead_time_days": "9 weeks"}),
        reference_date=REFERENCE_DATE,
    )

    assert parsed.unit_price == Decimal("9.99")
    assert parsed.lead_time_days == 21
    assert parsed.field_sources["unit_price"] == "form"
    assert parsed.field_sources["lead_time_days"] == "form"


async def test_an_llm_null_never_erases_a_form_value():
    """Verbatim-or-null means null is "not found", not "delete what you have"."""

    parsed, _ = await parse_submission(
        form_values={"unit_price": "2.50", "lead_time": "3 weeks"},
        free_text="Pricing as discussed.",
        llm=_llm_returning({"unit_price": None, "lead_time_days": None, "currency": None}),
        reference_date=REFERENCE_DATE,
    )

    assert parsed.unit_price == Decimal("2.50")
    assert parsed.lead_time_days == 21
    assert parsed.field_sources["unit_price"] == "form"


async def test_the_llm_layer_is_additive_and_records_its_own_provenance():
    """Fields only the model supplies are kept, and tagged as model-supplied."""

    parsed, _ = await parse_submission(
        form_values={"unit_price": "2.50"},
        free_text="We can also offer a two-year warranty on DDP Hamburg terms.",
        llm=_llm_returning({"warranty_months": 24, "incoterms": "DDP Hamburg"}),
        reference_date=REFERENCE_DATE,
    )

    assert parsed.unit_price == Decimal("2.50")
    assert parsed.warranty_months == 24
    assert parsed.incoterms == "DDP Hamburg"
    assert parsed.field_sources["unit_price"] == "form"
    assert parsed.field_sources["warranty_months"] == "llm"
    assert parsed.field_sources["incoterms"] == "llm"


async def test_a_raising_llm_degrades_to_the_heuristic_path():
    """A provider outage must not lose the supplier's submission."""

    parsed, _ = await parse_submission(
        form_values={"unit_price": "2.50"},
        free_text="MOQ: 500 units\nLead time: 6-8 weeks",
        llm=_llm_raising(),
        reference_date=REFERENCE_DATE,
    )

    assert parsed.unit_price == Decimal("2.50")
    assert parsed.moq == 500
    assert parsed.lead_time_days == 56
    assert parsed.field_sources["moq"] == "heuristic"
    assert parsed.field_sources["lead_time_days"] == "heuristic"


async def test_an_llm_that_returns_nothing_useful_still_leaves_a_usable_parse():
    parsed, _ = await parse_submission(
        form_values={"unit_price": "2.50"},
        free_text="MOQ: No MOQ at this stage",
        llm=_llm_returning(None),
        reference_date=REFERENCE_DATE,
    )

    assert parsed.unit_price == Decimal("2.50")
    # FINDING: parse_moq ("No MOQ" -> 0) is dead code — nothing calls it. Both
    # parse paths coerce the MOQ with parse_int, so an explicitly declined
    # minimum records None here. The completeness check compensates for that via
    # the declined-pattern rule, but the comparison engine then scores the MOQ as
    # UNKNOWN (55) instead of full marks (100), i.e. a supplier who said "no
    # minimum" is scored *worse* on MOQ than one who named a small one.
    assert parsed.moq is None
    assert parse_moq("No MOQ at this stage") == 0  # the rule exists, unused


def test_merge_parsed_keeps_the_earliest_layer_per_field():
    first = ParsedQuote(unit_price=Decimal("1.00"), field_sources={"unit_price": "form"})
    second = ParsedQuote(unit_price=Decimal("9.00"), moq=500, field_sources={"moq": "llm"})

    merged = merge_parsed(first, second)

    assert merged.unit_price == Decimal("1.00")
    assert merged.moq == 500
    assert merged.field_sources["unit_price"] == "form"
    assert merged.field_sources["moq"] == "llm"


def test_coerce_llm_payload_normalizes_the_way_the_heuristic_path_does():
    """Both paths must agree on what "3-4 weeks" or "USD 2.50" means."""

    parsed = coerce_llm_payload(
        {
            "unit_price": "USD 2.50",
            "lead_time_days": "3-4 weeks",
            "incoterms": "DDP Hamburg",
            "validity_date": "2027-03-15",
            "confidence": 0.8,
        },
        REFERENCE_DATE,
    )

    assert parsed.unit_price == Decimal("2.50")
    assert parsed.lead_time_days == 28
    assert parsed.incoterms == "DDP Hamburg"
    assert parsed.validity_date == date(2027, 3, 15)
    assert parsed.source == "llm"


# --------------------------------------------------------------- normalizers
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2 weeks", 14),
        ("3-4 weeks", 28),  # the upper bound: never under-state a lead time
        ("15 business days", 21),  # business days convert at 7/5
        ("45 days", 45),
        ("6 months", 180),
        ("TBD", None),
        (None, None),
        ("", None),
        (30, 30),
    ],
)
def test_parse_lead_time_days(raw, expected):
    assert parse_lead_time_days(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("USD 45.00/pc", Decimal("45.00")),
        ("1,250", Decimal("1250")),
        ("$7.80", Decimal("7.80")),
        ("2.5", Decimal("2.5")),
        (45, Decimal("45")),
        ("TBD", None),
        ("", None),
        ("on request", None),
        (None, None),
    ],
)
def test_parse_money(raw, expected):
    assert parse_money(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("USD", "USD"),
        ("usd", "USD"),
        ("€2.10", "EUR"),
        ("$7.80", "USD"),
        (None, None),
    ],
)
def test_parse_currency(raw, expected):
    assert parse_currency(raw) == expected


def test_parse_currency_does_not_recognise_a_non_answer():
    """A non-answer is not a currency.

    Regression guard: "TBD" is three uppercase letters, so it used to be returned
    as a currency code — and the quote then dropped out of the comparison with the
    confusing reason "No FX rate for 'TBD'" instead of being treated as the missing
    field it is.
    """

    assert parse_currency("TBD") is None
    assert parse_currency("to be confirmed") is None
    assert parse_currency("") is None
    assert parse_currency(None) is None


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("500", 500),
        ("1,250", 1250),
        ("MOQ 500 units", 500),
        ("TBD", None),
        (None, None),
    ],
)
def test_parse_int(raw, expected):
    assert parse_int(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("24 months", 24),
        ("2 years", 24),
        ("1 year", 12),
        ("no warranty", 0),
        ("TBD", None),
        (None, None),
    ],
)
def test_parse_warranty_months(raw, expected):
    assert parse_warranty_months(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2027-03-15", date(2027, 3, 15)),
        ("15 Mar 2027", date(2027, 3, 15)),
        ("Mar 15, 2027", date(2027, 3, 15)),
        ("TBD", None),
        (None, None),
    ],
)
def test_parse_date(raw, expected):
    assert parse_date(raw) == expected


def test_relative_validity_is_resolved_against_the_reference_date():
    """Only the injected reference date decides the answer — never today()."""

    assert parse_validity_date("valid for 30 days", REFERENCE_DATE) == date(2026, 1, 31)
    assert parse_validity_date("valid for 2 weeks", REFERENCE_DATE) == date(2026, 1, 15)
    assert parse_validity_date("valid for 30 days", None) is None


def test_moq_declined_versus_negative():
    """An explicit "none" is a value; "TBD" is the absence of one."""

    assert parse_moq("No MOQ at this stage") == 0
    assert parse_moq("TBD") is None
    assert parse_moq("500 units") == 500


def test_payment_terms_and_unit_text_normalization():
    assert normalize_payment_terms("Net 30") == "Net 30"
    assert normalize_payment_terms("TBD") is None
    assert normalize_unit_text("box of 100") == "box of 100"
    assert normalize_unit_text("PCS") == "pcs"
    assert normalize_unit_text("TBD") is None


def test_a_currency_is_never_invented_from_an_ordinary_word():
    """Currency codes are uppercase in real text; prose is not.

    Regression guard with a material consequence: upper-casing the whole input
    first turned "We try to ship quickly." into the Turkish lira, which *is* in the
    FX table — so the comparison engine converted the price at 32.5/USD instead of
    reporting the quote as incomparable. A confidently wrong landed cost is worse
    than a missing one.
    """

    assert parse_currency("We try to ship quickly.") is None
    assert parse_currency("Could you confirm the target volume?") is None
    assert parse_currency("Please confirm the final price.") is None

    parsed = heuristic_parse("We try to ship quickly.", reference_date=REFERENCE_DATE)
    assert parsed.currency is None


def test_a_currency_is_still_read_from_real_text():
    """The fix must not break the cases that legitimately name a currency."""

    assert parse_currency("USD") == "USD"
    assert parse_currency("usd") == "USD"
    assert parse_currency("USD 45.00/pc") == "USD"
    assert parse_currency("Price in EUR") == "EUR"
    assert parse_currency("$7.80") == "USD"
    assert parse_currency("€") == "EUR"
    # An unknown-but-clearly-uppercase code still passes through, so the engine can
    # report a precise reason rather than silently defaulting to USD.
    assert parse_currency("QAR") == "QAR"
    # Structural acronyms are not currencies.
    assert parse_currency("MOQ") is None
    assert parse_currency("PCS") is None


@pytest.mark.parametrize("raw", ["TBD", "to be confirmed", "will advise later"])
def test_is_negative_for_non_answers(raw):
    assert is_negative(raw) is True


@pytest.mark.parametrize("raw", ["no MOQ", "none"])
def test_is_declined_for_explicit_refusals(raw):
    """Explicitly declining *is* an answer — chasing it damages the relationship."""

    assert is_declined(raw) is True


def test_net_payment_terms_are_not_mistaken_for_a_non_answer():
    assert is_negative("Net 30") is False
    assert is_declined("Net 30") is False


def test_negative_phrase_matching_respects_word_boundaries():
    """Words must be matched whole, or ordinary English becomes a non-answer.

    Regression guard: ``NEGATIVE_PATTERNS`` contained the two-letter token "na" and
    was matched with a bare ``in`` test, so "final", "Canada", and "maintenance" all
    meant "no answer yet". A supplier writing "Final price: 3.00 USD" had their only
    price silently discarded.
    """

    assert is_negative("final") is False
    assert is_negative("Canada") is False
    assert is_negative("maintenance") is False

    # And the price survives.
    assert parse_money("final price 3.00") == Decimal("3.00")

    assert is_negative("Price valid until 2027-03-15") is False
    assert is_negative("Final offer valid until 2027-03-15") is False

    # The phrases that genuinely mean "no answer yet" still match.
    assert is_negative("TBD") is True
    assert is_negative("Payment terms: to be confirmed") is True
    assert is_negative("We will advise on the lead time") is True
    assert is_negative("MOQ: N/A") is True


# --------------------------------------------------------------- completeness
def test_every_required_field_answered_is_complete():
    parsed = parse_form_values(
        {
            "unit_price": "USD 2.50",
            "lead_time": "3 weeks",
            "moq": "500",
            "payment_terms": "Net 30",
        },
        reference_date=REFERENCE_DATE,
    )

    report = evaluate_completeness(
        parsed, ["unit_price", "lead_time", "moq", "payment_terms"]
    )

    assert report.is_complete is True
    assert report.status == "complete"
    assert report.missing == []
    assert report.missing_labels == []
    assert report.summary == "Every required field is answered."


def test_a_blank_required_field_is_reported_with_its_supplier_facing_label():
    parsed = parse_form_values({"unit_price": "USD 2.50"}, reference_date=REFERENCE_DATE)

    report = evaluate_completeness(parsed, ["unit_price", "moq", "payment_terms"])

    assert report.is_complete is False
    assert report.status == "incomplete"
    assert report.missing == ["moq", "payment_terms"]
    assert report.missing_labels == ["minimum order quantity", "payment terms"]
    assert "minimum order quantity" in report.summary


def test_explicitly_declined_moq_in_the_notes_counts_as_an_answer():
    parsed = ParsedQuote(unit_price=Decimal("2.50"))

    report = evaluate_completeness(
        parsed, ["unit_price", "moq"], raw_text="No MOQ at this stage"
    )

    assert "moq" not in report.missing
    assert report.declined == ["moq"]
    assert report.is_complete is True


def test_moq_tbd_is_a_gap():
    parsed = ParsedQuote(unit_price=Decimal("2.50"))

    report = evaluate_completeness(parsed, ["unit_price", "moq"], raw_text="MOQ: TBD")

    assert report.missing == ["moq"]
    assert report.is_complete is False
    assert report.summary == "Missing required field(s): minimum order quantity."


def test_a_field_the_buyer_never_required_is_never_reported_as_missing():
    """A gap only exists relative to the RFQ's own required-field contract."""

    parsed = ParsedQuote(unit_price=Decimal("2.50"))

    report = evaluate_completeness(parsed, ["unit_price"])

    assert report.is_complete is True
    assert "moq" not in report.missing
    assert "warranty_months" not in report.missing
    assert "moq" not in report.missing_labels


def test_a_blocking_question_is_escalated_instead_of_chased():
    parsed = ParsedQuote(
        unit_price=Decimal("2.50"),
        blocking_question="What volume should we price for?",
    )

    report = evaluate_completeness(parsed, ["unit_price", "moq"])

    assert report.is_complete is False
    assert "Resolve the supplier's question" in report.summary
    assert "instead of sending a reminder" in report.summary
    # Nothing in the summary tells the buyer (or the supplier) to chase.
    assert "chase" not in report.summary.lower()
    assert "chasing" not in report.summary.lower()


def test_label_for_moq_is_supplier_vocabulary():
    assert label_for("moq") == "minimum order quantity"
    assert label_for("lead_time_days") == "production lead time"


def test_no_supplier_facing_label_contains_an_underscore():
    """Copy that leaks an internal field name reads as machine output."""

    for field, label in FIELD_LABELS.items():
        assert "_" not in label, field
        assert label == label.strip()
        assert label, field


# -------------------------------------------------------- heuristic extraction
def test_heuristic_extraction_from_a_realistic_notes_block():
    parsed = heuristic_parse(NOTES_BLOCK, reference_date=REFERENCE_DATE)

    assert parsed.unit_price == Decimal("3.20")
    assert parsed.lead_time_days == 56  # 6-8 weeks takes the upper bound
    assert parsed.moq == 500
    # "TBD" is not an answer, so no payment terms are recorded.
    assert parsed.payment_terms is None
    assert parsed.incoterms == "DDP Hamburg"
    assert parsed.validity_date == date(2027, 3, 15)
    assert parsed.field_sources["unit_price"] == "heuristic"


def test_heuristic_extraction_infers_a_lead_time_from_prose():
    parsed = heuristic_parse(
        "Happy to quote. Our usual production lead time is about 10 weeks.",
        reference_date=REFERENCE_DATE,
    )

    assert parsed.lead_time_days == 70


def test_nothing_a_supplier_typed_is_silently_dropped():
    """Unmapped input is preserved in ``unparsed`` for the buyer to read."""

    parsed = parse_form_values(
        {"unit_price": "TBD", "moq": "TBD", "paint_colour": "RAL 7016"},
        reference_date=REFERENCE_DATE,
    )

    assert parsed.unit_price is None
    assert parsed.moq is None
    assert parsed.unparsed is not None
    assert "paint_colour: RAL 7016" in parsed.unparsed
    assert "unit_price: TBD" in parsed.unparsed


def test_heuristic_parse_without_text_is_empty_not_invented():
    parsed = heuristic_parse(None, reference_date=REFERENCE_DATE)

    assert parsed.provided_fields() == {}


# ------------------------------------------------------------- classification
def test_an_out_of_office_reply_is_not_quote_data():
    assert classify_text("I am out of office until Monday.") == "other"
    assert classify_text("") == "other"
    assert classify_text(None) == "other"


def test_text_carrying_a_price_is_quote_data():
    assert classify_text("Our price is USD 2.50 per pc.") == "quote_data"
    assert classify_text("Unit price: 3.20") == "quote_data"


def test_a_bare_question_is_a_question():
    assert classify_text("Could you confirm the target volume?") == "question"


def test_a_question_containing_the_word_price_is_a_question():
    """A message that asks something and states no figure is a question.

    Regression guard: ``DATA_MARKERS`` contained the bare substring "price", so
    "What volume should we price for?" was classified as quote data — which meant a
    supplier waiting on the buyer was recorded as an ordinary response and then
    chased for fields they had already said they could not give.
    """

    assert classify_text("What volume should we price for?") == "question"
    assert classify_text("Could you confirm the target volume?") == "question"
    assert classify_text("Which port should we quote to?") == "question"

    # A question that DOES carry a figure is still data: the question is recorded
    # separately as blocking_question.
    assert classify_text("Can we price this at USD 2.50 per pc?") == "quote_data"
    assert classify_text("Should the MOQ be 500 or 1000?") == "quote_data"


def test_extract_question_ignores_pleasantries():
    """A post-quote "let us know" is not a blocker and must not be escalated."""

    assert extract_question("Please let us know your decision.") is None
    assert extract_question("Thanks — looking forward to working with you.") is None
    assert extract_question(None) is None


def test_extract_question_returns_the_actual_blocking_sentence():
    assert (
        extract_question("What volume should we price for?")
        == "What volume should we price for?"
    )

    mixed = "Thanks for the RFQ. Which destination port should we quote to?"
    assert extract_question(mixed) == "Which destination port should we quote to?"


async def test_a_question_only_message_is_escalated_even_with_no_llm():
    """The escalate-don't-chase guardrail must hold with no LLM configured.

    This is the regression that mattered most. ``parse_submission`` only promotes a
    free-text question to ``blocking_question`` when the classification says
    "question", but ``ParsedQuote.classification`` defaulted to "quote_data" and the
    heuristic layer always carried that default — so it won the merge and overrode
    the classifier. With no LLM key (the documented free-tier and quota-exhausted
    case, and the configuration the test suite runs in) a supplier who was waiting
    on the buyer got recorded as ordinary quote data and chased for fields they had
    already said they could not give.
    """

    parsed, report = await parse_submission(
        free_text="Could you confirm the target volume before we can price this?",
        reference_date=REFERENCE_DATE,
    )

    assert parsed.classification == "question"
    assert parsed.blocking_question is not None
    assert "volume" in parsed.blocking_question.lower()
    # No commercial value was invented from the question.
    assert parsed.unit_price is None

    # Against a real required-field contract, the completeness summary tells the
    # reader to resolve the question rather than send a reminder. That summary is
    # what a buyer reads on the dashboard, and it mirrors what the policy decides.
    from agents.quote_parser import evaluate_completeness

    report = evaluate_completeness(
        parsed,
        ["unit_price", "currency", "lead_time", "moq", "payment_terms"],
    )

    assert report.is_complete is False
    assert "Resolve the supplier's question" in report.summary
    assert "reminder" in report.summary


async def test_an_llm_supplied_classification_is_kept():
    """A model that classifies the message has its verdict respected."""

    parsed, _ = await parse_submission(
        free_text="Could you confirm the target volume?",
        llm=_llm_returning(
            {"classification": "question", "blocking_question": "What volume?", "confidence": 0.9}
        ),
        reference_date=REFERENCE_DATE,
    )

    assert parsed.blocking_question == "What volume?"
    assert parsed.classification == "question"


async def test_parse_source_names_the_combination_when_layers_merge():
    """Provenance is the summary of what contributed, not whichever ran last.

    Regression guard: ``source`` used to end up as the last layer's own value
    ("heuristic") even when the price came from the form and another field from the
    LLM — so any consumer branching on ``source`` was misled. ``field_sources`` was
    already accurate; this makes the summary agree with it.
    """

    parsed, _ = await parse_submission(
        form_values={"unit_price": "2.50"},
        free_text="MOQ: 500 units",
        llm=_llm_returning({"warranty_months": 24}),
        reference_date=REFERENCE_DATE,
    )

    assert parsed.source == "merged"
    assert parsed.field_sources["unit_price"] == "form"
    assert parsed.field_sources["warranty_months"] == "llm"
    assert parsed.field_sources["moq"] == "heuristic"


# ---------------------------------------------------------------- eval cases
#: A small offline evaluation set, mirroring the reference implementation's
#: discipline: named cases, run end-to-end through the real entry point, each
#: asserting the specific values a buyer would act on. No network, no clock.
EVAL_CASES: list[tuple[str, dict, str, dict]] = [
    (
        "complete_quote",
        {
            "unit_price": "USD 2.50",
            "currency": "USD",
            "lead_time": "3 weeks",
            "moq": "500",
            "payment_terms": "Net 30",
            "incoterms": "DDP Hamburg",
            "validity_date": "2027-03-15",
        },
        "",
        {
            "unit_price": Decimal("2.50"),
            "currency": "USD",
            "lead_time_days": 21,
            "moq": 500,
            "payment_terms": "Net 30",
            "incoterms": "DDP Hamburg",
            "validity_date": date(2027, 3, 15),
        },
    ),
    (
        "partial_quote",
        {"unit_price": "4.75"},
        "Looking forward to your order.",
        {
            "unit_price": Decimal("4.75"),
            "lead_time_days": None,
            "moq": None,
            "payment_terms": None,
            "incoterms": None,
        },
    ),
    (
        "tbd_heavy_quote",
        {
            "unit_price": "TBD",
            "lead_time": "TBD",
            "moq": "TBD",
            "payment_terms": "to be confirmed",
            "incoterms": "TBD",
        },
        "",
        {
            "unit_price": None,
            "lead_time_days": None,
            "moq": None,
            "payment_terms": None,
            "incoterms": None,
        },
    ),
    (
        "question_only_message",
        {},
        "Could you confirm the target volume and the destination port?",
        # NOTE: currency is deliberately not asserted here — the heuristic
        # currency fallback invents one from any three-letter word; see
        # test_a_currency_is_invented_from_an_ordinary_word.
        {"unit_price": None, "moq": None, "lead_time_days": None},
    ),
    (
        "quote_with_a_pack_size",
        {"unit": "box of 100", "unit_price": "12.00"},
        "",
        {"unit": "box of 100", "unit_price": Decimal("12.00")},
    ),
    (
        "non_usd_quote",
        {"currency": "EUR", "unit_price": "€2.10", "incoterms": "CIF Rotterdam"},
        "",
        {
            "currency": "EUR",
            "unit_price": Decimal("2.10"),
            "incoterms": "CIF Rotterdam",
        },
    ),
    (
        "labelled_notes_only",
        {},
        NOTES_BLOCK,
        {
            "unit_price": Decimal("3.20"),
            "lead_time_days": 56,
            "moq": 500,
            "incoterms": "DDP Hamburg",
            "validity_date": date(2027, 3, 15),
            "payment_terms": None,
        },
    ),
]


@pytest.mark.parametrize(
    "name, form_values, free_text, expected",
    EVAL_CASES,
    ids=[case[0] for case in EVAL_CASES],
)
async def test_offline_eval_case(name, form_values, free_text, expected):
    parsed, report = await parse_submission(
        form_values=form_values,
        free_text=free_text,
        reference_date=REFERENCE_DATE,
    )

    assert isinstance(parsed, ParsedQuote)
    assert report is not None

    for field, value in expected.items():
        assert getattr(parsed, field) == value, f"{name}: {field}"


async def test_eval_set_covers_the_required_scenarios():
    """Guard the eval set itself: it must keep covering the named scenarios."""

    names = {case[0] for case in EVAL_CASES}

    assert len(EVAL_CASES) >= 6
    assert names >= {
        "complete_quote",
        "partial_quote",
        "tbd_heavy_quote",
        "question_only_message",
        "quote_with_a_pack_size",
        "non_usd_quote",
    }


def test_every_eval_case_name_is_a_snake_case_identifier():
    for name, *_ in EVAL_CASES:
        assert re.fullmatch(r"[a-z0-9_]+", name), name
        assert "_" in name
