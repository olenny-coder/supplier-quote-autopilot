"""Unit-of-measure normalization.

The RFQ asks for a quantity in a unit ("1000 pcs"). A supplier may quote per
"box of 100", per "kg", or per "set". Comparing a per-box price against a per-piece
price without noticing is one of the most expensive silent errors in procurement.

This module does two things:

* **Canonicalise** the unit string so "PCS", "pcs.", "pieces", "EA" all collapse.
* **Detect a mismatch** against the RFQ's unit and report it, rather than
  guessing a conversion factor. There is no reliable way to convert "kg" into
  "pcs" without the part's weight, so the engine excludes such a quote from
  ranked comparison and tells the buyer why.

Explicit, pack-size-aware conversions (``BOX/100``) *are* applied, because the
supplier stated the pack size — that is information, not a guess.
"""

import re
from dataclasses import dataclass

#: canonical code -> aliases
UNIT_ALIASES: dict[str, tuple[str, ...]] = {
    "pcs": ("pcs", "pc", "piece", "pieces", "ea", "each", "unit", "units", "nos", "no"),
    "set": ("set", "sets", "kit", "kits"),
    "pair": ("pair", "pairs", "pr"),
    "box": ("box", "boxes", "bx", "carton", "cartons", "ctn"),
    "pallet": ("pallet", "pallets", "plt"),
    "roll": ("roll", "rolls", "reel", "reels"),
    "sheet": ("sheet", "sheets", "sh"),
    "kg": ("kg", "kgs", "kilogram", "kilograms", "kilo", "kilos"),
    "g": ("g", "gram", "grams", "gm", "gms"),
    "t": ("t", "ton", "tons", "tonne", "tonnes", "mt"),
    "lb": ("lb", "lbs", "pound", "pounds"),
    "m": ("m", "meter", "meters", "metre", "metres"),
    "cm": ("cm", "centimeter", "centimetre"),
    "mm": ("mm", "millimeter", "millimetre"),
    "ft": ("ft", "foot", "feet"),
    "in": ("in", "inch", "inches"),
    "l": ("l", "liter", "liters", "litre", "litres"),
    "ml": ("ml", "milliliter", "millilitre"),
    "sqm": ("sqm", "m2", "square meter", "square metre"),
    "hour": ("hour", "hours", "hr", "hrs"),
    "day": ("day", "days"),
    "service": ("service", "services", "lot", "lots", "job"),
}

_ALIAS_TO_CANONICAL = {
    alias: canonical for canonical, aliases in UNIT_ALIASES.items() for alias in aliases
}

#: Units that contain a countable number of discrete items, so a stated pack size
#: converts exactly into a per-piece price.
PACKABLE_UNITS = {"box", "pallet", "roll"}

#: Units that count individual items.
DISCRETE_UNITS = {"pcs", "set", "pair", "sheet"}

#: Physical size of one unit, expressed in its measurement group's base unit
#: (mass -> kg, length -> m, volume -> l, area -> m2, time -> h). Group bases
#: themselves are 1.0.
#:
#: Used to convert a *price* between units as ``size(target) / size(quoted)``:
#: 1 t = 1000 kg, so a per-tonne price becomes a per-kg price by dividing by 1000.
UNIT_SIZE_IN_BASE: dict[str, float] = {
    # mass, base kg
    "kg": 1.0,
    "g": 0.001,
    "t": 1000.0,
    "lb": 0.45359237,
    # length, base m
    "m": 1.0,
    "cm": 0.01,
    "mm": 0.001,
    "ft": 0.3048,
    "in": 0.0254,
    # volume, base l
    "l": 1.0,
    "ml": 0.001,
    # area, base m2
    "sqm": 1.0,
    # time, base hour
    "hour": 1.0,
    "day": 24.0,
}

#: "box of 100", "carton/50", "pack 250"
_PACK_RE = re.compile(
    r"\b(?:box|carton|ctn|pack|bag|drum|pallet|roll|reel)\s*(?:of|/|x|\*)?\s*(\d+)\b",
    re.IGNORECASE,
)

#: Units that are mass/volume/length — never interchangeable with a count.
_INCOMMENSURABLE_GROUPS = {
    "count": {"pcs", "set", "pair", "box", "pallet", "roll", "sheet", "service"},
    "mass": {"kg", "g", "t", "lb"},
    "length": {"m", "cm", "mm", "ft", "in"},
    "volume": {"l", "ml"},
    "area": {"sqm"},
    "time": {"hour", "day"},
}


@dataclass(slots=True)
class NormalizedUnit:
    canonical: str
    #: Multiplier from the quoted price basis to the RFQ's canonical basis.
    #: 1 unless the supplier stated a pack size that we can honour exactly.
    pack_size: int | None = None

    def describe(self) -> str:
        return f"{self.canonical} (pack of {self.pack_size})" if self.pack_size else self.canonical


def normalize_unit(value: str | None, default: str = "pcs") -> NormalizedUnit:
    """Map a free-text unit into a canonical code and any stated pack size."""

    if not value:
        return NormalizedUnit(canonical=default)

    text = str(value).strip().lower()

    if not text:
        return NormalizedUnit(canonical=default)

    pack_size = None
    pack_match = _PACK_RE.search(text)
    if pack_match:
        try:
            pack_size = int(pack_match.group(1))
        except ValueError:  # pragma: no cover - regex guarantees digits
            pack_size = None
        if pack_size is not None and pack_size <= 0:
            pack_size = None

    # Strip a trailing count so "box of 100" normalizes to "box", not "pcs".
    for alias in sorted(_ALIAS_TO_CANONICAL, key=len, reverse=True):
        if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", text):
            return NormalizedUnit(
                canonical=_ALIAS_TO_CANONICAL[alias],
                pack_size=pack_size,
            )

    return NormalizedUnit(canonical=text[:16], pack_size=pack_size)


def group_of(canonical: str) -> str | None:
    for group, members in _INCOMMENSURABLE_GROUPS.items():
        if canonical in members:
            return group
    return None


def are_comparable(left: str | None, right: str | None) -> bool:
    """True when two units sit in the same measurement group."""

    left_unit = normalize_unit(left)
    right_unit = normalize_unit(right)

    if left_unit.canonical == right_unit.canonical:
        return True

    left_group = group_of(left_unit.canonical)
    right_group = group_of(right_unit.canonical)

    if left_group is None or right_group is None:
        # Unknown units: only equal strings are comparable (handled above).
        return False

    return left_group == right_group


def price_basis_multiplier(
    quoted_unit: str | None,
    rfq_unit: str | None,
) -> tuple[float, str | None]:
    """Multiplier converting a quoted unit price onto the RFQ's unit basis.

    Returns ``(multiplier, warning)``. A warning containing "excluded" means the
    conversion could not be justified and the quote must not be ranked against
    the others.
    """

    quoted = normalize_unit(quoted_unit)
    target = normalize_unit(rfq_unit)

    # A container the supplier explicitly sized ("box of 100", "pallet/500") is
    # information, not a guess: dividing by the stated pack size is exact.
    if quoted.pack_size and quoted.canonical in PACKABLE_UNITS and target.canonical in DISCRETE_UNITS:
        return 1.0 / quoted.pack_size, (
            f"Supplier priced a {quoted.canonical} of {quoted.pack_size}; "
            f"converted to a per-{target.canonical} price."
        )

    if quoted.canonical == target.canonical:
        return 1.0, None

    if not are_comparable(quoted.canonical, target.canonical):
        return 1.0, (
            f"Quoted in '{quoted.describe()}' but this RFQ is priced in "
            f"'{target.describe()}' — no defensible conversion exists, so this "
            f"quote is excluded from ranking. Ask the supplier to re-quote."
        )

    # Same measurement group but a different unit (kg vs t, m vs cm, ...).
    #
    # The multiplier converts a PRICE, not a quantity, and those move in opposite
    # directions: 1 tonne is 1000 kg, so a per-tonne price is 1/1000 of a per-kg
    # price. Expressing each unit as its physical size in the group's base unit and
    # dividing makes that impossible to get backwards — size(target) / size(quoted),
    # not size(quoted) / size(target). Getting this wrong on a mass unit is a 10^6
    # error in the landed cost, which is enough to invert an award.
    quoted_size = UNIT_SIZE_IN_BASE.get(quoted.canonical)
    target_size = UNIT_SIZE_IN_BASE.get(target.canonical)

    if quoted_size and target_size:
        multiplier = target_size / quoted_size
        return multiplier, (
            f"Converted a per-{quoted.canonical} price to a per-{target.canonical} "
            f"price using a fixed factor of {multiplier:.6g}."
        )

    return 1.0, (
        f"Units '{quoted.describe()}' and '{target.describe()}' are not "
        f"interchangeable; this quote is excluded from ranking."
    )
