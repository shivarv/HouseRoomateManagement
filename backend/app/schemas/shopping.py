import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.household import MemberBrief

ShoppingCategory = Literal["groceries", "toiletries", "cleaning", "household", "other"]
ShoppingStatus = Literal["needed", "bought"]


def _clean(value: str | None) -> str | None:
    return " ".join(value.split()) if isinstance(value, str) else value


class ShoppingItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    quantity: str | None = Field(default=None, max_length=40)
    category: ShoppingCategory | None = None  # guessed from the name when left out
    note: str | None = Field(default=None, max_length=200)

    _strip = field_validator("name", "quantity", "note", mode="before")(_clean)


class ShoppingItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    quantity: str | None = Field(default=None, max_length=40)  # "" clears it
    category: ShoppingCategory | None = None
    note: str | None = Field(default=None, max_length=200)  # "" clears it

    _strip = field_validator("name", "quantity", "note", mode="before")(_clean)


class ShoppingBought(BaseModel):
    item_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)


class ShoppingItemOut(BaseModel):
    id: uuid.UUID
    name: str
    quantity: str | None
    category: ShoppingCategory
    note: str | None
    status: ShoppingStatus
    added_by: MemberBrief | None
    bought_by: MemberBrief | None
    bought_at: datetime | None
    created_at: datetime
    can_undo: bool  # bought, and I bought it or added it


class ShoppingList(BaseModel):
    needed: list[ShoppingItemOut]  # oldest first
    recently_bought: list[ShoppingItemOut]  # last 14 days, newest first
    suggestions: list[str]  # things this house bought before that aren't on the list now
