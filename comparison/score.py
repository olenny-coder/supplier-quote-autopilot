"""Weighted multi-criteria scoring and risk flagging.

Every criterion is scored 0–100, higher always better. Two families:

* **Absolute** (lead time, payment terms, MOQ, validity, warranty, supplier risk)
  — scored against fixed, documented thresholds, so a quote's score does not move
  when an unrelated supplier is added to the batch. Five quotes out of five
  scoring badly is real information.
* **Relative** (price) — scored min-max *within the batch*. Price has no absolute
  meaning without a benchmark: the cheapest quote in a bad batch is still the
  cheapest, and a buyer needs to see that, not a 40/100 that hides the ranking.
  The comparison snapshot records that price was scored relatively.

Adapted from ForgeFlow's long-lead-time flagging (MIT, Copyright (c) 2026
JayleeBot) — see NOTICE.
"""

import math
from datetime import date
from decimal import Decimal

from comparison.schemas import CRITERIA
from comparison.schemas import QuoteResult

#: Lead time (days) -> score. Linear interpolation between the anchors.
LEAD_TIME_ANCHORS: list[tuple[float, float]] = [
    (0, 100.0),
    (7, 100.0),
    (14, 92.0),
    (30, 78.0),
    (45, 62.0),
    (60, 48.0),
    (90, 28.0),
    (120, 15.0),
    (180, 5.0),
]

#: Payment terms score by net days granted to the buyer (longer is better for us).
PAYMENT_TERM_ANCHORS: list[tuple[float, float]] = [
    (0, 35.0),
    (15, 60.0),
    (30, 78.0),
    (45, 88.0),
    (60, 95.0),
    (90, 100.0),
]

SUPPLIER_RISK_SCORES = {"low": 100.0, "medium": 62.0, "high": 25.0}

#: Warranty: months of coverage -> score.
WARRANTY_ANCHORS: list[tuple[float, float]] = [
    (0, 40.0),
    (6, 65.0),
    (12, 85.0),
    (24, 95.0),
    (36, 100.0),
]

UNKNOWN_SCORE = 55.0


def _interpolate(anchors: list[tuple[float, float]], value: float) -> float:
    if value <= anchors[0][0]:
        return anchors[0][1]

    if value >= anchors[-1][0]:
        return anchors[-1][1]

    for (low_x, low_y), (high_x, high_y) in zip(anchors, anchors[1:]):
        if low_x <= value <= high_x:
            span = high_x - low_x
            if span == 0:
                return high_y
            ratio = (value - low_x) / span
            return low_y + ratio * (high_y - low_y)

    return UNKNOWN_SCORE  # pragma: no cover - anchors are contiguous


def score_lead_time(days: int | None) -> float:
    if days is None:
        return UNKNOWN_SCORE
    if days < 0:
        return 0.0
    return round(_interpolate(LEAD_TIME_ANCHORS, float(days)), 2)


def parse_payment_term_days(terms: str | None) -> int | None:
    """``"Net 30"`` → 30, ``"2/10 Net 30"`` → 30, ``"prepay"`` → 0.

    Returns ``None`` when the terms carry no recognisable day count, so the
    scorer can distinguish "bad terms" from "unparseable text".
    """

    if not terms:
        return None

    text = str(terms).strip().lower()

    if not text:
        return None

    if any(token in text for token in ("prepay", "pre-pay", "advance", "upfront", "up front", "cash in advance", "cia")):
        return 0

    if "cod" in text or "cash on delivery" in text:
        return 0

    digits = ""
    best: int | None = None

    for char in text:
        if char.isdigit():
            digits += char
            continue
        if digits:
            best = int(digits)
            digits = ""
    if digits:
        best = int(digits)

    if best is None:
        return None

    # "2/10 Net 30" — the *largest* number is the net period. Guard against a
    # percentage being picked up as the term length.
    return min(best, 365)


def score_payment_terms(terms: str | None) -> float:
    days = parse_payment_term_days(terms)

    if days is None:
        return UNKNOWN_SCORE

    return round(_interpolate(PAYMENT_TERM_ANCHORS, float(days)), 2)


def score_moq(moq: int | None, quantity: int) -> float:
    """Lower MOQ is better; at or below the RFQ quantity scores full marks."""

    if moq is None:
        return UNKNOWN_SCORE

    if moq <= 0:
        return 100.0

    if quantity <= 0:
        return UNKNOWN_SCORE

    if moq <= quantity:
        return 100.0

    # Penalize logarithmically: 2x the quantity is a mild problem, 100x is severe.
    ratio = moq / quantity
    penalty = min(100.0, 100.0 * math.log10(ratio) * 0.5)

    return round(max(0.0, 100.0 - penalty), 2)


def score_validity(validity: date | None, today: date) -> float:
    """Days of remaining validity. An expired quote scores zero and is flagged."""

    if validity is None:
        return UNKNOWN_SCORE

    remaining = (validity - today).days

    if remaining < 0:
        return 0.0

    return round(_interpolate([(0, 20.0), (7, 45.0), (14, 62.0), (30, 78.0), (60, 92.0), (90, 100.0)], float(remaining)), 2)


def score_warranty(months: int | None) -> float:
    if months is None:
        return UNKNOWN_SCORE

    return round(_interpolate(WARRANTY_ANCHORS, float(max(0, months))), 2)


def score_supplier_risk(rating: str | None) -> float:
    return SUPPLIER_RISK_SCORES.get((rating or "low").strip().lower(), UNKNOWN_SCORE)


def score_price(prices: list[Decimal | None], value: Decimal | None) -> float:
    """Min-max price score within the batch. Cheapest gets 100.

    When every comparable quote has the same price, or only one exists, there is
    nothing to discriminate on — everyone gets 100 and the ranking is decided by
    the other criteria. That is honest: it does not invent a difference.
    """

    known = [p for p in prices if p is not None]

    if value is None or not known:
        return 0.0

    lowest = min(known)
    highest = max(known)

    if highest == lowest:
        return 100.0

    span = highest - lowest
    ratio = (highest - value) / span

    return round(100.0 * float(ratio), 2)


def collect_risk_flags(
    result: QuoteResult,
    *,
    quantity: int,
    today: date,
    lead_time_risk_days: int = 90,
) -> list[str]:
    """Human-readable concerns. Never blocking — the buyer decides."""

    flags: list[str] = []

    if result.lead_time_days is not None:
        if result.lead_time_days >= lead_time_risk_days:
            weeks = result.lead_time_days / 7
            flags.append(
                f"Long lead time: {result.lead_time_days} days (~{weeks:.0f} weeks), "
                f"at or above the {lead_time_risk_days}-day threshold."
            )
        if (
            result.validity_date is not None
            and result.lead_time_days > (result.validity_date - today).days
            and (result.validity_date - today).days >= 0
        ):
            flags.append(
                "Quoted lead time extends beyond the quote's validity date — "
                "confirm the price still stands when the order is placed."
            )

    if result.validity_date is not None:
        remaining = (result.validity_date - today).days
        if remaining < 0:
            flags.append(
                f"Quote validity expired {abs(remaining)} day(s) ago "
                f"({result.validity_date.isoformat()})."
            )
        elif remaining <= 14:
            flags.append(
                f"Quote expires in {remaining} day(s) "
                f"({result.validity_date.isoformat()})."
            )

    if result.moq is not None and quantity and result.moq > quantity:
        flags.append(
            f"MOQ of {result.moq} exceeds the requested quantity of {quantity} — "
            f"you would be buying {result.moq - quantity} extra unit(s)."
        )

    if (result.supplier_risk or "low").lower() == "high":
        flags.append("Supplier is rated high risk.")

    payment_days = parse_payment_term_days(result.payment_terms)
    if payment_days == 0 and result.payment_terms:
        flags.append(
            f"Payment terms require payment up front ({result.payment_terms})."
        )

    if result.incompleteness_note:
        flags.append(result.incompleteness_note)

    if result.unit_mismatch:
        flags.append(
            "Unit of measure differs from the RFQ — verify before awarding."
        )

    return flags


def score_quote(
    result: QuoteResult,
    *,
    prices: list[Decimal | None],
    weights: dict[str, float],
    quantity: int,
    today: date,
) -> QuoteResult:
    """Fill ``scores`` and ``composite_score`` on a normalized quote result."""

    scores = {
        "price": score_price(prices, result.total_base),
        "lead_time": score_lead_time(result.lead_time_days),
        "payment_terms": score_payment_terms(result.payment_terms),
        "moq": score_moq(result.moq, quantity),
        "validity": score_validity(result.validity_date, today),
        "warranty": score_warranty(result.warranty_months),
        "risk": score_supplier_risk(result.supplier_risk),
    }

    result.scores = scores

    composite = sum(scores.get(criterion, 0.0) * weights.get(criterion, 0.0) for criterion in CRITERIA)

    # A quote missing required fields is still scored (the buyer may want to see
    # where it would land) but it is docked, so it can never outrank a complete
    # quote on equal economics.
    if result.completeness == "incomplete":
        missing = len(result.missing_fields)
        composite *= max(0.5, 1.0 - 0.08 * missing)

    result.composite_score = round(composite, 2)

    return result
