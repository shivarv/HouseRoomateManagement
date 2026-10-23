"""Guided set-up of a new house from a template: details, then people, chores, groceries and bills."""

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.bill import AmountType, PayerMode
from app.schemas.bill import Frequency as BillFrequency
from app.schemas.chore import AssignmentMode, Frequency
from app.schemas.household import HouseholdCreate

MAX_ITEMS = 10  # per list; also the most people a template house starts with


def _clean(value: str | None) -> str | None:
    return " ".join(value.split()) if isinstance(value, str) else value


def _unique(names: list[str], what: str) -> None:
    seen: set[str] = set()
    for name in names:
        if name.lower() in seen:
            raise ValueError(f"Two {what} are both called “{name}”")
        seen.add(name.lower())


class SetupChore(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    frequency: Frequency = "daily"
    assignment_mode: AssignmentMode = "rotation"
    # Who takes turns, in order, by name (me or roommates). Left out: everyone in the house.
    people: list[str] | None = Field(default=None, max_length=MAX_ITEMS)

    _strip = field_validator("name", mode="before")(_clean)

    @field_validator("people", mode="before")
    @classmethod
    def _names(cls, value):
        return [_clean(v) for v in value] if isinstance(value, list) else value


class SetupGrocery(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    category_key: str = Field(default="other", min_length=1, max_length=40)

    _strip = field_validator("name", mode="before")(_clean)


class SetupBill(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    icon: str = Field(default="🧾", min_length=1, max_length=16)
    payer_mode: PayerMode = "anyone"
    payer_name: str | None = None  # payer_mode "one": me or one of the roommates, by name
    frequency: BillFrequency = "monthly"
    due_day: int = Field(default=1, ge=1, le=31)
    amount_type: AmountType = "fixed"
    amount_cents: int | None = Field(default=None, ge=0, le=100_000_000)

    _strip = field_validator("name", "icon", "payer_name", mode="before")(_clean)

    @model_validator(mode="after")
    def _check(self):
        if self.frequency == "weekly" and self.due_day > 7:
            raise ValueError(f"{self.name}: for weekly bills, due_day is 1 = Monday … 7 = Sunday")
        if self.payer_mode == "one" and not self.payer_name:
            raise ValueError(f"{self.name}: pick who pays it")
        return self


class HouseholdSetup(HouseholdCreate):
    """Everything a new house starts with, created in one go (all or nothing)."""

    # Besides me, by name. None is fine: people can join later with the invite code.
    roommates: list[str] = Field(default=[], max_length=MAX_ITEMS - 1)
    chores: list[SetupChore] = Field(min_length=1, max_length=MAX_ITEMS)  # at least one to begin with
    groceries: list[SetupGrocery] = Field(default=[], max_length=MAX_ITEMS)  # may be none
    bills: list[SetupBill] = Field(min_length=1, max_length=MAX_ITEMS)  # at least one to begin with
    currency: str = Field(default="USD", min_length=3, max_length=3)

    @field_validator("roommates", mode="before")
    @classmethod
    def _names(cls, value):
        return [_clean(v) for v in value] if isinstance(value, list) else value

    @model_validator(mode="after")
    def _check(self):
        if any(not 1 <= len(n) <= 100 for n in self.roommates):
            raise ValueError("Every roommate needs a name (up to 100 characters)")
        _unique(self.roommates, "roommates")
        _unique([c.name for c in self.chores], "chores")
        _unique([g.name for g in self.groceries], "grocery items")
        _unique([b.name for b in self.bills], "bills")
        if not self.currency.isalpha():
            raise ValueError("currency must be a 3-letter code like USD or INR")
        self.currency = self.currency.upper()
        return self


class SetupTemplate(BaseModel):
    """Defaults to prefill the set-up screens with, up to `max_items` of each."""

    max_items: int
    chores: list[SetupChore]
    groceries: list[SetupGrocery]
    bills: list[SetupBill]
    categories: list[dict]  # {key, label, icon}: what groceries can be filed under
