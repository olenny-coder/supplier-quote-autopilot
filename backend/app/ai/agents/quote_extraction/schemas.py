"""Structured-output schemas for the quote-extraction agent."""

from decimal import Decimal

from pydantic import BaseModel
from pydantic import Field


class ExtractedQuote(BaseModel):
    supplier_name: str | None = Field(
        default=None,
        description="Supplier name",
    )

    unit_price: Decimal | None = Field(
        default=None,
        description="Quoted unit price",
    )

    currency: str | None = Field(
        default=None,
        description="Currency code",
    )

    lead_time: int | None = Field(
        default=None,
        description="Lead time in days",
    )

    payment_terms: str | None = Field(
        default=None,
        description="Payment terms",
    )

    remarks: str | None = Field(
        default=None,
        description="Additional remarks",
    )


class ExtractedQuotes(BaseModel):
    quotes: list[ExtractedQuote]
