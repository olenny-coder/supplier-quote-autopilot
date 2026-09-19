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

#: Response time in HOURS -> score. The services counterpart of a lead time, and the
#: number a facilities manager actually cares about: a burst pipe is not a
#: production schedule. The curve is steep at the fast end on purpose — the
#: difference between a 2-hour and a 24-hour response is a different kind of service
#: rather than a marginal improvement — and it flattens once you are past a day.
RESPONSE_TIME_ANCHORS: list[tuple[float, float]] = [
    (0, 100.0),
    (2, 100.0),
    (4, 92.0),
    (8, 82.0),
    (24, 62.0),    # next business day
    (48, 45.0),
    (72, 32.0),
    (168, 15.0),   # a week
    (336, 5.0),
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


def score_response_time(hours: int | None) -> float:
    """How fast someone is on site. Steeper than a lead time, for good reason.

    A supplier who states no response time scores the neutral value rather than
    zero: a missing SLA is a gap to chase, not evidence of bad service. That keeps
    the ranking honest while the follow-up engine asks for the number.
    """

    if hours is None:
        return UNKNOWN_SCORE

    if hours < 0:
        return 0.0

    return round(_interpolate(RESPONSE_TIME_ANCHORS, float(hours)), 2)


def score_compliance(
    held: list[str] | None,
    required: list[str] | None,
) -> float:
    """Accreditation coverage against what the RFQ asked for.

    This is the one criterion that can make a quote *unsafe* rather than merely
    worse. A contractor without an EMA Licensed Electrical Worker cannot legally
    carry out electrical minor works in Singapore, so a cheap bid from one is not a
    saving — it is a compliance problem, and the score has to say so loudly.

    Returns 100 when the RFQ required nothing: absence of a requirement is not a
    failure to meet it. Partial coverage is scored proportionally, but a quote with
    none of the required credentials scores zero rather than the neutral value,
    because "did not answer" and "does not hold the licence" are different problems.
    """

    required = [item.strip() for item in (required or []) if item and item.strip()]

    if not required:
        return 100.0 if held else UNKNOWN_SCORE

    if not held:
        return 0.0

    held_normalized = {item.strip().casefold() for item in held if item}

    matched = sum(
        1 for item in required if item.casefold() in held_normalized
    )

    return round(100.0 * matched / len(required), 2)


def missing_accreditations(
    held: list[str] | None,
    required: list[str] | None,
) -> list[str]:
    """The required credentials this supplier did not claim, verbatim as asked."""

    required = [item for item in (required or []) if item and item.strip()]

    if not required:
        return []

    held_normalized = {item.strip().casefold() for item in (held or []) if item}

    return [item for item in required if item.strip().casefold() not in held_normalized]


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


def format_percent(value: Decimal | float | int | None) -> str:
    """A rate as a person writes it: ``9``, never ``9.00`` and never ``9E+1``.

    Needed because the *same* rate formats two different ways depending on where it
    came from. A rate parsed from a supplier's submission is ``Decimal('9')`` and
    renders as "9%", while the same figure after a round trip through the
    ``Numeric(5, 2)`` column is ``Decimal('9.00')`` and renders as "9.00%" — because
    ``Decimal.__format__`` honours the coefficient's significance under ``:g``. Two
    spellings of one number in one screen is exactly the kind of thing that makes a
    buyer wonder whether they are looking at two different figures.
    """

    if value is None:
        return "0"

    text = f"{Decimal(str(value)):f}"  # 'f' never produces scientific notation

    if "." in text:
        text = text.rstrip("0").rstrip(".")

    return text or "0"


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

    # ---------------------------------------------------------------- services
    if result.missing_accreditations:
        listed = ", ".join(result.missing_accreditations)
        flags.append(
            f"Does not hold required accreditation: {listed}. Confirm the work can "
            f"be carried out lawfully before awarding."
        )

    if result.response_time_hours is None:
        flags.append(
            "No response time (SLA) stated — confirm how quickly they will attend."
        )
    elif result.response_time_hours > 24:
        flags.append(
            f"Response time of {result.response_time_hours}h exceeds one business day."
        )

    if result.gst_rate and result.breakdown.tax_derived_from_rate:
        flags.append(
            f"GST added at {format_percent(result.gst_rate)}% from the rate stated on "
            f"the quote, not from an explicit tax figure."
        )

    if result.callout_charge is None and result.response_time_hours is not None:
        # Not a defect, but the single most common surprise on a maintenance
        # invoice, so it is worth asking about even when the price looks complete.
        flags.append(
            "No callout/attendance charge stated — confirm whether attendance is "
            "billed separately from the works."
        )

    if result.materials_markup_pct is not None and result.materials_markup_pct > 20:
        flags.append(
            f"Materials markup of {format_percent(result.materials_markup_pct)}% is "
            f"above the 20% typically accepted for minor works."
        )

    return flags


def score_quote(
    result: QuoteResult,
    *,
    prices: list[Decimal | None],
    weights: dict[str, float],
    quantity: int,
    today: date,
    required_accreditations: list[str] | None = None,
) -> QuoteResult:
    """Fill ``scores`` and ``composite_score`` on a normalized quote result."""

    scores = {
        "price": score_price(prices, result.total_base),
        "response_time": score_response_time(result.response_time_hours),
        "lead_time": score_lead_time(result.lead_time_days),
        "compliance": score_compliance(
            result.compliance_accreditations, required_accreditations
        ),
        "payment_terms": score_payment_terms(result.payment_terms),
        "moq": score_moq(result.moq, quantity),
        "validity": score_validity(result.validity_date, today),
        "warranty": score_warranty(result.warranty_months),
        "risk": score_supplier_risk(result.supplier_risk),
    }

    result.scores = scores

    composite = sum(
        scores.get(criterion, 0.0) * weights.get(criterion, 0.0)
        for criterion in CRITERIA
    )

    # A licence the buyer required and the supplier does not hold is not a scoring
    # nuance — the work cannot legally be carried out. Capping the composite at 25
    # keeps such a quote visible and rankable (the buyer may want to see it, and a
    # quote is never silently dropped) while guaranteeing it cannot win on price.
    if required_accreditations:
        missing = missing_accreditations(
            result.compliance_accreditations, required_accreditations
        )

        if missing:
            result.missing_accreditations = missing
            composite = min(composite, 25.0)

    # A quote missing required fields is still scored (the buyer may want to see
    # where it would land) but it is docked, so it can never outrank a complete
    # quote on equal economics.
    if result.completeness == "incomplete":
        missing_count = len(result.missing_fields)
        composite *= max(0.5, 1.0 - 0.08 * missing_count)

    result.composite_score = round(composite, 2)

    return result
