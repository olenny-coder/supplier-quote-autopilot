"""Comparison engine — landed cost, FX, Incoterms, units, scoring, ranking, export.

The engine is pure domain logic (no database, no FastAPI, no network), so these
tests are fast, offline and deterministic: every date is passed in explicitly and
every money assertion uses :class:`~decimal.Decimal`.

The properties protected here are the ones whose silent failure costs money:

* a landed cost is arithmetic, not an estimate — asserted to the cent;
* an unconvertible currency or unit **excludes** a quote with a stated reason
  rather than being treated as parity, and the excluded quote stays in ``results``
  so no supplier is ever silently dropped from a comparison;
* rebasing Incoterms changes the number, and equal terms change nothing;
* the recommendation and its backup come from the ranking, and the rationale is
  never empty — a comparison must always explain itself.
"""

import csv
import io
from datetime import date
from decimal import ROUND_HALF_UP
from decimal import Decimal

import pytest

from comparison import ComparisonInput
from comparison import QuoteInput
from comparison import comparison_to_csv
from comparison import normalize_weights
from comparison import rebase_factor
from comparison import run_comparison
from comparison.fx import UnknownCurrencyError
from comparison.fx import build_rate_table
from comparison.fx import convert
from comparison.incoterms import normalize_incoterm
from comparison.score import UNKNOWN_SCORE
from comparison.score import parse_payment_term_days
from comparison.score import score_moq
from comparison.units import normalize_unit
from comparison.units import price_basis_multiplier
from comparison.schemas import CRITERIA
from comparison.schemas import DEFAULT_WEIGHTS

#: A fixed "today" so validity scoring never depends on the wall clock.
TODAY = date(2026, 6, 1)


def _quote(quote_id: int = 1, supplier_name: str = "Acme", **overrides) -> QuoteInput:
    """A complete, comparable FOB/USD quote unless overridden by the test."""

    fields = {
        "quote_id": quote_id,
        "supplier_name": supplier_name,
        "currency": "USD",
        "unit": "pcs",
        "unit_price": Decimal("2.50"),
        "incoterms": "FOB",
    }
    fields.update(overrides)
    return QuoteInput(**fields)


def _run(quotes, *, quantity: int = 1000, unit: str = "pcs", base_incoterms="FOB", **payload):
    return run_comparison(
        ComparisonInput(
            rfq_id=1,
            rfq_number="RFQ-2026-001",
            item_name="Bearing 6204",
            quantity=quantity,
            unit=unit,
            base_currency="USD",
            base_incoterms=base_incoterms,
            quotes=list(quotes),
            today=TODAY,
            **payload,
        )
    )


# ---------------------------------------------------------------- landed cost
def test_landed_cost_is_unit_price_times_quantity_plus_addons_minus_discount():
    """The headline number is auditable arithmetic in the RFQ's own currency."""

    quote = _quote(
        unit_price=Decimal("2.50"),
        shipping_cost=Decimal("100.00"),
        duties=Decimal("50.00"),
        taxes=Decimal("25.00"),
        discount=Decimal("10.00"),
    )

    result = _run([quote], quantity=1000)
    breakdown = result.results[0].breakdown

    assert breakdown.goods == Decimal("2500.00")
    assert breakdown.shipping == Decimal("100.00")
    assert breakdown.duties == Decimal("50.00")
    assert breakdown.taxes == Decimal("25.00")
    assert breakdown.discount == Decimal("10.00")
    # 2500 + 100 + 50 + 25 - 10
    assert breakdown.subtotal == Decimal("2665.00")
    assert breakdown.total == Decimal("2665.00")
    assert result.results[0].total_base == Decimal("2665.00")


def test_equal_incoterms_terms_are_not_rebased():
    """FOB against an FOB basis must not move the number at all."""

    multiplier, adjusted = rebase_factor("FOB", "FOB")

    # Exactly Decimal("1"), not a float that happens to print as 1.0.
    assert multiplier == Decimal("1")
    assert adjusted is False
    assert rebase_factor(None, None) == (Decimal("1"), False)

    result = _run([_quote(incoterms="FOB Shenzhen")])
    breakdown = result.results[0].breakdown

    assert breakdown.incoterms_from == "FOB"
    assert breakdown.incoterms_to == "FOB"
    assert breakdown.total == breakdown.total_before_incoterms


def test_ddp_quote_is_reduced_when_compared_on_an_fob_basis():
    """A DDP price already contains freight and duty the FOB basis excludes."""

    quote = _quote(unit_price=Decimal("10.00"), incoterms="DDP Hamburg")

    result = _run([quote], quantity=100)
    breakdown = result.results[0].breakdown

    assert breakdown.incoterms_from == "DDP"
    assert breakdown.incoterms_to == "FOB"
    assert breakdown.total_before_incoterms == Decimal("1000.00")
    # 1.04 / 1.13 is the FOB-to-DDP ladder ratio.
    assert breakdown.total == Decimal("920.35")
    assert breakdown.total < breakdown.total_before_incoterms
    assert result.results[0].notes, "a rebased quote must say that it was rebased"


def test_exw_quote_is_increased_when_compared_on_an_fob_basis():
    """The rebasing must work in the other direction too."""

    result = _run([_quote(unit_price=Decimal("10.00"), incoterms="EXW Shenzhen")], quantity=100)
    breakdown = result.results[0].breakdown

    assert breakdown.incoterms_from == "EXW"
    assert breakdown.total_before_incoterms == Decimal("1000.00")
    assert breakdown.total == Decimal("1040.00")
    assert breakdown.total > breakdown.total_before_incoterms


# ------------------------------------------------------------------------- FX
def test_eur_quote_is_converted_into_the_usd_rfq_currency_at_the_table_rate():
    """A non-base currency quote is converted, not compared at face value."""

    quote = _quote(currency="EUR", unit_price=Decimal("100.00"))

    result = _run([quote], quantity=10)
    scored = result.results[0]

    expected_rate = (Decimal("1") / Decimal("0.92")).quantize(
        Decimal("0.0000001"), rounding=ROUND_HALF_UP
    )

    assert result.base_currency == "USD"
    assert scored.currency_original == "EUR"
    assert scored.breakdown.fx_from == "EUR"
    assert scored.breakdown.fx_to == "USD"
    assert scored.breakdown.fx_rate == expected_rate
    assert scored.unit_price_base == Decimal("108.6957")
    # 100 EUR/pc at 0.92 USD-per-EUR-basis is worth MORE dollars, not fewer.
    assert scored.total_base == Decimal("1086.96")


def test_unknown_currency_excludes_the_quote_instead_of_assuming_one_to_one():
    """Treating an unknown currency as parity would silently mis-price the award."""

    quote = _quote(quote_id=9, supplier_name="Mystery Metals", currency="XYZ")

    result = _run([quote])
    scored = result.results[0]

    assert scored.comparable is False
    assert scored.rank is None
    assert scored.exclusion_reason and "XYZ" in scored.exclusion_reason
    # Nothing was costed, so no 1:1 total was invented.
    assert scored.total_base is None
    assert scored.breakdown.total == Decimal("0")


def test_convert_reports_the_rate_it_applied():
    converted, rate = convert(Decimal("100"), "EUR", "USD", build_rate_table())

    assert rate > 0
    assert converted == Decimal("100") * rate
    assert convert(Decimal("50"), "USD", "USD", build_rate_table()) == (
        Decimal("50"),
        Decimal("1"),
    )

    with pytest.raises(UnknownCurrencyError):
        convert(Decimal("1"), "ZZZ", "USD", build_rate_table())


# ---------------------------------------------------------------------- units
def test_box_of_100_is_converted_to_a_per_piece_price():
    """A stated pack size is information, so it converts exactly (÷100)."""

    multiplier, warning = price_basis_multiplier("box of 100", "pcs")
    assert multiplier == pytest.approx(0.01)
    assert warning and "excluded" not in warning

    assert normalize_unit("box of 100").canonical == "box"
    assert normalize_unit("box of 100").pack_size == 100

    result = _run([_quote(unit="box of 100", unit_price=Decimal("120.00"))], quantity=1000)
    scored = result.results[0]

    assert scored.comparable is True
    assert scored.unit_original == "box"
    assert scored.unit_price_base == Decimal("1.2000")
    assert scored.breakdown.goods == Decimal("1200.00")
    # A conversion happened, so the buyer is told about it.
    assert scored.unit_mismatch is True
    assert any("box of 100" in note for note in scored.notes)


def test_kg_quote_against_a_piece_rfq_is_excluded_with_a_reason_naming_the_units():
    """Mass and count are not interchangeable without the part's weight."""

    multiplier, warning = price_basis_multiplier("kg", "pcs")
    assert multiplier == 1.0
    assert warning and "excluded" in warning

    result = _run(
        [
            _quote(quote_id=1, supplier_name="ByWeight", unit="kg", unit_price=Decimal("8.00")),
            _quote(quote_id=2, supplier_name="ByPiece", unit="pcs", unit_price=Decimal("2.50")),
        ]
    )

    by_weight = result.by_id(1)
    by_piece = result.by_id(2)

    assert by_weight.comparable is False
    assert by_weight.rank is None
    assert "kg" in by_weight.exclusion_reason
    assert "pcs" in by_weight.exclusion_reason
    assert "excluded" in by_weight.exclusion_reason
    # The comparable quote is still ranked: one bad unit does not spoil the batch.
    assert by_piece.comparable is True
    assert by_piece.rank == 1
    assert result.recommended_quote_id == 2


def test_tonne_to_kilogram_divides_a_per_tonne_price():
    """A price converts in the OPPOSITE direction to a quantity.

    Regression guard for a 10^6 error: 1 t = 1000 kg, so a per-tonne price is
    1/1000 of a per-kg price. Multiplying instead of dividing made a mass-quoted
    supplier astronomically more expensive than a count-quoted one — enough to
    invert a real award recommendation.
    """

    multiplier, warning = price_basis_multiplier("t", "kg")

    assert multiplier == 0.001
    assert warning and "excluded" not in warning

    result = _run(
        [_quote(unit="t", unit_price=Decimal("2.00"))],
        quantity=100,
        unit="kg",
    )

    # 100 kg at 2.00 per tonne is 0.20 USD.
    assert result.results[0].unit_price_base == Decimal("0.0020")
    assert result.results[0].total_base == Decimal("0.20")


def test_unit_price_conversion_is_the_inverse_of_quantity_conversion():
    """Whatever the direction, the two must agree — one cannot be inverted alone."""

    for quoted, target, expected in (
        ("t", "kg", 0.001),
        ("kg", "t", 1000.0),
        ("kg", "g", 0.001),
        ("g", "kg", 1000.0),
        ("lb", "kg", 2.2046226),
        ("m", "cm", 0.01),
        ("ft", "m", 3.2808399),
        ("l", "ml", 0.001),
    ):
        multiplier, _ = price_basis_multiplier(quoted, target)

        assert multiplier == pytest.approx(expected, rel=1e-6), f"{quoted} -> {target}"


# ------------------------------------------------------------------------ MOQ
def test_score_moq_full_marks_at_or_below_the_requested_quantity():
    assert score_moq(500, 1000) == 100.0
    assert score_moq(1000, 1000) == 100.0
    # "No MOQ" (0) is the best possible answer.
    assert score_moq(0, 1000) == 100.0


def test_score_moq_is_meaningfully_lower_above_the_requested_quantity():
    above = score_moq(2000, 1000)

    assert above == 84.95
    assert above < score_moq(1000, 1000)
    # 100x the requested quantity is the documented floor.
    assert score_moq(100_000, 1000) == 0.0


def test_score_moq_unknown_is_the_neutral_value():
    neutral = score_moq(None, 1000)

    assert neutral == UNKNOWN_SCORE
    # Neutral means neither rewarded nor penalised.
    assert score_moq(1000, 1000) > neutral > score_moq(10_000, 1000)


# ------------------------------------------------------------ payment terms
@pytest.mark.parametrize(
    "terms, expected",
    [
        ("Net 30", 30),
        ("Net 60", 60),
        ("2/10 Net 30", 30),
        ("prepay", 0),
        ("TBD", None),
        ("to be advised", None),
        ("we will discuss later", None),
        (None, None),
    ],
)
def test_parse_payment_term_days(terms, expected):
    """Days granted to the buyer; None deliberately means "cannot be parsed"."""

    assert parse_payment_term_days(terms) == expected


# -------------------------------------------------------------------- weights
def test_empty_weights_are_the_defaults():
    assert normalize_weights({}) == DEFAULT_WEIGHTS
    assert normalize_weights(None) == DEFAULT_WEIGHTS


def test_arbitrary_weights_are_normalized_to_sum_to_one():
    weights = normalize_weights({"price": 3, "lead_time": 1})

    assert weights["price"] == pytest.approx(0.75)
    assert weights["lead_time"] == pytest.approx(0.25)
    assert sum(weights.values()) == pytest.approx(1.0)


def test_unknown_weight_keys_are_dropped():
    weights = normalize_weights({"price": 1, "margin": 99, "goodwill": 4})

    assert "margin" not in weights
    assert "goodwill" not in weights
    assert weights["price"] == pytest.approx(1.0)


def test_all_zero_weights_fall_back_to_the_defaults():
    """A malformed per-RFQ override must not produce a division by zero."""

    assert normalize_weights({"price": 0, "lead_time": 0}) == DEFAULT_WEIGHTS
    assert normalize_weights({"price": -5}) == DEFAULT_WEIGHTS


def test_normalized_weights_always_carry_every_criterion():
    for raw in ({}, {"price": 1}, {"price": 1, "unknown": 2}):
        weights = normalize_weights(raw)

        assert set(weights) == set(CRITERIA), raw
        assert sum(weights.values()) == pytest.approx(1.0)


# ------------------------------------------------------------------- ranking
def test_the_cheapest_landed_cost_does_not_automatically_rank_first():
    """Price is only one weighted criterion — a cheap-but-slow quote loses."""

    cheapest = _quote(
        quote_id=1,
        supplier_name="CheapCo",
        unit_price=Decimal("2.00"),  # 2,000 USD landed for 1000 pcs
        lead_time_days=210,
        moq=5000,
        payment_terms="prepay",
        validity_date=date(2026, 5, 1),  # already expired on TODAY
        warranty_months=0,
        supplier_risk="high",
    )
    balanced = _quote(
        quote_id=2,
        supplier_name="Balanced",
        unit_price=Decimal("3.00"),  # 3,000 USD landed
        lead_time_days=7,
        moq=100,
        payment_terms="Net 60",
        validity_date=date(2026, 9, 1),
        warranty_months=36,
    )
    expensive = _quote(
        quote_id=3,
        supplier_name="Expensive",
        unit_price=Decimal("5.00"),
        lead_time_days=30,
        moq=1000,
        payment_terms="Net 30",
        validity_date=date(2026, 7, 1),
        warranty_months=12,
        supplier_risk="medium",
    )

    result = _run([cheapest, balanced, expensive])
    ranked = result.ranked()

    assert [r.supplier_name for r in ranked] == ["Balanced", "CheapCo", "Expensive"]
    assert ranked[0].total_base > result.by_id(1).total_base

    by_cost = sorted(result.results, key=lambda r: r.total_base)
    assert by_cost[0].quote_id == 1
    assert by_cost[0].rank == 2
    assert result.recommended_quote_id == 2
    assert result.backup_quote_id == 1

    # The rationale must call out the price/ranking inversion explicitly.
    assert "cheapest on landed cost" in result.rationale


def test_missing_unit_price_keeps_the_quote_in_the_results_unranked():
    """Silently dropping a supplier from a comparison is the costly failure mode."""

    result = _run(
        [
            _quote(quote_id=1, supplier_name="NoPrice", unit_price=None),
            _quote(quote_id=2, supplier_name="Priced", unit_price=Decimal("2.50")),
        ]
    )

    assert len(result.results) == 2  # nobody is dropped
    missing = result.by_id(1)

    assert missing is not None
    assert missing.rank is None
    assert missing.comparable is False
    assert missing.exclusion_reason
    assert missing.supplier_name == "NoPrice"
    assert result.recommended_quote_id == 2


def test_an_incomplete_quote_scores_lower_than_an_identical_complete_one():
    """Completeness is docked so a gap can never outrank a full answer."""

    complete = _quote(quote_id=1, supplier_name="Complete", unit_price=Decimal("2.50"))
    incomplete = _quote(
        quote_id=2,
        supplier_name="Partial",
        unit_price=Decimal("2.50"),
        completeness="incomplete",
        missing_fields=["moq", "payment_terms"],
    )

    result = _run([complete, incomplete])
    complete_score = result.by_id(1).composite_score
    incomplete_score = result.by_id(2).composite_score

    # Identical economics, so the only difference is the completeness dock.
    assert result.by_id(1).scores["price"] == result.by_id(2).scores["price"]
    assert incomplete_score < complete_score
    assert result.by_id(2).incompleteness_note
    assert result.ranked()[0].quote_id == 1


def test_recommendation_and_backup_follow_the_ranking():
    quotes = [
        _quote(quote_id=1, supplier_name="Slow", unit_price=Decimal("1.00"), lead_time_days=180),
        _quote(quote_id=2, supplier_name="Fast", unit_price=Decimal("3.00"), lead_time_days=7),
        _quote(quote_id=3, supplier_name="Middle", unit_price=Decimal("2.00"), lead_time_days=30),
    ]

    result = _run(quotes)
    ranked = result.ranked()

    assert result.recommended_quote_id == ranked[0].quote_id
    assert result.backup_quote_id == ranked[1].quote_id
    assert result.recommended.quote_id == result.recommended_quote_id
    assert [r.rank for r in ranked] == [1, 2, 3]


def test_a_single_quote_has_no_backup():
    result = _run([_quote(quote_id=1, supplier_name="Only")])

    assert result.recommended_quote_id == 1
    assert result.backup_quote_id is None
    assert result.recommended_quote_id is not None


# ----------------------------------------------------------------- rationale
def test_rationale_is_never_empty():
    normal = _run(
        [
            _quote(quote_id=1, supplier_name="Fast", unit_price=Decimal("3.00"), lead_time_days=7),
            _quote(quote_id=2, supplier_name="Slow", unit_price=Decimal("1.00"), lead_time_days=180),
        ]
    )
    excluded = _run([_quote(quote_id=1, supplier_name="NoPrice", unit_price=None)])
    empty = _run([])

    assert normal.rationale.strip()
    assert excluded.rationale.strip()
    assert empty.rationale.strip()

    # Each case says something true about why there is (or is not) a winner.
    assert "ranks first" in normal.rationale
    assert "could be ranked" in excluded.rationale
    assert "NoPrice" in excluded.rationale
    assert "nothing to compare" in empty.rationale
    assert empty.recommended_quote_id is None
    assert empty.recommended is None
    assert normal.rationale.endswith("requires an explicit human approval.")


def test_all_quotes_excluded_is_not_conclusive_but_still_explains_itself():
    result = _run(
        [
            _quote(quote_id=1, supplier_name="A", unit_price=None),
            _quote(quote_id=2, supplier_name="B", currency="XYZ"),
        ]
    )

    assert result.ranked() == []
    assert result.is_conclusive is False
    assert result.recommended_quote_id is None
    assert len(result.results) == 2
    for scored in result.results:
        assert scored.exclusion_reason


# --------------------------------------------------------------- determinism
def test_the_same_input_produces_identical_scores_and_ordering():
    """A buyer re-running a comparison must not see the ranking move."""

    def payload():
        return [
            _quote(quote_id=1, supplier_name="A", unit_price=Decimal("2.11"), lead_time_days=21),
            _quote(quote_id=2, supplier_name="B", unit_price=Decimal("2.00"), lead_time_days=21),
            _quote(
                quote_id=3,
                supplier_name="C",
                unit_price=Decimal("2.00"),
                lead_time_days=21,
                payment_terms="Net 60",
            ),
        ]

    first = _run(payload())
    second = _run(payload())

    assert [(r.quote_id, r.composite_score, r.rank) for r in first.results] == [
        (r.quote_id, r.composite_score, r.rank) for r in second.results
    ]
    assert first.model_dump_jsonable() == second.model_dump_jsonable()


# ---------------------------------------------------------------------- CSV
def test_csv_export_parses_and_carries_the_context_the_buyer_needs():
    quotes = [
        _quote(quote_id=1, supplier_name="Fast Freight", unit_price=Decimal("3.00"), lead_time_days=7),
        _quote(quote_id=2, supplier_name="Slow Boat", unit_price=Decimal("1.00"), lead_time_days=180),
        _quote(quote_id=3, supplier_name="By Weight", unit="kg", unit_price=Decimal("8.00")),
    ]

    result = _run(quotes)
    text = comparison_to_csv(result)
    rows = list(csv.reader(io.StringIO(text)))
    cells = [cell for row in rows for cell in row]

    # The export is a real CSV: quoted fields must round-trip through csv.reader.
    assert rows[0][0] == "Supplier Quote Autopilot — comparison export"
    assert ["RFQ", "RFQ-2026-001"] in rows
    assert "RFQ-2026-001" in cells

    for supplier in ("Fast Freight", "Slow Boat", "By Weight"):
        assert supplier in cells

    for line in result.rationale.split("\n"):
        if line.strip():
            assert line in cells, "every rationale line is exported verbatim"

    assert any("not an award" in cell for cell in cells)

    # An excluded quote carries its reason into its own row.
    excluded = result.by_id(3)
    excluded_row = next(row for row in rows if len(row) > 1 and row[1] == "By Weight")
    assert excluded.rank is None
    assert excluded_row[0] == "not ranked"
    assert excluded.exclusion_reason in " | ".join(excluded_row)


def test_csv_export_of_an_empty_comparison_still_has_a_header_row():
    text = comparison_to_csv(_run([]))
    rows = list(csv.reader(io.StringIO(text)))

    assert any(row and row[0] == "Rank" for row in rows)
    assert any("nothing to compare" in " ".join(row) for row in rows)


def test_the_static_fx_warning_fires_whenever_any_quote_was_converted():
    """The caveat must cover the whole batch, not just the winner.

    Regression guard: the warning used to inspect only ``results[0]``, so a batch
    containing a converted EUR quote raised no caveat at all whenever a USD quote
    happened to win — precisely the case where a buyer is most likely to trust the
    numbers without looking at where they came from.
    """

    dollar = _quote(quote_id=1, supplier_name="Dollar", unit_price=Decimal("3.00"))
    euro = _quote(
        quote_id=2,
        supplier_name="Euro",
        currency="EUR",
        unit_price=Decimal("5.00"),
        lead_time_days=30,
    )

    result = _run([dollar, euro])

    assert result.recommended_quote_id == 1
    assert result.results[0].breakdown.fx_from == "USD"
    # The EUR quote really was converted...
    assert result.by_id(2).breakdown.fx_from == "EUR"
    assert result.by_id(2).total_base == Decimal("5434.80")
    # ...so the caveat is raised, and it names the supplier it applies to.
    warnings = [risk for risk in result.risks if "static baseline FX" in risk]
    assert len(warnings) == 1
    assert "Euro" in warnings[0]


def test_no_fx_warning_when_every_quote_is_already_in_the_base_currency():
    """The converse: an all-USD batch must not carry a currency caveat."""

    result = _run(
        [
            _quote(quote_id=1, supplier_name="A", unit_price=Decimal("3.00")),
            _quote(quote_id=2, supplier_name="B", unit_price=Decimal("4.00")),
        ]
    )

    assert not any("static baseline FX" in risk for risk in result.risks)


def test_the_static_fx_warning_fires_when_the_winner_is_converted():
    """The case that always worked: the recommended quote itself needed conversion."""

    result = _run(
        [
            _quote(quote_id=1, supplier_name="Euro", currency="EUR", unit_price=Decimal("2.00")),
            _quote(quote_id=2, supplier_name="Dollar", unit_price=Decimal("5.00")),
        ]
    )

    assert result.recommended_quote_id == 1
    assert any("static baseline FX" in risk for risk in result.risks)


# ------------------------------------------------------------ incoterm basics
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("fob shenzhen", "FOB"),
        ("DDP Hamburg", "DDP"),
        ("Delivered Duty Paid", "DDP"),
        ("EXW", "EXW"),
        ("", None),
        (None, None),
        ("banana", None),
    ],
)
def test_normalize_incoterm(raw, expected):
    assert normalize_incoterm(raw) == expected
