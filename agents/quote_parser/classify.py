"""Classification of an inbound free-text block.

Adapted from ForgeFlow's ``ignore`` / ``supplier_quote`` / ``supplier_reminder``
taxonomy (MIT, Copyright (c) 2026 JayleeBot) — see NOTICE — but reduced to what
this project's channel actually produces.

A submission that arrives through a tokenized web form is *always* quote data:
the supplier either filled the fields in or left them blank, and there is no email
thread to reason about. The classification only matters for the free-text notes
box and for inbound replies, where three outcomes are useful:

``quote_data``  the text provides commercial values — parse it.
``question``    the text asks the buyer something and provides little else —
                escalate to the buyer instead of chasing the supplier.
``other``       an acknowledgement or unrelated content — record it, act on nothing.

The ordering is deliberate: a message that both asks a question *and* supplies
values is ``quote_data`` with a ``blocking_question`` set, not ``question``.
"""

import re

from agents.quote_parser.schemas import Classification

QUESTION_MARKERS = (
    "?",
    "could you",
    "can you",
    "would you",
    "please confirm",
    "please advise",
    "let us know",
    "we need to know",
    "which ",
    "what is the",
    "what's the",
)

OTHER_MARKERS = (
    "out of office",
    "automatic reply",
    "auto-reply",
    "on leave",
    "annual leave",
    "public holiday",
    "received your email",
    "thank you for your email",
    "unsubscribe",
)

#: Signals that commercial data is actually present.
#:
#: Deliberately excludes the bare word "price". A question that mentions pricing —
#: "What volume should we price for?" — was previously classified as quote data, so
#: a supplier waiting on the buyer got recorded as an ordinary response and then
#: chased. Ambiguous markers only count as data when the text also carries a figure
#: (see :func:`classify_text`).
DATA_MARKERS = (
    "unit price",
    "price per",
    "our price",
    "quoted price",
    "price is",
    "price:",
    "quotation attached",
    "quotation is attached",
    "please find our quote",
    "attached quotation",
    "lead time",
    "moq",
    "minimum order",
    "minimum quantity",
    "payment terms",
    "incoterms",
    "fob",
    "cif",
    "exw",
    "ddp",
    "valid until",
    "validity",
    "warranty",
)

#: Words that only mean "data" when a number is also present. Without a figure,
#: "price" and "quote" in a question are just the subject of the question.
AMBIGUOUS_MARKERS = ("price", "quote", "quotation", "cost", "discount")

DIGIT_RE = re.compile(r"\d")

CURRENCY_OR_NUMBER_RE = re.compile(
    r"(?:[$€£¥₹]\s*\d)|(?:\b\d[\d,]*(?:\.\d+)?\s*(?:USD|EUR|GBP|INR|JPY|CNY|VND|THB))|"
    r"(?:/\s*(?:pc|pcs|piece|kg|unit|set))",
    re.IGNORECASE,
)


def classify_text(raw_text: str | None) -> Classification:
    """Classify one free-text block."""

    if not raw_text or not raw_text.strip():
        return "other"

    text = raw_text.lower()

    if any(marker in text for marker in OTHER_MARKERS) and not any(
        marker in text for marker in DATA_MARKERS
    ):
        return "other"

    has_figure = bool(CURRENCY_OR_NUMBER_RE.search(raw_text)) or bool(
        DIGIT_RE.search(raw_text)
    )

    # An unambiguous data phrase counts on its own; an ambiguous one ("price")
    # only counts alongside a figure, so a question about pricing stays a question.
    has_data = any(marker in text for marker in DATA_MARKERS) or (
        has_figure and any(marker in text for marker in AMBIGUOUS_MARKERS)
    )

    has_question = any(marker in text for marker in QUESTION_MARKERS)

    if has_data:
        # Data plus a question is still data — the caller records the question
        # separately as a blocking_question.
        return "quote_data"

    if has_question:
        return "question"

    return "other"


def extract_question(raw_text: str | None) -> str | None:
    """Pull the supplier's blocking question out of free text, if there is one.

    Only sentences that actually ask something are considered. "Please let us know
    your decision" is a post-quote pleasantry, not a blocker, so it is filtered out
    here rather than being escalated to the buyer as a fake blocker.
    """

    if not raw_text:
        return None

    pleasantries = (
        "let us know your decision",
        "let us know if you",
        "looking forward to",
        "feel free to",
        "do not hesitate",
        "kind regards",
        "best regards",
    )

    sentences = re.split(r"(?<=[?.!])\s+", raw_text.replace("\n", " ").strip())

    for sentence in sentences:
        stripped = sentence.strip()

        if not stripped or "?" not in stripped:
            continue

        lowered = stripped.lower()

        if any(pleasantry in lowered for pleasantry in pleasantries):
            continue

        return stripped[:500]

    return None
