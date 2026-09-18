"""Incoterms normalization and rebasing.

Suppliers quote on whatever terms suit them — one says EXW Shenzhen, another DDP
your dock. Comparing those totals directly is wrong: the DDP number already
contains freight, duty, and clearance that the EXW number does not.

This module rebases every quote onto the RFQ's preferred Incoterms using an
**indicative cost ladder** expressed as a fraction of goods value:

    EXW  0%    FCA  2%    FOB  4%    CFR  7%    CIF  8%
    DAP 10%    DPU 11%    DDP 13%

``cost_at(B) = cost_at(X) * (1 + factor(B)) / (1 + factor(X))``

This is deliberately an approximation, and it is surfaced as such: every rebased
quote carries an ``incoterms_adjusted`` note and the snapshot stores the factors
used, so the buyer knows the comparison includes an estimate rather than only
quoted figures. Override the ladder with ``INCOTERM_FACTORS_JSON`` when a
category has known real freight economics.
"""

from decimal import Decimal
from decimal import InvalidOperation

#: Fraction of goods value to move the goods from the named term to DDP-like
#: delivered-at-buyer terms. Indicative, configurable, and documented.
DEFAULT_FACTORS: dict[str, float] = {
    "EXW": 0.00,  # ex works — buyer collects
    "FCA": 0.02,
    "FAS": 0.03,
    "FOB": 0.04,  # on board at origin port
    "CFR": 0.07,  # freight paid to destination port
    "CIF": 0.08,  # freight + insurance
    "CPT": 0.09,
    "CIP": 0.10,
    "DAP": 0.10,  # delivered at named place, duty unpaid
    "DPU": 0.11,
    "DDP": 0.13,  # delivered duty paid
}

ALIASES: dict[str, str] = {
    "EX WORKS": "EXW",
    "EXW": "EXW",
    "FCA": "FCA",
    "FAS": "FAS",
    "FREE ON BOARD": "FOB",
    "FOB": "FOB",
    "CFR": "CFR",
    "C AND F": "CFR",
    "C&F": "CFR",
    "CIF": "CIF",
    "CPT": "CPT",
    "CIP": "CIP",
    "DELIVERED AT PLACE": "DAP",
    "DAP": "DAP",
    "DPU": "DPU",
    "DDU": "DAP",  # legacy term, superseded by DAP
    "DELIVERED DUTY PAID": "DDP",
    "DDP": "DDP",
    "LDP": "DDP",
}

#: Terms where the supplier has already included international freight.
DELIVERED_TERMS = {"DAP", "DPU", "DDP", "CIP", "CPT"}


class UnknownIncotermError(ValueError):
    def __init__(self, term: str) -> None:
        super().__init__(f"Unrecognised Incoterms '{term}'.")
        self.term = term


def normalize_incoterm(value: str | None) -> str | None:
    """``"fob shenzhen"`` → ``"FOB"``. ``None`` when nothing recognisable."""

    if not value:
        return None

    text = str(value).strip().upper()

    if not text:
        return None

    # Longest alias first so "DELIVERED DUTY PAID" is not matched as "DDP"-adjacent
    # noise, and "C&F" is not shadowed by "C".
    for alias in sorted(ALIASES, key=len, reverse=True):
        if text.startswith(alias) or alias in text:
            return ALIASES[alias]

    return None


def describe_incoterm(value: str | None) -> dict[str, object]:
    """Normalized code plus the named place, for display."""

    if not value:
        return {"code": None, "place": None, "raw": None}

    text = str(value).strip()
    code = normalize_incoterm(text)
    place = None

    if code:
        upper = text.upper()
        alias = next(
            (a for a in sorted(ALIASES, key=len, reverse=True) if a in upper),
            None,
        )
        if alias:
            place = text[upper.index(alias) + len(alias) :].strip(" ,-") or None

    return {"code": code, "place": place, "raw": text}


def build_factor_table(overrides: dict[str, float] | None = None) -> dict[str, float]:
    factors = dict(DEFAULT_FACTORS)

    for code, value in (overrides or {}).items():
        key = (code or "").strip().upper()
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if key and numeric >= 0:
            factors[key] = numeric

    return factors


def factor_for(
    term: str | None,
    factors: dict[str, float] | None = None,
) -> float:
    table = factors if factors is not None else build_factor_table()
    code = normalize_incoterm(term)

    if code is None:
        # Unknown terms are treated as EXW-basis. The engine records a note so
        # the buyer sees that nothing was adjusted rather than assuming it was.
        return 0.0

    return table.get(code, 0.0)


def rebase_factor(
    from_term: str | None,
    to_term: str | None,
    factors: dict[str, float] | None = None,
) -> tuple[Decimal, bool]:
    """Return ``(multiplier, was_adjusted)`` to move a total from one basis to another."""

    source = factor_for(from_term, factors)
    target = factor_for(to_term, factors)

    if source == target:
        return Decimal("1"), False

    try:
        multiplier = Decimal(str(1 + target)) / Decimal(str(1 + source))
    except (InvalidOperation, ZeroDivisionError):  # pragma: no cover - defensive
        return Decimal("1"), False

    return multiplier, True
