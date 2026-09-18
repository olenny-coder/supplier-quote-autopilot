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
        f"Ranking is a weighted score over price (relative to the other quotes in "
        f"this batch), lead time, payment terms, MOQ, validity, warranty, and "
        f"supplier risk."
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

    if winner.completeness == "incomplete":
        lines.append(
            "**Caution:** the leading quote is incomplete — it is still missing "
            f"{', '.join(winner.missing_fields) or 'required fields'}. Chase those "
            "before treating this as final."
        )

    if len(ranked) > 1:
        runner_up = ranked[1]
        cost_gap = float(runner_up.total_base or 0) - float(winner.total_base or 0)
        score_gap = winner.composite_score - runner_up.composite_score

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

        if score_gap < 3.0:
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
        lines.append(
            f"{cheapest.supplier_name} is cheapest on landed cost "
            f"({money(float(cheapest.total_base or 0), currency)}) but ranks "
            f"{cheapest.rank} overall once lead time and terms are weighted in."
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
            f"{len(incomplete)} quote(s) are incomplete ({names}); their scores are "
            f"docked and their figures may change."
        )

    excluded = [r for r in comparison.results if not r.comparable]

    if excluded:
        names = ", ".join(r.supplier_name for r in excluded)
        risks.append(
            f"{len(excluded)} quote(s) could not be ranked ({names}); "
            f"see each quote's exclusion reason."
        )

    if comparison.results and not comparison.results[0].breakdown.fx_from == comparison.base_currency:
        risks.append(
            "Currency conversion used a static baseline FX table, not a live rate. "
            "Confirm the rate before committing."
        )

    for result in comparison.results:
        for flag in result.risk_flags:
            entry = f"{result.supplier_name}: {flag}"
            if entry not in risks:
                risks.append(entry)

    return risks


def tie_break_note(comparison: ComparisonResult) -> str | None:
    """Explicit note when two ranked quotes are effectively equal."""

    ranked = comparison.ranked()

    if len(ranked) < 2:
        return None

    gap = ranked[0].composite_score - ranked[1].composite_score

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
