"""Services comparison — taxonomies, the nine criteria, GST, rate bases, ranking.

The suite's other modules pin ``procurement_type="goods"`` because that is what
they were written for. This one covers the product's actual subject: building
maintenance and minor works, priced in SGD against a rate basis, differentiated by
an SLA and by the licences a contractor holds.

Everything here is pure — no database, no FastAPI, no network — so it is fast and
deterministic, and every money assertion is a :class:`~decimal.Decimal`.

The properties protected, in the order they would hurt:

* **the service weights are the ones applied.** ``ComparisonInput.weights`` once
  defaulted to the goods set, so the per-type fallback never fired and a
  maintenance RFQ was scored on MOQ and Incoterms while its SLA was ignored;
* **a quote missing a required licence cannot win on price.** It stays visible and
  rankable, with the composite capped, because cheap and unlicensed is the most
  expensive outcome available to a buyer;
* **every quote in an RFQ is costed on the same tax basis.** Ranking a
  GST-inclusive quote against a tax-exclusive one is how the wrong supplier wins;
* **a rate basis is not a unit of measure.** "per job" and "per pcs" are different
  bases and must never be treated as comparable, while "per job" and "lump sum" are
  the same basis and must never be excluded over a choice of words.
"""

from datetime import date
from decimal import Decimal

import pytest

from agents.quote_parser.completeness import label_for
from agents.quote_parser.normalize import parse_accreditations
from agents.quote_parser.normalize import parse_percent
from agents.quote_parser.normalize import parse_response_time_hours
from agents.quote_parser.normalize import normalize_unit_text
from comparison import ComparisonInput
from comparison import QuoteInput
from comparison import comparison_to_csv
from comparison import normalize_weights
from comparison import run_comparison
from comparison.schemas import CRITERIA
from comparison.schemas import DEFAULT_WEIGHTS_GOODS
from comparison.schemas import DEFAULT_WEIGHTS_SERVICE
from comparison.schemas import default_weights
from comparison.score import UNKNOWN_SCORE
from comparison.score import format_percent
from comparison.score import missing_accreditations
from comparison.score import score_compliance
from comparison.score import score_response_time
from comparison.units import display_rate_basis
from comparison.units import normalize_unit
from comparison.units import price_basis_multiplier
from app.features.rfq import taxonomy

TODAY = date(2026, 6, 1)

LEW = "EMA Licensed Electrical Worker (LEW)"
BIZSAFE = "bizSAFE Level 3"

SERVICE_WEIGHTS = {
    "price": 0.40,
    "response_time": 0.15,
    "lead_time": 0.05,
    "compliance": 0.10,
    "payment_terms": 0.05,
    "moq": 0.00,
    "validity": 0.05,
    "warranty": 0.05,
    "risk": 0.15,
}


# --------------------------------------------------------------------- helpers
def _quote(quote_id: int = 1, supplier_name: str = "Acme M&E", **overrides) -> QuoteInput:
    """A complete, compliant Singapore maintenance quote unless overridden."""

    fields = {
        "quote_id": quote_id,
        "supplier_name": supplier_name,
        "currency": "SGD",
        "unit": "per point",
        "unit_price": Decimal("162.00"),
        "response_time_hours": 2,
        "callout_charge": Decimal("120.00"),
        "payment_terms": "Net 30",
        "validity_date": date(2027, 6, 30),
        "completeness": "complete",
        "compliance_accreditations": [LEW, BIZSAFE],
    }
    fields.update(overrides)

    return QuoteInput(**fields)


def _run(quotes, *, quantity: int = 24, **payload):
    """A services RFQ in SGD with a 4-hour SLA and two required licences."""

    fields = {
        "unit": "per point",
        "base_currency": "SGD",
        "procurement_type": "service",
        "gst_rate": Decimal("9"),
        "required_accreditations": [LEW, BIZSAFE],
    }
    fields.update(payload)

    return run_comparison(
        ComparisonInput(
            rfq_id=1,
            rfq_number="RFQ-2026-ACMV",
            item_name="Corridor lighting replacement",
            quantity=quantity,
            quotes=list(quotes),
            today=TODAY,
            **fields,
        )
    )


# =========================================================== taxonomies/weights
def test_the_domain_offers_the_services_a_facilities_team_actually_buys():
    """The categories are the customer's own vocabulary, not a generic list."""

    for expected in (
        "Building Maintenance & Handyman",
        "Electrical Minor Works",
        "Mechanical Minor Works",
        "Plumbing & Sanitary Minor Works",
        "Painting & Decorating",
        "ACMV / Air-Conditioning",
    ):
        assert expected in taxonomy.SERVICE_CATEGORIES

    assert taxonomy.SERVICE_CATEGORIES[-1] == "Other Services"
    assert "Fasteners" not in taxonomy.SERVICE_CATEGORIES

    # Goods keep their own, smaller list rather than sharing the services one.
    assert "Spare Parts & Consumables" in taxonomy.GOODS_CATEGORIES
    assert not set(taxonomy.GOODS_CATEGORIES) & set(taxonomy.SERVICE_CATEGORIES)


def test_a_rate_basis_is_what_a_service_price_is_quoted_against():
    """"per point" and "lump sum" are the services analogue of a unit of measure."""

    for basis in ("per job", "per visit", "per hour", "per day", "per point", "lump sum"):
        assert basis in taxonomy.SERVICE_RATE_BASES

    assert taxonomy.GOODS_UNITS == ("pcs", "set", "box", "kg", "m", "roll", "sheet", "lot")
    assert "pcs" not in taxonomy.SERVICE_RATE_BASES


def test_the_two_procurement_types_require_different_fields():
    """A services RFQ must not ask for Incoterms; a goods RFQ must not ask for an SLA."""

    service = taxonomy.default_required_fields("service")
    goods = taxonomy.default_required_fields("goods")

    assert service == [
        "unit_price",
        "currency",
        "unit",
        "response_time",
        "payment_terms",
        "validity_date",
    ]

    # Deliberately absent: nothing is being shipped, and a minimum callout is a
    # charge rather than a quantity gate.
    assert "incoterms" not in service
    assert "moq" not in service
    assert "lead_time" not in service

    # Goods are untouched by the pivot.
    assert goods == [
        "unit_price",
        "currency",
        "lead_time",
        "moq",
        "payment_terms",
        "incoterms",
        "validity_date",
    ]

    assert taxonomy.default_required_fields(None) == service
    assert taxonomy.default_required_fields("goods") == goods


def test_there_are_nine_criteria_and_each_type_weights_them_differently():
    assert CRITERIA == (
        "price",
        "response_time",
        "lead_time",
        "compliance",
        "payment_terms",
        "moq",
        "validity",
        "warranty",
        "risk",
    )

    assert default_weights("service") == SERVICE_WEIGHTS
    assert default_weights("service") == DEFAULT_WEIGHTS_SERVICE
    assert default_weights("goods") == DEFAULT_WEIGHTS_GOODS

    # A weight set that does not sum to 1 silently rescales every composite score.
    for weights in (DEFAULT_WEIGHTS_SERVICE, DEFAULT_WEIGHTS_GOODS):
        assert sum(weights.values()) == pytest.approx(1.0)
        assert set(weights) == set(CRITERIA)

    # The two sets are genuinely different, which is the whole point.
    assert default_weights("service")["response_time"] == 0.15
    assert default_weights("goods")["response_time"] == 0.0
    assert default_weights("service")["moq"] == 0.0
    assert default_weights("goods")["moq"] == 0.05


def test_the_library_default_is_goods_so_existing_callers_do_not_silently_rewrite():
    """The engine's own default stays `goods`; the app's product default is `service`.

    Silently re-weighting every existing caller's comparison would be a worse
    failure than requiring the new caller to say what it is buying.
    """

    assert ComparisonInput(rfq_id=1).procurement_type == "goods"
    assert taxonomy.DEFAULT_PROCUREMENT_TYPE == "service"


def test_an_empty_weight_map_falls_back_to_the_procurement_types_own_weights():
    """The defect: a truthy goods default meant the fallback never fired.

    ``ComparisonInput.weights`` used to default to the goods dictionary, so
    ``normalize_weights(weights, fallback=...)`` short-circuited on a truthy value
    and a maintenance RFQ was scored on MOQ and Incoterms while its 4-hour SLA was
    weighted zero.
    """

    assert ComparisonInput(rfq_id=1).weights == {}

    assert normalize_weights({}, fallback=SERVICE_WEIGHTS) == SERVICE_WEIGHTS
    assert normalize_weights(None, fallback=SERVICE_WEIGHTS) == SERVICE_WEIGHTS
    assert normalize_weights({}, fallback=DEFAULT_WEIGHTS_GOODS) == DEFAULT_WEIGHTS_GOODS


def test_the_service_weights_are_the_ones_actually_applied_to_the_composite():
    """Asserted against the arithmetic, and against the goods set it is not."""

    result = _run([_quote()])
    scored = result.results[0]

    assert result.weights == SERVICE_WEIGHTS

    as_service = sum(scored.scores[key] * SERVICE_WEIGHTS[key] for key in CRITERIA)
    as_goods = sum(scored.scores[key] * DEFAULT_WEIGHTS_GOODS[key] for key in CRITERIA)

    # The quote states no MOQ, so it only differs between the two where the weights
    # do: the SLA (weighted 0 for goods) and compliance.
    assert scored.scores["response_time"] > 0
    assert as_service != pytest.approx(as_goods)
    assert scored.composite_score == pytest.approx(as_service, abs=0.01)


# ============================================================ response time/SLA
@pytest.mark.parametrize(
    "hours, expected",
    [
        (None, 55.0),   # a gap to chase, not evidence of bad service
        (0, 100.0),
        (2, 100.0),
        (4, 92.0),
        (8, 82.0),
        (24, 62.0),     # next business day
        (48, 45.0),
        (72, 32.0),
        (168, 15.0),
        (336, 5.0),     # a fortnight, and the floor
        (1000, 5.0),    # beyond the last anchor, clamped rather than extrapolated
    ],
)
def test_response_time_is_scored_on_a_steep_curve(hours, expected):
    """Two hours and twenty-four hours are a different kind of service."""

    assert score_response_time(hours) == expected


def test_an_unstated_sla_scores_neutral_and_raises_a_flag():
    """Missing is not the same as bad — otherwise a chaseable gap looks like a bad bid."""

    scored = _run([_quote(response_time_hours=None)]).results[0]

    assert scored.scores["response_time"] == UNKNOWN_SCORE
    assert any("No response time (SLA) stated" in flag for flag in scored.risk_flags)


def test_a_response_time_beyond_one_business_day_is_flagged():
    slow = _run([_quote(response_time_hours=48)]).results[0]

    assert any("exceeds one business day" in flag for flag in slow.risk_flags)

    prompt = _run([_quote(response_time_hours=4)]).results[0]

    assert not any("exceeds one business day" in flag for flag in prompt.risk_flags)


# ===================================================== compliance/accreditations
def test_compliance_is_full_marks_when_the_buyer_required_nothing():
    """Absence of a requirement is not a failure to meet it."""

    assert score_compliance([LEW], []) == 100.0
    assert score_compliance([LEW], None) == 100.0

    # Nothing required and nothing claimed is the neutral value, not zero.
    assert score_compliance([], []) == UNKNOWN_SCORE
    assert score_compliance(None, None) == UNKNOWN_SCORE


def test_compliance_is_proportional_but_zero_when_nothing_required_is_held():
    """"Did not answer" and "does not hold the licence" are different problems."""

    assert score_compliance([LEW, BIZSAFE], [LEW, BIZSAFE]) == 100.0
    assert score_compliance([LEW], [LEW, BIZSAFE]) == 50.0
    assert score_compliance([], [LEW, BIZSAFE]) == 0.0

    # Case and padding must not decide whether a contractor is licensed.
    assert score_compliance(["  ema licensed electrical worker (lew) "], [LEW]) == 100.0


def test_missing_accreditations_returns_the_required_items_verbatim():
    assert missing_accreditations([LEW], [LEW, BIZSAFE]) == [BIZSAFE]
    assert missing_accreditations([LEW, BIZSAFE], [LEW]) == []
    assert missing_accreditations(None, []) == []
    assert missing_accreditations([LEW], []) == []


def test_a_quote_missing_a_required_licence_is_capped_and_named():
    """Cheap and unlicensed is the most expensive outcome available to a buyer.

    The quote stays in ``results`` and keeps a rank — it is never silently dropped,
    because the buyer may want to see it — but it cannot win on price.
    """

    licensed = _quote(
        quote_id=1,
        supplier_name="Licensed",
        unit_price=Decimal("162.00"),
    )
    unlicensed = _quote(
        quote_id=2,
        supplier_name="Cheap but unlicensed",
        unit_price=Decimal("50.00"),          # dramatically cheaper
        compliance_accreditations=[BIZSAFE],   # missing the LEW
    )

    result = _run([licensed, unlicensed])

    cheap = result.by_id(2)

    assert cheap.comparable is True
    assert cheap.rank is not None
    assert cheap.missing_accreditations == [LEW]
    assert cheap.composite_score <= 25.0
    assert cheap.scores["compliance"] == 50.0

    assert result.recommended_quote_id == 1

    assert any(
        "Does not hold required accreditation" in flag for flag in cheap.risk_flags
    )


def test_a_quote_missing_every_required_licence_scores_zero_on_compliance():
    unscrupulous = _quote(compliance_accreditations=[])

    scored = _run([unscrupulous]).results[0]

    assert scored.scores["compliance"] == 0.0
    assert scored.missing_accreditations == [LEW, BIZSAFE]
    assert scored.composite_score <= 25.0


def test_the_cap_does_not_apply_when_the_buyer_required_no_accreditations():
    """A goods RFQ, or a buyer who did not ask, must not be capped by this rule."""

    scored = _run([_quote()], required_accreditations=[]).results[0]

    assert scored.missing_accreditations == []
    assert scored.composite_score > 25.0


def test_the_recommendation_states_the_compliance_problem_in_bold():
    """When the capped quote is still the leader, the buyer must be told why.

    Every quote here is unlicensed, so the capped one wins on price. That is exactly
    the situation the bold block exists for: the buyer is about to read a
    recommendation for work that may not lawfully proceed.
    """

    dearer = _quote(quote_id=1, supplier_name="Alpha", unit_price=Decimal("200.00"))
    cheaper = _quote(quote_id=2, supplier_name="Beta", unit_price=Decimal("20.00"))

    for quote in (dearer, cheaper):
        quote.compliance_accreditations = []

    result = _run([dearer, cheaper])

    assert result.recommended_quote_id == 2

    rationale = result.rationale

    assert "**Beta does not hold" in rationale
    assert LEW in rationale
    assert "score is capped" in rationale
    assert "lawfully" in rationale


# ======================================================================== money
def test_the_callout_charge_enters_the_landed_cost():
    """The most common hidden cost in a maintenance quote, added rather than ignored."""

    scored = _run([_quote()]).results[0]
    breakdown = scored.breakdown

    assert breakdown.goods == Decimal("3888.00")     # 162.00 x 24 points
    assert breakdown.callout == Decimal("120.00")
    assert breakdown.taxes == Decimal("360.72")      # 9% of 3888 + 120
    assert breakdown.subtotal == Decimal("4368.72")
    assert breakdown.total == Decimal("4368.72")
    assert scored.total_base == Decimal("4368.72")


def test_no_callout_charge_is_flagged_because_it_is_the_classic_surprise():
    scored = _run([_quote(callout_charge=None)]).results[0]

    assert scored.breakdown.callout == Decimal("0.00")
    assert any("No callout/attendance charge stated" in f for f in scored.risk_flags)


def test_a_materials_markup_above_twenty_percent_is_flagged():
    greedy = _run([_quote(materials_markup_pct=Decimal("35"))]).results[0]

    assert any("Materials markup of 35%" in flag for flag in greedy.risk_flags)

    ordinary = _run([_quote(materials_markup_pct=Decimal("12"))]).results[0]

    assert not any("Materials markup" in flag for flag in ordinary.risk_flags)


@pytest.mark.parametrize(
    "quote_rate, rfq_rate, explicit_tax, expected_tax, derived",
    [
        # The supplier stated a rate: that rate applies.
        (Decimal("9"), Decimal("9"), None, Decimal("360.72"), True),
        (Decimal("8.5"), Decimal("9"), None, Decimal("340.68"), True),
        # An explicit 0 is an answer — a supplier who is not GST-registered keeps it.
        (Decimal("0"), Decimal("9"), None, Decimal("0.00"), False),
        # An explicit amount is never double-counted.
        (None, Decimal("9"), Decimal("120.00"), Decimal("120.00"), False),
        # Neither stated: the RFQ's own rate applies, so every quote in the RFQ is
        # costed on the same basis.
        (None, Decimal("9"), None, Decimal("360.72"), True),
        # No rate anywhere: figures stay tax-exclusive rather than being invented.
        (None, None, None, Decimal("0.00"), False),
    ],
)
def test_gst_resolution_rules(quote_rate, rfq_rate, explicit_tax, expected_tax, derived):
    scored = _run(
        [_quote(gst_rate=quote_rate, taxes=explicit_tax)],
        gst_rate=rfq_rate,
    ).results[0]

    assert scored.breakdown.taxes == expected_tax
    assert scored.breakdown.tax_derived_from_rate is derived


def test_derived_gst_is_disclosed_rather_than_silently_added():
    scored = _run([_quote()]).results[0]

    assert any(
        "GST added at 9% from the rate stated on the quote" in flag
        for flag in scored.risk_flags
    )


def test_a_rate_is_written_the_same_way_wherever_it_came_from():
    """``Decimal('9')`` and ``Decimal('9.00')`` used to render as "9%" and "9.00%".

    A rate parsed from a submission is the first, and the same figure after a round
    trip through the ``Numeric(5, 2)`` column is the second, so one screen could show
    two spellings of one number.
    """

    assert format_percent(Decimal("9")) == "9"
    assert format_percent(Decimal("9.00")) == "9"
    assert format_percent(Decimal("8.50")) == "8.5"
    assert format_percent(9.0) == "9"
    assert format_percent(Decimal("0.00")) == "0"
    assert format_percent(None) == "0"

    # Never scientific notation, which `Decimal.normalize()` would have produced.
    assert format_percent(Decimal("1E+2")) == "100"

    # And the flag itself is stable across both spellings.
    from_decimal_9 = _run([_quote(gst_rate=Decimal("9"))]).results[0]
    from_decimal_900 = _run([_quote(gst_rate=Decimal("9.00"))]).results[0]

    gst_flags = [
        flag
        for flag in from_decimal_9.risk_flags
        if flag.startswith("GST added at")
    ]
    other = [
        flag
        for flag in from_decimal_900.risk_flags
        if flag.startswith("GST added at")
    ]

    assert gst_flags == other
    assert gst_flags and "at 9%" in gst_flags[0]


def test_a_foreign_currency_service_quote_is_converted_and_rounded_to_cents():
    """A converted add-on came back with 28 decimal places in the API."""

    offshore = _quote(
        currency="MYR",
        unit_price=Decimal("620.00"),
        callout_charge=Decimal("350.00"),
        gst_rate=None,
    )

    scored = _run([offshore]).results[0]
    breakdown = scored.breakdown

    assert breakdown.fx_from == "MYR"
    assert breakdown.fx_to == "SGD"
    # 620 x 24 MYR at the table rate, then the callout converted separately.
    for money_field in ("goods", "callout", "taxes", "subtotal", "total"):
        value = getattr(breakdown, money_field)
        assert value == value.quantize(Decimal("0.01")), money_field


# ==================================================================== rate bases
def test_whole_scope_bases_are_the_same_basis_under_different_names():
    """"lump sum" against a "per job" RFQ is not a reason to exclude a supplier."""

    for quoted in ("per job", "lump sum", "lump-sum", "lumpsum", "per service", "lot"):
        multiplier, warning = price_basis_multiplier(quoted, "per job")

        assert multiplier == 1.0
        assert warning is None, quoted


@pytest.mark.parametrize(
    "basis",
    ["per visit", "per hour", "per day", "per point", "per month"],
)
def test_each_measured_service_basis_is_its_own_basis(basis):
    """A per-hour rate and a lump sum cannot be ranked without knowing the effort."""

    assert normalize_unit(basis).canonical == normalize_unit(basis).canonical
    assert price_basis_multiplier(basis, basis) == (1.0, None)

    # And none of them is the whole-scope basis.
    assert normalize_unit(basis).canonical != normalize_unit("per job").canonical


def test_different_service_bases_are_excluded_naming_the_buyers_own_wording():
    """The message has to tell the buyer what to ask the supplier to change."""

    multiplier, warning = price_basis_multiplier("per hour", "per point")

    assert multiplier == 1.0
    assert warning is not None
    assert "excluded" in warning
    assert "per hour" in warning
    assert "per point" in warning
    # Not the internal canonical codes.
    assert "'hour'" not in warning
    assert "'point'" not in warning


def test_a_per_job_price_is_not_comparable_with_a_per_piece_rfq():
    multiplier, warning = price_basis_multiplier("per job", "pcs")

    assert multiplier == 1.0
    assert warning is not None and "excluded" in warning
    assert "per job" in warning
    assert "pcs" in warning


def test_square_metres_are_not_linear_metres():
    """"per sq m" was read as per metre, so an area rate became a length rate."""

    assert normalize_unit("per sq m").canonical == "sqm"
    assert normalize_unit("per sq.m").canonical == "sqm"
    assert normalize_unit("per sqm").canonical == "sqm"
    assert normalize_unit("square metre").canonical == "sqm"

    # The two spellings are the same basis, so neither supplier is excluded.
    assert price_basis_multiplier("per sq m", "per sqm") == (1.0, None)

    # A genuine area/length mismatch is still caught.
    _, warning = price_basis_multiplier("per metre", "per sqm")

    assert warning is not None and "excluded" in warning


def test_excluded_quotes_stay_in_the_results_with_a_reason():
    """No supplier is ever silently dropped from a comparison."""

    comparable = _quote(quote_id=1, supplier_name="Comparable")
    wrong_basis = _quote(quote_id=2, supplier_name="Wrong basis", unit="per hour")

    result = _run([comparable, wrong_basis])

    assert len(result.results) == 2

    excluded = result.by_id(2)

    assert excluded.comparable is False
    assert excluded.rank is None
    assert "per hour" in excluded.exclusion_reason
    assert result.recommended_quote_id == 1


# ====================================================================== ranking
def test_a_complete_quote_outranks_a_cheaper_incomplete_one():
    """An ordering rule, not a score penalty — and the buyer is told why."""

    complete = _quote(quote_id=1, supplier_name="Complete", unit_price=Decimal("162.00"))
    incomplete = _quote(
        quote_id=2,
        supplier_name="Incomplete",
        unit_price=Decimal("90.00"),
        completeness="incomplete",
        missing_fields=["payment_terms", "validity_date"],
        payment_terms=None,
        validity_date=None,
    )

    result = _run([complete, incomplete])

    assert result.by_id(1).rank == 1
    assert result.by_id(2).rank == 2
    assert result.recommended_quote_id == 1

    assert "Incomplete" in result.rationale
    assert "incomplete" in result.rationale.lower()


def test_an_incomplete_quote_is_still_scored_and_still_visible():
    """Docked, never hidden: the buyer may want to see where it would land."""

    scored = _run(
        [
            _quote(
                quote_id=2,
                completeness="incomplete",
                missing_fields=["payment_terms"],
            )
        ]
    ).results[0]

    assert scored.comparable is True
    assert scored.rank == 1
    assert scored.composite_score > 0
    assert scored.scores["price"] == 100.0
    assert scored.incompleteness_note is not None
    assert "payment_terms" in scored.incompleteness_note


def test_the_rationale_names_the_criteria_a_services_rfq_was_ranked_on():
    """A fixed goods sentence told the buyer MOQ decided their award."""

    rationale = _run([_quote()]).rationale.split("\n")[0]

    assert "response time (SLA)" in rationale
    assert "mobilisation time" in rationale
    assert "accreditations and licences" in rationale

    # The goods vocabulary must not appear as if it were scored.
    assert "minimum order quantity" not in rationale
    assert "warranty" not in rationale.replace("defect liability", "")


def test_a_cheaper_non_compliant_quote_is_explained_not_merely_outranked():
    licensed = _quote(quote_id=1, supplier_name="Licensed", unit_price=Decimal("162.00"))
    unlicensed = _quote(
        quote_id=2,
        supplier_name="Unlicensed",
        unit_price=Decimal("20.00"),
        compliance_accreditations=[],
    )

    rationale = _run([licensed, unlicensed]).rationale

    assert "Unlicensed is cheapest on landed cost" in rationale
    assert "does not hold" in rationale


def test_the_comparison_always_explains_itself():
    result = _run([_quote()])

    assert result.rationale.strip()
    assert "human approval" in result.rationale
    assert result.is_conclusive is True


def test_the_service_csv_export_carries_the_rate_basis_it_was_quoted_on():
    result = _run([_quote()])

    rows = list(csv_read(comparison_to_csv(result)))

    assert rows[0]["Supplier"] == "Acme M&E"
    assert rows[0]["Quoted unit"] == "per point"
    assert rows[0]["Quoted currency"] == "SGD"
    assert rows[0]["Currency (normalized)"] == "SGD"
    assert rows[0]["Taxes"] == "360.72"
    assert rows[0]["Completeness"] == "complete"


def csv_read(text: str):
    """Rows of the comparison table, skipping the context block above it."""

    import csv
    import io

    start = text.find("Rank,Supplier")

    assert start != -1, text[:400]

    return csv.DictReader(io.StringIO(text[start:]))


# ===================================================================== parsers
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("4 hours", 4),
        ("within 2 hrs", 2),
        ("2-4 hours", 4),          # the upper bound: nobody committed to two
        ("same day", 8),
        ("next business day", 24),
        ("2 working days", 48),
        ("1 business day", 24),
        ("30 minutes", 1),         # 0 would read as instantaneous
        ("24/7", 4),
        ("within 48 hours", 48),
        ("48", 48),                # a bare number in a labelled field means hours
        (4, 4),
        ("TBD", None),
        ("will advise", None),
        ("ASAP", None),
        (None, None),
        ("", None),
    ],
)
def test_a_supplier_writes_an_sla_in_words_and_it_becomes_hours(raw, expected):
    assert parse_response_time_hours(raw) == expected


def test_an_attendance_promise_is_not_read_as_a_production_schedule():
    """The two are different questions; a lead-time parser would answer the wrong one."""

    assert parse_response_time_hours("2 weeks") == 336
    assert parse_lead_time_days_equivalent() == 14


def parse_lead_time_days_equivalent() -> int:
    from agents.quote_parser.normalize import parse_lead_time_days

    return parse_lead_time_days("2 weeks")


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("9%", Decimal("9")),
        ("9", Decimal("9")),
        ("0.09", Decimal("9.00")),      # a fraction, not a percentage
        ("GST 9%", Decimal("9")),
        ("15% markup", Decimal("15")),
        (9, Decimal("9")),
        (0.09, Decimal("9.00")),
        ("none", Decimal("0")),
        ("0", Decimal("0")),
        (1, Decimal("1")),              # 1 stays 1%, not 100%
        ("TBD", None),
        (None, None),
        ("999", None),                  # outside 0..100 is not a rate
    ],
)
def test_a_percentage_is_read_the_way_a_person_writes_it(raw, expected):
    assert parse_percent(raw) == expected


def test_accreditations_split_on_separators_but_never_inside_a_credential():
    """A false positive here would invent a licence the supplier never claimed."""

    assert parse_accreditations(f"{LEW}, {BIZSAFE}; ISO 9001") == [LEW, BIZSAFE, "ISO 9001"]
    assert parse_accreditations("ISO 9001 | ISO 14001") == ["ISO 9001", "ISO 14001"]

    # "&" and "/" appear INSIDE real credentials and must not split them.
    assert parse_accreditations("Lift & Escalator (BCA Permit Holder)") == [
        "Lift & Escalator (BCA Permit Holder)"
    ]
    assert parse_accreditations(["LEW", "lew", " bizSAFE "]) == ["LEW", "bizSAFE"]
    assert parse_accreditations("none") == []
    assert parse_accreditations("TBD") == []
    assert parse_accreditations("") == []
    assert parse_accreditations(None) == []


def test_a_rate_basis_keeps_the_words_the_supplier_used():
    """"per point" collapsed to "point", so the buyer read "162.00 service"."""

    assert normalize_unit_text("per job") == "per job"
    assert normalize_unit_text("lump sum") == "lump sum"
    assert normalize_unit_text("per visit") == "per visit"
    assert normalize_unit_text("per point") == "per point"
    assert normalize_unit_text("per sq m") == "sqm"

    # Goods behaviour is untouched by that change.
    assert normalize_unit_text("PCS") == "pcs"
    assert normalize_unit_text("kg") == "kg"
    assert normalize_unit_text("box of 100") == "box of 100"
    assert normalize_unit_text("TBD") is None


def test_a_stored_canonical_basis_is_displayed_as_a_phrase():
    """A quote stored before this fix still has to render readably."""

    assert display_rate_basis("point") == "per point"
    assert display_rate_basis("service") == "per job"
    assert display_rate_basis("visit") == "per visit"
    assert display_rate_basis("month") == "per month"

    # A real unit of measure is returned as its canonical code.
    assert display_rate_basis("PCS") == "pcs"
    assert display_rate_basis("per sq m") == "sqm"
    assert display_rate_basis(None, fallback="per job") == "per job"


def test_supplier_labels_follow_what_is_being_bought():
    """A plumbing contractor should not be asked for a production lead time."""

    assert label_for("moq", "service") == "minimum callout charge"
    assert label_for("moq", "goods") == "minimum order quantity"

    assert label_for("lead_time", "service") == "mobilisation time"
    assert label_for("lead_time_days", "service") == "mobilisation time"
    assert label_for("lead_time_days", "goods") == "production lead time"

    assert label_for("unit", "service") == "rate basis"
    assert label_for("unit", "goods") == "unit of measure"

    # Fields that mean the same thing either way are not overridden.
    assert label_for("response_time", "service") == "response time (SLA)"
    assert label_for("compliance_accreditations", "service") == "accreditations and licences"
    assert label_for("payment_terms", "service") == "payment terms"

    # Tax is GST in Singapore and "tax" everywhere else.
    assert "GST" in taxonomy.describe_tax("SGD", 9.0)
    assert "GST" not in taxonomy.describe_tax("USD", 8.0)
    assert "Tax is added at 8%" in taxonomy.describe_tax("USD", 8.0)
