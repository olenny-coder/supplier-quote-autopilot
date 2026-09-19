"""Deterministic recommendation narrative.

The LLM writes the *nice* version of the recommendation. This module writes the
one that always exists. That split is deliberate:

* a comparison must never come back empty because the free-tier LLM quota ran
  out, and
* the numbers behind an award recommendation should be reproducible without a
  network call.

Everything here is pure string building over already-computed results.
"""

from comparison.schemas import ComparisonResult
from comparison.schemas import QuoteResult


def describe_ranking_basis(comparison: ComparisonResult) -> str:
    """The criteria the ranking actually used, in the buyer's own vocabulary.

    A fixed sentence naming "lead time, MOQ, and warranty" was wrong for every
    services comparison: a maintenance RFQ is ranked on the SLA and the supplier's
    licences, and a buyer reading that MOQ decided their award would be looking for
    a number that does not exist on the quote.
    """

    labels = {
        "price": "price (relative to the other quotes in this batch)",
        "response_time": "response time (SLA)",
        "lead_time": (
            "mobilisation time"
            if (comparison.procurement_type or "service") == "service"
            else "lead time"
        ),
        "compliance": "accreditations and licences",
        "payment_terms": "payment terms",
        "moq": (
            "minimum callout"
            if (comparison.procurement_type or "service") == "service"
            else "minimum order quantity"
        ),
        "validity": "rate validity",
        "warranty": (
            "defect liability period"
            if (comparison.procurement_type or "service") == "service"
            else "warranty"
        ),
        "risk": "supplier risk",
    }

    # Driven by the weights actually applied, not by a fixed list: a criterion
    # weighted to zero did not influence the score and must not be named as if it had.
    weighted = [
        key
        for key, weight in (comparison.weights or {}).items()
        if weight and key in labels
    ]

    if not weighted:
        return "price, and the supplier's own terms"

    named = [labels[key] for key in weighted]

    if len(named) == 1:
        return named[0]

    return ", ".join(named[:-1]) + f", and {named[-1]}"


def money(value: float | None, currency: str) -> str:
    if value is None:
        return "—"

    return f"{value:,.2f} {currency}"


def describe_quote(result: QuoteResult, currency: str) -> str:
    """One-line summary of a quote's headline terms."""

    parts = [f"{result.supplier_name}: {money(float(result.total_base or 0), currency)} landed"]

    if result.unit_price_base is not None:
        parts.append(f"{float(result.unit_price_base):,.2f}/{result.unit_original}")

    if result.lead_time_days is not None:
        parts.append(f"{result.lead_time_days}d lead")

    if result.payment_terms:
        parts.append(str(result.payment_terms))

    return ", ".join(parts)


def build_rationale(comparison: ComparisonResult) -> str:
    """Plain-English explanation of the ranking and the recommendation."""

    ranked = comparison.ranked()

    if not comparison.results:
        return "No supplier quotes have been received yet, so there is nothing to compare."

    if not ranked:
        excluded = [r for r in comparison.results if not r.comparable]
        reasons = "; ".join(
            f"{r.supplier_name}: {r.exclusion_reason}" for r in excluded if r.exclusion_reason
        )
        return (
            "None of the received quotes could be ranked. "
            + (reasons or "No quote carried a usable unit price.")
        )

    winner = ranked[0]
    currency = comparison.base_currency

    lines: list[str] = []

    lines.append(
        f"{len(ranked)} of {len(comparison.results)} quote(s) were comparable. "
        f"Ranking is a weighted score over {describe_ranking_basis(comparison)}. "
        f"Complete quotes rank ahead of incomplete ones."
    )

    lines.append(
        f"**{winner.supplier_name}** ranks first with a score of "
        f"{winner.composite_score:.1f}/100 and a landed cost of "
        f"{money(float(winner.total_base or 0), currency)} for "
        f"{comparison.quantity:,} {comparison.unit}."
    )

    if winner.breakdown.total_before_incoterms != winner.breakdown.total:
        lines.append(
            f"Their total was rebased from {winner.breakdown.incoterms_from or 'unstated'} "
            f"to {comparison.base_incoterms or 'the RFQ basis'} "
            f"(factor {winner.breakdown.incoterms_factor})."
        )

    # Make the ordering rule visible when it actually changed the outcome, so a
    # buyer is never puzzled by a pricier recommendation.
    outranked = [
        result
        for result in ranked[1:]
        if result.completeness == "incomplete"
        and result.total_base is not None
        and winner.total_base is not None
        and result.total_base < winner.total_base
    ]

    if outranked:
        names = ", ".join(result.supplier_name for result in outranked)
        lines.append(
            f"{names} quoted a lower landed cost but is incomplete, so it ranks "
            f"below {winner.supplier_name} — the missing details would change that "
            f"comparison, so chase them before treating it as settled."
        )

    if winner.completeness == "incomplete":
        lines.append(
            "**Caution:** every comparable quote is incomplete, so this ranking is "
            f"provisional. The leading quote is still missing "
            f"{', '.join(winner.missing_fields) or 'required fields'}."
        )

    # A high-risk supplier can be cheap precisely because they economise on the
    # things that make them low risk. That judgement is the buyer's, not the
    # engine's — so the arithmetic is left alone and stays re-weightable, but the
    # recommendation says it out loud rather than leaving it buried in a flag list.
    if (winner.supplier_risk or "low").lower() == "high":
        lines.append(
            f"**The recommended supplier, {winner.supplier_name}, is rated high "
            f"risk.** The score reflects price and terms only. Confirm insurance, "
            f"safety record and references before awarding — or put more weight on "
            f"supplier risk if that judgement should count for more."
        )

    if winner.missing_accreditations:
        lines.append(
            f"**{winner.supplier_name} does not hold "
            f"{', '.join(winner.missing_accreditations)}**, which this RFQ requires. "
            f"Their score is capped for that reason, and the work may not lawfully "
            f"proceed without it."
        )

    if len(ranked) > 1:
        runner_up = ranked[1]
        cost_gap = float(runner_up.total_base or 0) - float(winner.total_base or 0)

        lines.append(
            f"{runner_up.supplier_name} is next at {runner_up.composite_score:.1f}/100 "
            f"({money(float(runner_up.total_base or 0), currency)} landed, "
            f"{'+' if cost_gap >= 0 else ''}{cost_gap:,.2f} {currency} versus the leader)."
        )

        if len(ranked) > 2:
            third = ranked[2]
            lines.append(
                f"{third.supplier_name} is third at {third.composite_score:.1f}/100 "
                f"({money(float(third.total_base or 0), currency)} landed)."
            )

        # Only meaningful when both quotes are equally complete. Otherwise the
        # ranking was decided by the completeness rule, not by the score gap — and
        # the leading quote's score can legitimately be the *lower* of the two.
        same_basis = winner.completeness == runner_up.completeness
        score_gap = abs(winner.composite_score - runner_up.composite_score)

        if same_basis and score_gap < 3.0:
            lines.append(
                f"The top two are within {score_gap:.1f} points — treat this as a "
                f"genuine tie and weigh the commercial relationship and the open "
                f"risk flags when deciding."
            )

    cheapest = min(
        (r for r in ranked if r.total_base is not None),
        key=lambda r: r.total_base or 0,
        default=None,
    )

    if cheapest is not None and cheapest.quote_id != winner.quote_id:
        # Name the actual reason when the ranking has one, rather than blaming
        # "lead time and terms" for a quote that was ranked down for something else
        # entirely — a missing licence, say, which the text must not bury.
        reason = ""

        if cheapest.missing_accreditations:
            reason = (
                ", and it does not hold "
                + ", ".join(str(item) for item in cheapest.missing_accreditations)
                + " — which this RFQ requires"
            )
        elif cheapest.completeness == "incomplete":
            reason = ", and its submission is still incomplete"

        lines.append(
            f"{cheapest.supplier_name} is cheapest on landed cost "
            f"({money(float(cheapest.total_base or 0), currency)}) but ranks "
            f"{cheapest.rank} overall once every weighted criterion is applied"
            f"{reason}."
        )

    if comparison.risks:
        lines.append("Open risks: " + " ".join(comparison.risks))

    lines.append(
        "This is a recommendation only. Awarding a supplier requires an explicit "
        "human approval."
    )

    return "\n\n".join(lines)


def collect_comparison_risks(comparison: ComparisonResult) -> list[str]:
    """Roll the per-quote flags up into a batch-level risk list."""

    risks: list[str] = []

    incomplete = [r for r in comparison.results if r.completeness == "incomplete"]

    if incomplete:
        names = ", ".join(r.supplier_name for r in incomplete)
        risks.append(
            f"{len(incomplete)} quote(s) are incomplete ({names}); they rank below "
            f"every complete quote and their figures may change."
        )

    excluded = [r for r in comparison.results if not r.comparable]

    if excluded:
        names = ", ".join(r.supplier_name for r in excluded)
        risks.append(
            f"{len(excluded)} quote(s) could not be ranked ({names}); "
            f"see each quote's exclusion reason."
        )

    # Warn whenever ANY quote was converted, not just the winner. Checking only the
    # leading result meant a batch containing a converted EUR quote raised no caveat
    # at all whenever a USD quote happened to win — the very case where a buyer is
    # most likely to trust the numbers without looking.
    converted = [
        result
        for result in comparison.results
        if result.comparable
        and result.currency_original
        and result.currency_original != comparison.base_currency
    ]

    if converted:
        names = ", ".join(sorted({result.supplier_name for result in converted}))
        risks.append(
            f"Currency conversion used a static baseline FX table, not a live rate "
            f"({names}). Confirm the rate before committing."
        )

    rebased = [
        result
        for result in comparison.results
        if result.comparable
        and result.breakdown.total != result.breakdown.total_before_incoterms
    ]

    if rebased:
        names = ", ".join(sorted({result.supplier_name for result in rebased}))
        risks.append(
            f"Incoterms rebasing applied to {names} using an indicative cost ladder, "
            f"not quoted freight. Treat those totals as estimates."
        )

    for result in comparison.results:
        for flag in result.risk_flags:
            entry = f"{result.supplier_name}: {flag}"
            if entry not in risks:
                risks.append(entry)

    return risks


def tie_break_note(comparison: ComparisonResult) -> str | None:
    """Explicit note when two ranked quotes on the SAME basis are effectively equal.

    Comparing the raw score gap across incomplete and complete quotes would be
    misleading: the ordering rule puts completeness first, so the leading quote's
    score can legitimately be lower than the runner-up's. Only quotes judged on the
    same basis are compared.
    """

    ranked = comparison.ranked()

    if len(ranked) < 2:
        return None

    if ranked[0].completeness != ranked[1].completeness:
        return None

    gap = abs(ranked[0].composite_score - ranked[1].composite_score)

    if gap >= 3.0:
        return None

    return (
        f"{ranked[0].supplier_name} and {ranked[1].supplier_name} are separated by "
        f"{gap:.1f} points — statistically a tie. Prefer the one with fewer open "
        f"risk flags."
    )


def summarize_for_buyer(comparison: ComparisonResult) -> str:
    """Short headline used in list views and CSV exports."""

    winner = comparison.recommended

    if winner is None:
        return "No recommendation — not enough comparable quotes."

    return (
        f"Recommended: {winner.supplier_name} "
        f"({winner.composite_score:.1f}/100, "
        f"{money(float(winner.total_base or 0), comparison.base_currency)} landed)"
    )
