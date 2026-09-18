from datetime import date

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class RFQCreate(BaseModel):
    item_name: str = Field(
        min_length=1,
        max_length=255,
    )

    specification: str = Field(
        min_length=1,
        max_length=1000,
    )

    quantity: int = Field(
        gt=0,
    )

    delivery_expectation: date

    notes: str | None = None


class RFQUpdate(BaseModel):
    item_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    specification: str | None = Field(
        default=None,
        min_length=1,
        max_length=1000,
    )

    quantity: int | None = Field(
        default=None,
        gt=0,
    )

    delivery_expectation: date | None = None

    notes: str | None = None


class RFQResponse(BaseModel):
    id: int

    item_name: str

    specification: str

    quantity: int

    delivery_expectation: date

    notes: str | None

    model_config = ConfigDict(
        from_attributes=True,
    )