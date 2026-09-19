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

#: Ordinary three-letter words that are NOT currencies but can appear uppercase
#: (headings, acronyms, units of measure). Without this, "MOQ" or "PCS" would be
#: accepted as a currency code.
NON_CURRENCY_TOKENS = frozenset(
    {
        "MOQ", "PCS", "PC", "EA", "UOM", "RFQ", "PO", "VAT", "GST", "TBD", "EXP",
        "INC", "LTD", "GMBH", "SPA", "SL", "BV", "AG", "LLC", "PLC", "CO", "SA",
        "NRE", "COO", "FOB", "CIF", "EXW", "DDP", "DAP", "CFR", "CPT", "CIP",
        "FCA", "FAS", "DPU", "DDU", "LDP", "ETA", "ETD", "PCS.", "NET",
    }
)


def _currency_reference() -> tuple[dict[str, str], frozenset[str]]:
    """Aliases and known codes, taken from the comparison engine's FX table.

    Sourced from one place so the parser and the engine cannot disagree about which
    codes exist. Imported defensively: ``comparison`` is a sibling package, and the
    parser should still work (with a reduced alias set) if it is unavailable.
    """

    try:
        from comparison.fx import CURRENCY_ALIASES as _aliases
        from comparison.fx import DEFAULT_RATES

        return dict(_aliases), frozenset(DEFAULT_RATES)
    except Exception:  # noqa: BLE001 - degrade, never crash the parser
        return (
            {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "₹": "INR"},
            frozenset({"USD", "EUR", "GBP", "JPY", "CNY", "INR"}),
        )


CURRENCY_ALIASES, KNOWN_CURRENCY_CODES = _currency_reference()

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
#:
#: Matched on WORD BOUNDARIES, not as bare substrings. Substring matching made
#: "final" contain "na" and "analysis" contain "na", so a stated price like
#: "final price 3.00" was silently discarded as a non-answer. Every entry here is
#: a phrase a supplier would write to mean "not yet answered".
NEGATIVE_PATTERNS = (
    "tbd",
    "t.b.d",
    "to be determined",
    "to be confirmed",
    "to be advised",
    "to be discussed",
    "will advise",
    "will confirm",
    "will revert",
    "not sure",
    "not yet",
    "n/a",
    "unknown",
    "pending",
    "checking with",
    "let you know",
    "get back to you",
    "cannot confirm",
    "unable to confirm",
)

#: Compiled once. ``\b`` around the phrase stops "na" matching inside "final".
_NEGATIVE_RE = re.compile(
    r"|".join(rf"\b{re.escape(pattern)}\b" for pattern in NEGATIVE_PATTERNS),
    re.IGNORECASE,
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

    return bool(_NEGATIVE_RE.search(str(text).strip()))


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
    """Extract an ISO-4217 code from a field value or free text.

    Two guards, both learned from real failures:

    * **A code must be uppercase in the source text.** Uppercasing the whole input
      first turned ordinary words into currencies — "we try to ship quickly"
      became the Turkish lira, which is in the FX table, so the comparison engine
      cheerfully converted at the lira rate instead of reporting the quote as
      incomparable. Currencies are written uppercase; prose is not.
    * **A non-answer is not a currency.** "TBD" is three uppercase letters, so it
      used to be returned as a code and then blew up later with the confusing
      "No FX rate for 'TBD'" instead of being treated as a missing field.
    """

    if value is None:
        return None

    text = str(value).strip()

    if not text or is_negative(text):
        return None

    symbols = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "₹": "INR"}

    for symbol, code in symbols.items():
        if symbol in text:
            return code

    # Only uppercase tokens count: scan the ORIGINAL text, do not uppercase it.
    for token in re.findall(r"\b[A-Z]{3}\b", text):
        if token in CURRENCY_ALIASES:
            return CURRENCY_ALIASES[token]
        if token not in NON_CURRENCY_TOKENS:
            return token

    # A lowercase code is only accepted when the input IS the code ("usd", "eur",
    # "inr"). Scanning free text case-insensitively would accept "TRY" from "we try
    # to ship quickly" — a real currency in the FX table, so the engine would
    # convert at the lira rate rather than reporting the quote as incomparable.
    stripped = text.strip().strip(".,;:")

    if len(stripped) == 3 and stripped.isalpha() and stripped.islower():
        upper = stripped.upper()

        if upper in CURRENCY_ALIASES:
            return CURRENCY_ALIASES[upper]

        if upper in KNOWN_CURRENCY_CODES and upper not in NON_CURRENCY_TOKENS:
            return upper

    return None


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


# --------------------------------------------------------------- response time
#: "4 hours", "within 2 hrs", "same day", "2 working days".
#:
#: Deliberately a separate pattern from ``LEAD_TIME_RE``: a lead time is how long
#: production takes, a response time is how fast someone attends site, and mixing
#: them up would score a supplier on the wrong dimension entirely.
RESPONSE_TIME_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:-|to|–)?\s*(\d+(?:\.\d+)?)?\s*"
    r"(business\s+days?|working\s+days?|minutes?|mins?|hours?|hrs?|h|days?|weeks?|wks?)\b",
    re.IGNORECASE,
)

#: Phrases a maintenance supplier writes instead of a number, mapped to hours.
#:
#: Checked before the numeric pattern, so "within the same day" is not read as the
#: "1 day" that the digit-free text would otherwise fail to match at all.
#: Ordered longest-first within each meaning so "next business day" wins over
#: "next day".
RESPONSE_TIME_PHRASES: tuple[tuple[str, int], ...] = (
    ("next business day", 24),
    ("next working day", 24),
    ("same business day", 8),
    ("same working day", 8),
    ("same-day", 8),
    ("same day", 8),
    ("within the day", 8),
    ("next day", 24),
    ("immediate", 1),
    ("emergency", 4),
    ("24/7", 4),
    ("24x7", 4),
    ("round the clock", 4),
)


def parse_response_time_hours(value: object) -> int | None:
    """Normalize an SLA into whole hours.

    A range takes its **upper** bound, matching the lead-time rule and for the same
    reason: quoting the optimistic end of "2-4 hours" would make a supplier look
    faster than they promised, and the buyer would plan an outage around a number
    nobody committed to.

    Sub-hour SLAs are recorded as 1 hour rather than 0. The scoring anchors are
    whole hours, and 0 would read as instantaneous — a claim no supplier made.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if value >= 0 else None

    if isinstance(value, float):
        return int(round(value)) if value >= 0 else None

    text = str(value).strip()

    if not text or is_negative(text):
        return None

    lowered = text.lower()

    for phrase, hours in RESPONSE_TIME_PHRASES:
        if phrase in lowered:
            return hours

    match = RESPONSE_TIME_RE.search(text)

    if not match:
        # A bare number in a response-time field is hours, not days: the field is
        # labelled, so "4" means four hours to the supplier who typed it.
        return parse_int(text)

    low = float(match.group(1))
    high = float(match.group(2)) if match.group(2) else low
    unit = match.group(3).lower()

    magnitude = max(low, high)

    if unit.startswith(("week", "wk")):
        hours = magnitude * 7 * 24
    elif unit.startswith(("d", "business", "working")):
        # A working day is still a day of elapsed time on the clock, so an SLA of
        # "2 working days" is 48 hours. It is the *lead time* rule that converts
        # working days to calendar days at 7/5, because there production only
        # advances on weekdays — here the supplier is simply not attending at night.
        hours = magnitude * 24
    elif unit.startswith("min"):
        hours = magnitude / 60
    else:  # hour, hr, h
        hours = magnitude

    return max(1, int(round(hours)))


# ------------------------------------------------------------------ percentages
PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)")


def parse_percent(value: object, *, maximum: float = 100.0) -> Decimal | None:
    """Normalize a percentage, e.g. a GST rate or a materials markup.

    A value between 0 and 1 written *without* a per cent sign is read as a
    fraction: ``0.09`` means 9%, because 0.09% is not a rate anyone charges. The
    guard stops short of 1, which stays 1% — "1" is far more likely to mean one
    per cent than a hundred.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    had_sign = False

    if isinstance(value, Decimal):
        amount = value
    elif isinstance(value, (int, float)):
        amount = Decimal(str(value))
    else:
        text = str(value).strip()

        if not text or is_negative(text):
            return None

        if is_declined(text):
            return Decimal("0")

        had_sign = "%" in text

        match = PERCENT_RE.search(text)

        if not match:
            return None

        try:
            amount = Decimal(match.group(1))
        except InvalidOperation:
            return None

    if not had_sign and Decimal("0") < amount < Decimal("1"):
        amount = amount * 100

    if amount < 0 or amount > Decimal(str(maximum)):
        return None

    return amount


# --------------------------------------------------------------- accreditations
#: Split ONLY on unambiguous separators.
#:
#: ``/`` and ``&`` are deliberately absent: they appear *inside* real credentials
#: ("LEW/Technician", "Lift & Escalator"), and splitting on them would invent two
#: accreditations the supplier never claimed. The whole point of this field is that
#: a missing required credential caps the quote's score, so a false positive here
#: is worse than a missed one.
ACCREDITATION_SPLIT_RE = re.compile(r"[,;|\n\r]+")

#: Cap on how many credentials are recorded. A paste of a whole company profile
#: should not become 200 rows in a comparison table.
MAX_ACCREDITATIONS = 20


def parse_accreditations(value: object) -> list[str]:
    """Split a free-text credential list into individual, de-duplicated items."""

    if value is None:
        return []

    if isinstance(value, (list, tuple, set, frozenset)):
        items = [str(item) for item in value]
    else:
        text = str(value).strip()

        if not text or is_negative(text) or is_declined(text):
            return []

        items = ACCREDITATION_SPLIT_RE.split(text)

    collected: list[str] = []
    seen: set[str] = set()

    for item in items:
        cleaned = str(item).strip().strip(".,;:-–—*•")

        if not cleaned or is_negative(cleaned):
            continue

        key = cleaned.lower()

        if key in seen:
            continue

        seen.add(key)
        collected.append(cleaned[:120])

    return collected[:MAX_ACCREDITATIONS]


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
    from comparison.units import display_rate_basis
    from comparison.units import normalize_unit

    if value is None:
        return None

    text = str(value).strip()

    if not text or is_negative(text):
        return None

    normalized = normalize_unit(text)

    if normalized.pack_size:
        return f"{normalized.canonical} of {normalized.pack_size}"

    # A service rate basis is a phrase, and collapsing it loses the word that makes
    # it one: "per point" became "point" and "lump sum" became "service", so the
    # stored quote — and every API client reading it — showed the buyer "162.00
    # service" as the basis. `display_rate_basis` keeps the phrase for the basis
    # codes and returns the canonical code for a real unit of measure, so "PCS" is
    # still "pcs" and "box of 100" is still "box of 100".
    return display_rate_basis(text, fallback=normalized.canonical)
