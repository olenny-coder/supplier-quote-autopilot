"""Value normalization shared by the heuristic and LLM parse paths.

Both paths end up here: the LLM returns loosely-typed JSON and the regex fallback
returns raw substrings, and both must become the same typed values. Keeping the
coercion in one module means the two paths cannot disagree about what "2 weeks"
means.

Every function returns ``None`` rather than a default when it is unsure — the
parser's contract is verbatim-or-null, and a default here would violate it.
"""

import re
from datetime import date
from datetime import timedelta
from decimal import Decimal
from decimal import InvalidOperation

MONEY_RE = re.compile(r"(-?\d[\d,\s]*(?:\.\d+)?)")
CURRENCY_RE = re.compile(r"\b([A-Z]{3})\b")

#: "2 weeks", "3-4 weeks", "15 business days", "45 days", "6 wks"
LEAD_TIME_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:-|to|–)?\s*(\d+(?:\.\d+)?)?\s*"
    r"(business\s+days?|working\s+days?|days?|weeks?|wks?|months?|mos?)",
    re.IGNORECASE,
)

MOQ_RE = re.compile(
    r"(?:moq|minimum\s+(?:order\s+)?(?:quantity|qty)|min\.?\s*(?:order|qty))"
    r"\s*(?:of|is|:|=)?\s*([\d,]+)",
    re.IGNORECASE,
)

WARRANTY_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:-)?\s*(year|years|yr|yrs|month|months|mo)\b",
    re.IGNORECASE,
)

VALIDITY_RE = re.compile(
    r"(?:valid|validity|expir\w*|quote\s+valid)\D{0,24}?"
    r"(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})",
    re.IGNORECASE,
)

RELATIVE_VALIDITY_RE = re.compile(
    r"valid\D{0,16}?(\d+)\s*(day|days|week|weeks|month|months)",
    re.IGNORECASE,
)

#: Phrases that mean "there is no answer here" — never treated as values.
NEGATIVE_PATTERNS = (
    "tbd",
    "t.b.d",
    "to be determined",
    "to be confirmed",
    "to be advised",
    "will advise",
    "will confirm",
    "not sure",
    "not yet",
    "n/a",
    "na",
    "unknown",
    "pending",
    "checking with",
    "let you know",
    "get back to you",
)

#: Phrases that mean "explicitly none" — an ANSWER, not a gap (ForgeFlow rule).
DECLINED_PATTERNS = (
    "no moq",
    "no minimum",
    "none",
    "no minimum order",
    "not applicable",
    "no nre",
    "no setup",
    "no charge",
    "no warranty",
    "exempt",
)

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def is_negative(text: str | None) -> bool:
    """True when the text says "no answer yet" rather than giving one."""

    if not text:
        return False

    lowered = str(text).strip().lower()

    return any(pattern in lowered for pattern in NEGATIVE_PATTERNS)


def is_declined(text: str | None) -> bool:
    """True when the text explicitly says there is none — which IS an answer."""

    if not text:
        return False

    lowered = str(text).strip().lower()

    return any(pattern in lowered for pattern in DECLINED_PATTERNS)


def clean_text(value: object) -> str | None:
    if value is None:
        return None

    text = str(value).strip()

    return text or None


# ------------------------------------------------------------------------- money
def parse_money(value: object) -> Decimal | None:
    """Extract a decimal from ``"USD 45.00/pc"``, ``"1,250"``, ``45``, or ``null``."""

    if value is None:
        return None

    if isinstance(value, Decimal):
        return value

    if isinstance(value, (int, float)):
        return Decimal(str(value))

    text = str(value).strip()

    if not text or is_negative(text):
        return None

    match = MONEY_RE.search(text)

    if not match:
        return None

    cleaned = match.group(1).replace(",", "").replace(" ", "")

    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_int(value: object) -> int | None:
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(round(value))

    text = str(value).strip()

    if not text or is_negative(text):
        return None

    match = MONEY_RE.search(text.replace(",", ""))

    if not match:
        return None

    try:
        return int(Decimal(match.group(1)))
    except (InvalidOperation, ValueError):
        return None


# --------------------------------------------------------------------- currency
def parse_currency(value: object) -> str | None:
    """First 3-letter uppercase token, or a well-known symbol."""

    if value is None:
        return None

    text = str(value).strip().upper()

    if not text:
        return None

    symbols = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "₹": "INR"}

    for symbol, code in symbols.items():
        if symbol in text:
            return code

    if len(text) == 3 and text.isalpha():
        return text

    match = CURRENCY_RE.search(text)

    return match.group(1) if match else None


# ------------------------------------------------------------------- lead time
def parse_lead_time_days(value: object) -> int | None:
    """Normalize any lead-time phrasing into CALENDAR days.

    A range takes its **upper** bound and a business-day figure is converted at
    7/5. Both choices are deliberately conservative: over-stating a lead time makes
    a supplier look slightly worse, under-stating it makes the buyer plan a launch
    around a date that will not be met.
    """

    if value is None:
        return None

    if isinstance(value, int) and not isinstance(value, bool):
        return value if value >= 0 else None

    text = str(value).strip()

    if not text or is_negative(text):
        return None

    match = LEAD_TIME_RE.search(text)

    if not match:
        return parse_int(value)

    low = float(match.group(1))
    high = float(match.group(2)) if match.group(2) else low
    unit = match.group(3).lower()

    magnitude = max(low, high)

    if unit.startswith(("week", "wk")):
        days = magnitude * 7
    elif unit.startswith(("month", "mo")):
        days = magnitude * 30
    elif unit.startswith(("business", "working")):
        days = magnitude * 7 / 5
    else:
        days = magnitude

    return int(round(days))


# ------------------------------------------------------------------------- MOQ
def parse_moq(value: object) -> int | None:
    if value is None:
        return None

    if is_negative(str(value)):
        return None

    if is_declined(str(value)):
        return 0

    text = str(value)

    match = MOQ_RE.search(text)

    if match:
        return parse_int(match.group(1))

    return parse_int(text)


# -------------------------------------------------------------------- warranty
def parse_warranty_months(value: object) -> int | None:
    if value is None:
        return None

    if isinstance(value, int) and not isinstance(value, bool):
        return value if value >= 0 else None

    text = str(value).strip()

    if not text or is_negative(text):
        return None

    if is_declined(text):
        return 0

    match = WARRANTY_RE.search(text)

    if not match:
        return None

    magnitude = float(match.group(1))
    unit = match.group(2).lower()

    if unit.startswith(("year", "yr")):
        return int(round(magnitude * 12))

    return int(round(magnitude))


# -------------------------------------------------------------------- validity
def parse_date(value: object, reference: date | None = None) -> date | None:
    """Parse an absolute date, or a relative "valid 30 days" against a reference."""

    if value is None:
        return None

    if isinstance(value, date):
        return value

    text = str(value).strip()

    if not text or is_negative(text):
        return None

    # ISO first — unambiguous.
    iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None

    # "31 Dec 2026" / "31 December 2026" / "Dec 31, 2026"
    named = re.search(
        r"(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})", text
    ) or re.search(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})", text)

    if named:
        groups = named.groups()
        if groups[0].isdigit():
            day, month_name, year = groups
        else:
            month_name, day, year = groups
        month = MONTHS.get(str(month_name).lower())
        if month:
            try:
                return date(int(year), month, int(day))
            except ValueError:
                return None

    # dd/mm/yyyy or mm/dd/yyyy — assume day-first outside the US-style cases
    # where the first component is > 12.
    slashed = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", text)
    if slashed:
        first, second, year = (int(part) for part in slashed.groups())
        if year < 100:
            year += 2000
        day, month = (second, first) if first > 12 else (first, second)
        try:
            return date(year, month, day)
        except ValueError:
            return None

    relative = RELATIVE_VALIDITY_RE.search(text)
    if relative and reference is not None:
        magnitude = int(relative.group(1))
        unit = relative.group(2).lower()
        if unit.startswith("week"):
            delta = timedelta(weeks=magnitude)
        elif unit.startswith("month"):
            delta = timedelta(days=magnitude * 30)
        else:
            delta = timedelta(days=magnitude)
        return reference + delta

    return None


def parse_validity_date(value: object, reference: date | None = None) -> date | None:
    """Find a validity date in free text, then fall back to relative phrasing."""

    if value is None:
        return None

    text = str(value).strip()

    if not text or is_negative(text):
        return None

    match = VALIDITY_RE.search(text)

    if match:
        parsed = parse_date(match.group(1), reference)
        if parsed:
            return parsed

    return parse_date(text, reference)


def normalize_incoterms(value: object) -> str | None:
    """Delegate to the comparison engine so both sides agree on one vocabulary."""

    from comparison.incoterms import normalize_incoterm

    if value is None:
        return None

    text = str(value).strip()

    if not text or is_negative(text):
        return None

    code = normalize_incoterm(text)

    if code is None:
        return None

    # Preserve the named place: "FOB Shenzhen" is materially different from "FOB".
    upper = text.upper()
    place = ""
    for token in ("EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"):
        index = upper.find(token)
        if index != -1:
            place = text[index + len(token) :].strip(" ,-")
            break

    return f"{code} {place}".strip() if place else code


def normalize_payment_terms(value: object) -> str | None:
    if value is None:
        return None

    text = str(value).strip()

    if not text or is_negative(text):
        return None

    return text[:255]


def normalize_unit_text(value: object) -> str | None:
    from comparison.units import normalize_unit

    if value is None:
        return None

    text = str(value).strip()

    if not text or is_negative(text):
        return None

    normalized = normalize_unit(text)

    if normalized.pack_size:
        return f"{normalized.canonical} of {normalized.pack_size}"

    return normalized.canonical
