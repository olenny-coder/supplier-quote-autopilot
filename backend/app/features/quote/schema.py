from decimal import Decimal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import computed_field


class QuoteCreate(BaseModel):
    supplier_name: str = Field(
        min_length=1,
        max_length=255,
    )

    unit_price: Decimal = Field(
        gt=0,
        decimal_places=2,
    )

    currency: str = Field(
        min_length=1,
        max_length=10,
    )

    lead_time: int = Field(
        ge=0,
    )

    payment_terms: str | None = None

    remarks: str | None = None


class QuoteUpdate(BaseModel):
    supplier_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    unit_price: Decimal | None = Field(
        default=None,
        gt=0,
        decimal_places=2,
    )

    currency: str | None = Field(
        default=None,
        min_length=1,
        max_length=10,
    )

    lead_time: int | None = Field(
        default=None,
        ge=0,
    )

    payment_terms: str | None = None

    remarks: str | None = None


class QuoteResponse(BaseModel):
    id: int

    rfq_id: int

    supplier_name: str

    unit_price: Decimal

    currency: str

    lead_time: int

    payment_terms: str | None

    remarks: str | None

    quantity: int

    model_config = ConfigDict(
        from_attributes=True,
    )

    @computed_field
    @property
    def total_price(self) -> Decimal:
        return self.unit_price * self.quantity