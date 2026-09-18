"""Comparison engine orchestration.

Pipeline, per quote:

    1. unit check + conversion onto the RFQ's unit basis   (units.py)
    2. unit price → base currency                          (fx.py / cost.py)
    3. landed cost: goods + shipping + duties + taxes − discount
    4. Incoterms rebasing onto the RFQ's basis             (incoterms.py)
    5. weighted multi-criteria scoring                     (score.py)
    6. risk flagging                                       (score.py)

Then the batch is ranked, the top two quotes become the recommendation and the
backup, and a deterministic rationale is written.

A quote that cannot be normalized is **not dropped** — it is returned with
``comparable=False`` and an ``exclusion_reason``. Silently omitting a supplier
from a comparison is the failure mode that costs money.
"""

from datetime import date

from comparison.cost import CostModelError
from comparison.cost import compute_cost
from comparison.cost import unit_price_in_base
from comparison.fx import UnknownCurrencyError
from comparison.fx import build_rate_table
from comparison.fx import describe as describe_fx
from comparison.fx import normalize_currency_code
from comparison.incoterms import build_factor_table
from comparison.incoterms import normalize_incoterm
from comparison.recommend import build_rationale
from comparison.recommend import collect_comparison_risks
from comparison.recommend import tie_break_note
from comparison.schemas import ComparisonInput
from comparison.schemas import ComparisonResult
from comparison.schemas import QuoteInput
from comparison.schemas import QuoteResult
from comparison.schemas import normalize_weights
from comparison.score import collect_risk_flags
from comparison.score import score_quote
from comparison.units import normalize_unit
from comparison.units import price_basis_multiplier


def normalize_quote(
    quote: QuoteInput,
    *,
    quantity: int,
    base_currency: str,
    base_incoterms: str | None,
    unit: str,
    rates: dict[str, float] | None,
    factors: dict[str, float] | None,
) -> QuoteResult:
    """Normalize one quote into an RFQ-basis :class:`QuoteResult`."""

    result = QuoteResult(
        quote_id=quote.quote_id,
        supplier_name=quote.supplier_name,
        currency_original=normalize_currency_code(quote.currency),
        unit_price_original=quote.unit_price,
        unit_original=normalize_unit(quote.unit).canonical,
        lead_time_days=quote.lead_time_days,
        moq=quote.moq,
        payment_terms=quote.payment_terms,
        incoterms=normalize_incoterm(quote.incoterms),
        validity_date=quote.validity_date,
        warranty_months=quote.warranty_months,
        supplier_risk=quote.supplier_risk,
        completeness=quote.completeness,
        missing_fields=list(quote.missing_fields or []),
    )

    if quote.completeness == "incomplete":
        result.incompleteness_note = (
            "Submission is missing required fields: "
            + (", ".join(quote.missing_fields) or "unknown")
            + "."
        )

    if quote.unit_price is None or quote.unit_price <= 0:
        result.comparable = False
        result.exclusion_reason = "No usable unit price was provided."
        return result

    # ---------------------------------------------------------------- units
    multiplier, unit_warning = price_basis_multiplier(quote.unit, unit)

    if unit_warning and "excluded" in unit_warning:
        result.comparable = False
        result.exclusion_reason = unit_warning
        return result

    if unit_warning:
        result.unit_mismatch = True
        result.notes.append(unit_warning)

    # ------------------------------------------------------------------ money
    try:
        result.unit_price_base = unit_price_in_base(
            quote,
            base_currency=base_currency,
            unit_multiplier=multiplier,
            rates=rates,
        )

        result.breakdown = compute_cost(
            quote,
            quantity=quantity,
            base_currency=base_currency,
            base_incoterms=base_incoterms,
            unit_price_base=result.unit_price_base,
            rates=rates,
            factors=factors,
        )
    except UnknownCurrencyError as exc:
        result.comparable = False
        result.exclusion_reason = str(exc)
        return result
    except CostModelError as exc:
        result.comparable = False
        result.exclusion_reason = str(exc)
        return result

    result.total_base = result.breakdown.total

    if result.breakdown.total != result.breakdown.total_before_incoterms:
        result.notes.append(
            f"Rebased from {result.breakdown.incoterms_from or 'unstated'} "
            f"to {base_incoterms or 'RFQ basis'} "
            f"(×{result.breakdown.incoterms_factor})."
        )

    return result


def run_comparison(payload: ComparisonInput) -> ComparisonResult:
    """Score every quote in ``payload`` and recommend a winner."""

    today = payload.today or date.today()

    rates = build_rate_table()
    factors = build_factor_table()
    weights = normalize_weights(payload.weights)

    base_currency = normalize_currency_code(payload.base_currency)
    base_incoterms = normalize_incoterm(payload.base_incoterms) or payload.base_incoterms

    comparison = ComparisonResult(
        rfq_id=payload.rfq_id,
        rfq_number=payload.rfq_number,
        item_name=payload.item_name,
        base_currency=base_currency,
        base_incoterms=base_incoterms,
        quantity=payload.quantity,
        unit=normalize_unit(payload.unit).canonical,
        weights=weights,
        fx_rates=describe_fx(rates),
    )

    comparison.results = [
        normalize_quote(
            quote,
            quantity=payload.quantity,
            base_currency=base_currency,
            base_incoterms=base_incoterms,
            unit=payload.unit,
            rates=rates,
            factors=factors,
        )
        for quote in payload.quotes
    ]

    comparable = [r for r in comparison.results if r.comparable]
    prices = [r.total_base for r in comparable]

    for result in comparable:
        score_quote(
            result,
            prices=prices,
            weights=weights,
            quantity=payload.quantity,
            today=today,
        )
        result.risk_flags = collect_risk_flags(
            result,
            quantity=payload.quantity,
            today=today,
        )

    # Ordering rule, and it is deliberate:
    #
    #   1. every COMPLETE quote ranks ahead of every incomplete one, regardless of
    #      score, because an incomplete quote is missing exactly the fields (MOQ,
    #      payment terms, validity) that would change its own cost and terms — it
    #      cannot be compared on equal terms, so it must not win one;
    #   2. within each group, by composite score;
    #   3. then by landed cost, then by id, so two identical runs never disagree.
    #
    # Incomplete quotes are still scored and still listed, immediately below the
    # ranked ones, with their exclusion note. Dropping them would be worse: a buyer
    # needs to see that a cheaper quote exists and what it is missing.
    comparable.sort(
        key=lambda r: (
            0 if r.completeness == "complete" else 1,
            -r.composite_score,
            float(r.total_base or 0),
            r.quote_id,
        )
    )

    for index, result in enumerate(comparable, start=1):
        result.rank = index

    # Present the stored results best-first, then the unranked ones. Consumers
    # (the UI table, the CSV export, the LLM brief) all want this order, and
    # leaving it in submission order would make every one of them re-sort.
    comparison.results = comparable + [
        result for result in comparison.results if not result.comparable
    ]

    if comparable:
        comparison.recommended_quote_id = comparable[0].quote_id
        if len(comparable) > 1:
            comparison.backup_quote_id = comparable[1].quote_id

    comparison.risks = collect_comparison_risks(comparison)

    note = tie_break_note(comparison)
    if note:
        comparison.risks.append(note)

    # Conclusive means a complete quote could be ranked and is therefore the
    # recommendation. When every comparison candidate is incomplete, the output is
    # advisory at best and the buyer is told so.
    comparison.is_conclusive = any(
        result.completeness == "complete" for result in comparable
    )

    comparison.rationale = build_rationale(comparison)

    return comparison
