"""Comparison narrative prompts.

The comparison agent is the one place in this product allowed to *recommend*. That
is deliberate and bounded:

* Follow-up emails never recommend anything (see ``agents/followup/prompts.py``) —
  a supplier must not learn where they stand from a chasing email.
* This agent may rank and recommend, but the recommendation is advisory only. The
  guardrail is structural, not prompt-level: an award requires an ``Approval`` row
  written by an authenticated buyer, and no code path awards automatically.

The model is given the already-computed scoring run rather than the raw quotes, so
its prose can only describe arithmetic the engine performed — it cannot introduce
a number of its own.
"""

SYSTEM_PROMPT = """\
You are the comparison analyst for a procurement platform. You are given a
completed, deterministic scoring run over several supplier quotes for one RFQ, and
you write a short brief for the buyer.

You do not perform any arithmetic. Every cost, score, weight, and ranking you
mention has already been computed and is in the input. Never invent a figure, never
recompute one, and never disagree with the ranking you were given.

<rules>
  - Lead with the recommendation and what drives it.
  - Be concrete: name suppliers, quote landed costs and scores from the input.
  - Explain the trade-off when the cheapest quote is not the top-ranked one.
  - Call out any quote that is incomplete, expired, missing a price, or excluded
    from ranking — and say that its figures may change.
  - State any data caveat from the input: static FX rates, approximate Incoterms
    rebasing, unit mismatches. Do not present an estimate as a quoted fact.
  - Note when the top two quotes are close enough that the decision should rest on
    judgement rather than score.
  - Do NOT recommend a course of action about the commercial relationship
    (negotiating, consolidating, dropping a supplier). Rank the quotes; leave the
    relationship decision to the buyer.
  - Close by stating plainly that this is a recommendation requiring human approval.
  - 150-250 words. Plain prose, short paragraphs. No markdown headings, no bullet
    lists with more than four items, no tables.
</rules>

Return exactly one JSON object and nothing else:

{
  "summary": "<the brief, 150-250 words>",
  "key_risks": ["<short risk statement>", "..."]
}

key_risks must list at most five items, drawn only from the risks already present
in the input. Use an empty array when there are none.
"""


def build_user_prompt(
    *,
    rfq_number: str,
    item_name: str,
    quantity: int,
    unit: str,
    base_currency: str,
    base_incoterms: str | None,
    weights: dict[str, float],
    ranked: list[dict],
    excluded: list[dict],
    risks: list[str],
    fx_source: str,
) -> str:
    """Render the scoring run into a compact, unambiguous brief."""

    lines = [
        "<rfq>",
        f"  reference: {rfq_number}",
        f"  item: {item_name}",
        f"  quantity: {quantity:,} {unit}",
        f"  currency_basis: {base_currency}",
        f"  incoterms_basis: {base_incoterms or 'as quoted'}",
        f"  fx_source: {fx_source}",
        "</rfq>",
        "",
        "<weights>",
    ]

    for criterion, weight in sorted(weights.items(), key=lambda item: -item[1]):
        if weight:
            lines.append(f"  {criterion}: {weight:.2f}")

    lines += ["</weights>", "", "<ranked_quotes>"]

    for result in ranked:
        lines.append(f"  rank {result.get('rank')}: {result.get('supplier_name')}")
        lines.append(f"    composite_score: {result.get('composite_score')}")
        lines.append(f"    landed_cost: {result.get('total_base')} {base_currency}")

        breakdown = result.get("breakdown") or {}
        lines.append(
            "    cost_lines: goods={goods} shipping={shipping} duties={duties} "
            "taxes={taxes} discount={discount}".format(
                goods=breakdown.get("goods"),
                shipping=breakdown.get("shipping"),
                duties=breakdown.get("duties"),
                taxes=breakdown.get("taxes"),
                discount=breakdown.get("discount"),
            )
        )
        lines.append(
            f"    quoted: {result.get('unit_price_original')} "
            f"{result.get('currency_original')} per {result.get('unit_original')} "
            f"({result.get('incoterms') or 'no incoterms stated'})"
        )
        lines.append(
            f"    lead_time_days: {result.get('lead_time_days')} "
            f"| moq: {result.get('moq')} "
            f"| payment_terms: {result.get('payment_terms')} "
            f"| validity: {result.get('validity_date')} "
            f"| warranty_months: {result.get('warranty_months')} "
            f"| supplier_risk: {result.get('supplier_risk')}"
        )
        lines.append(f"    completeness: {result.get('completeness')}")

        missing = result.get("missing_fields") or []
        if missing:
            lines.append(f"    missing_required_fields: {', '.join(map(str, missing))}")

        scores = result.get("scores") or {}
        if scores:
            lines.append(
                "    scores: "
                + ", ".join(f"{key}={value}" for key, value in sorted(scores.items()))
            )

        flags = result.get("risk_flags") or []
        if flags:
            for flag in flags:
                lines.append(f"    risk_flag: {flag}")

    if not ranked:
        lines.append("  (no quote could be ranked)")

    lines += ["</ranked_quotes>", "", "<excluded_quotes>"]

    if excluded:
        for result in excluded:
            lines.append(
                f"  {result.get('supplier_name')}: {result.get('exclusion_reason')}"
            )
    else:
        lines.append("  (none)")

    lines += ["</excluded_quotes>", "", "<batch_risks>"]

    if risks:
        for risk in risks:
            lines.append(f"  - {risk}")
    else:
        lines.append("  (none)")

    lines += ["</batch_risks>", "", "Write the brief now. Return only the JSON object."]

    return "\n".join(lines)
