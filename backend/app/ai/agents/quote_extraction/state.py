"""Graph state for the quote-extraction agent."""

from typing import TypedDict

from app.ai.agents.quote_extraction.schemas import ExtractedQuotes


class QuoteExtractionState(TypedDict):
    pdf_bytes: bytes
    extracted_quotes: ExtractedQuotes | None
