"""Comparison engine.

Pure domain logic: no database, no FastAPI, no network. The backend converts ORM
rows into :class:`~comparison.schemas.ComparisonInput` and persists the resulting
:class:`~comparison.schemas.ComparisonResult`, which keeps this package testable
in isolation and reusable from a script.

    >>> from comparison import ComparisonInput, QuoteInput, run_comparison
    >>> result = run_comparison(ComparisonInput(
    ...     rfq_id=1, quantity=1000, base_currency="USD", base_incoterms="FOB",
    ...     quotes=[QuoteInput(quote_id=1, supplier_name="A", unit_price="2.50")],
    ... ))
    >>> result.recommended.supplier_name
    'A'
"""

from comparison.cost import CostModelError
from comparison.cost import compute_cost
from comparison.cost import unit_price_in_base
from comparison.engine import normalize_quote
from comparison.engine import run_comparison
from comparison.exporters import comparison_to_csv
from comparison.fx import UnknownCurrencyError
from comparison.fx import build_rate_table
from comparison.fx import convert
from comparison.fx import normalize_currency_code
from comparison.incoterms import normalize_incoterm
from comparison.incoterms import rebase_factor
from comparison.recommend import build_rationale
from comparison.recommend import describe_quote
from comparison.recommend import summarize_for_buyer
from comparison.schemas import CRITERIA
from comparison.schemas import DEFAULT_WEIGHTS
from comparison.schemas import ComparisonInput
from comparison.schemas import ComparisonResult
from comparison.schemas import CostBreakdown
from comparison.schemas import QuoteInput
from comparison.schemas import QuoteResult
from comparison.schemas import normalize_weights
from comparison.score import collect_risk_flags
from comparison.score import score_quote
from comparison.units import normalize_unit
from comparison.units import price_basis_multiplier

__all__ = [
    "CRITERIA",
    "DEFAULT_WEIGHTS",
    "ComparisonInput",
    "ComparisonResult",
    "CostBreakdown",
    "CostModelError",
    "QuoteInput",
    "QuoteResult",
    "UnknownCurrencyError",
    "build_rate_table",
    "build_rationale",
    "collect_risk_flags",
    "comparison_to_csv",
    "compute_cost",
    "convert",
    "describe_quote",
    "normalize_currency_code",
    "normalize_incoterm",
    "normalize_quote",
    "normalize_unit",
    "normalize_weights",
    "price_basis_multiplier",
    "rebase_factor",
    "run_comparison",
    "score_quote",
    "summarize_for_buyer",
    "unit_price_in_base",
]
