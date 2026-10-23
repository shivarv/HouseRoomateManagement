import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.household import MemberBrief

# A GroceryCategory.key of the item's house. The defaults are groceries, toiletries, cleaning,
# household and other; admins can add more, so this is checked against the house, not a list.
ShoppingCategory = Annotated[str, Field(min_length=1, max_length=40)]
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


class GroceryCategoryOut(BaseModel):
    id: uuid.UUID
    key: str
    label: str
    icon: str
    position: int
    can_delete: bool  # every category but "other", the fallback


class GroceryPresetOut(BaseModel):
    id: uuid.UUID
    name: str
    category_key: str
    position: int


class GrocerySuggestion(BaseModel):
    """Something people added that isn't a quick-add item yet: the admin can add or dismiss it."""

    name: str  # the most recent spelling
    times_added: int
    category_key: str  # the category it was last filed under


class ShoppingList(BaseModel):
    needed: list[ShoppingItemOut]  # oldest first
    recently_bought: list[ShoppingItemOut]  # last 14 days, newest first
    categories: list[GroceryCategoryOut]  # the house's sections, in display order
    quick_add: list[GroceryPresetOut]  # the admin's quick-add items, alphabetical


class GrocerySettings(BaseModel):
    categories: list[GroceryCategoryOut]
    presets: list[GroceryPresetOut]
    suggestions: list[GrocerySuggestion]  # most added first


class GroceryCategoryCreate(BaseModel):
    label: str = Field(min_length=1, max_length=40)
    icon: str = Field(default="🛍️", min_length=1, max_length=16)

    _strip = field_validator("label", "icon", mode="before")(_clean)


class GroceryCategoryUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=40)
    icon: str | None = Field(default=None, min_length=1, max_length=16)

    _strip = field_validator("label", "icon", mode="before")(_clean)


class GroceryPresetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    category_key: ShoppingCategory | None = None  # guessed from the name when left out

    _strip = field_validator("name", mode="before")(_clean)


class GroceryPresetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    category_key: ShoppingCategory | None = None

    _strip = field_validator("name", mode="before")(_clean)


class GroceryOrder(BaseModel):
    """Every category of the house, in the new order."""

    ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class GrocerySuggestionDismiss(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    _strip = field_validator("name", mode="before")(_clean)
