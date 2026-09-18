"""CSV export of a comparison run.

Written for a spreadsheet, not for a machine: one row per quote, the original
figures next to the normalized ones, and a leading block of context so the file
is still interpretable after it has been emailed around.
"""

import csv
from io import StringIO

from comparison.recommend import summarize_for_buyer
from comparison.schemas import ComparisonResult

HEADERS = [
    "Rank",
    "Supplier",
    "Recommended",
    "Composite score",
    "Completeness",
    "Missing fields",
    "Quoted unit price",
    "Quoted currency",
    "Quoted unit",
    "Normalized unit price",
    "Landed cost",
    "Currency (normalized)",
    "Goods",
    "Shipping",
    "Duties",
    "Taxes",
    "Discount",
    "Incoterms (quoted)",
    "Incoterms (basis)",
    "Incoterms factor",
    "FX rate applied",
    "Lead time (days)",
    "MOQ",
    "Payment terms",
    "Validity date",
    "Warranty (months)",
    "Supplier risk",
    "Price score",
    "Lead time score",
    "Payment terms score",
    "MOQ score",
    "Validity score",
    "Warranty score",
    "Risk score",
    "Risk flags",
    "Notes",
]


def _number(value: object, places: int = 2) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.{places}f}"
    except (TypeError, ValueError):
        return str(value)


def comparison_to_csv(comparison: ComparisonResult) -> str:
    """Render the comparison as CSV text (no trailing newline surprises)."""

    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")

    # ---- context block -----------------------------------------------------
    writer.writerow(["Supplier Quote Autopilot — comparison export"])
    writer.writerow(["RFQ", comparison.rfq_number or comparison.rfq_id])
    writer.writerow(["Item", comparison.item_name])
    writer.writerow(["Quantity", f"{comparison.quantity} {comparison.unit}"])
    writer.writerow(["Currency basis", comparison.base_currency])
    writer.writerow(["Incoterms basis", comparison.base_incoterms or "as quoted"])
    writer.writerow(["Quotes received", len(comparison.results)])
    writer.writerow(["Quotes ranked", len(comparison.ranked())])
    writer.writerow(
        [
            "Weights",
            ", ".join(
                f"{key}={value:.2f}" for key, value in sorted(comparison.weights.items())
            ),
        ]
    )
    fx = comparison.fx_rates or {}
    writer.writerow(["FX source", f"{fx.get('source', '')} (as of {fx.get('as_of', '')})"])
    writer.writerow(["Recommendation", summarize_for_buyer(comparison)])
    writer.writerow([])

    # ---- rationale ---------------------------------------------------------
    writer.writerow(["Rationale"])
    for line in (comparison.rationale or "").split("\n"):
        if line.strip():
            writer.writerow([line])
    writer.writerow([])

    # ---- per-quote table ---------------------------------------------------
    writer.writerow(HEADERS)

    for result in sorted(
        comparison.results, key=lambda r: (r.rank is None, r.rank or 0, r.supplier_name)
    ):
        breakdown = result.breakdown
        writer.writerow(
            [
                result.rank or "not ranked",
                result.supplier_name,
                "YES" if result.quote_id == comparison.recommended_quote_id else "",
                _number(result.composite_score),
                result.completeness,
                ", ".join(result.missing_fields),
                _number(result.unit_price_original),
                result.currency_original,
                result.unit_original,
                _number(result.unit_price_base, 4),
                _number(result.total_base),
                comparison.base_currency,
                _number(breakdown.goods),
                _number(breakdown.shipping),
                _number(breakdown.duties),
                _number(breakdown.taxes),
                _number(breakdown.discount),
                result.incoterms or "",
                comparison.base_incoterms or "",
                _number(breakdown.incoterms_factor, 6),
                _number(breakdown.fx_rate, 7),
                result.lead_time_days if result.lead_time_days is not None else "",
                result.moq if result.moq is not None else "",
                result.payment_terms or "",
                result.validity_date.isoformat() if result.validity_date else "",
                result.warranty_months if result.warranty_months is not None else "",
                result.supplier_risk,
                _number(result.scores.get("price")),
                _number(result.scores.get("lead_time")),
                _number(result.scores.get("payment_terms")),
                _number(result.scores.get("moq")),
                _number(result.scores.get("validity")),
                _number(result.scores.get("warranty")),
                _number(result.scores.get("risk")),
                " | ".join(result.risk_flags),
                " | ".join(result.notes + ([result.exclusion_reason] if result.exclusion_reason else [])),
            ]
        )

    writer.writerow([])
    writer.writerow(
        [
            "Excluded / unranked quotes are listed above with their reason in the "
            "Notes column. This export is a recommendation, not an award."
        ]
    )

    return buffer.getvalue()
