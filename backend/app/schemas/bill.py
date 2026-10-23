import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.household import MemberBrief

PayerMode = Literal["one", "anyone", "everyone"]
Frequency = Literal["monthly", "weekly", "daily"]
AmountType = Literal["fixed", "variable"]
BillStatus = Literal["paid", "due", "overdue", "upcoming"]


def _clean(value: str | None) -> str | None:
    return " ".join(value.split()) if isinstance(value, str) else value


def _currency(value: str) -> str:
    value = value.strip().upper()
    if len(value) != 3 or not value.isalpha():
        raise ValueError("currency must be a 3-letter code like USD or INR")
    return value


def _check_due_day(frequency: str | None, due_day: int | None) -> None:
    if frequency == "weekly" and due_day is not None and not 1 <= due_day <= 7:
        raise ValueError("for weekly bills, due_day is the weekday: 1 = Monday … 7 = Sunday")


class BillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    icon: str = Field(default="🧾", min_length=1, max_length=16)
    payer_mode: PayerMode = "anyone"
    payer_id: uuid.UUID | None = None  # required when payer_mode is "one"
    frequency: Frequency = "monthly"
    # monthly: day of the month (1–31); weekly: weekday (1 = Monday … 7 = Sunday); daily: ignored
    due_day: int = Field(default=1, ge=1, le=31)
    amount_type: AmountType = "fixed"
    amount_cents: int | None = Field(default=None, ge=0, le=100_000_000)  # fixed bills only
    currency: str = "USD"
    note: str | None = Field(default=None, max_length=200)

    _strip = field_validator("name", "icon", "note", mode="before")(_clean)
    _code = field_validator("currency")(lambda v: _currency(v))

    @model_validator(mode="after")
    def _due(self):
        _check_due_day(self.frequency, self.due_day)
        return self


class BillUpdate(BaseModel):
    """Only the fields sent change. `amount_cents: null`, `note: ""` and `payer_id: null` clear them."""

    name: str | None = Field(default=None, min_length=1, max_length=80)
    icon: str | None = Field(default=None, min_length=1, max_length=16)
    payer_mode: PayerMode | None = None
    payer_id: uuid.UUID | None = None
    frequency: Frequency | None = None
    due_day: int | None = Field(default=None, ge=1, le=31)
    amount_type: AmountType | None = None
    amount_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    currency: str | None = None
    note: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None

    _strip = field_validator("name", "icon", "note", mode="before")(_clean)
    _code = field_validator("currency")(lambda v: v if v is None else _currency(v))


class BillPay(BaseModel):
    member_id: uuid.UUID | None = None  # who paid; defaults to me
    period: date | None = None  # any day in the period; defaults to the current one. Not future ones.


class BillAmountSet(BaseModel):
    """A variable bill's amount for one period (admins). `null` clears it."""

    amount_cents: int | None = Field(ge=0, le=100_000_000)
    period: date | None = None  # any day in the period; defaults to the current one


class BillPaymentOut(BaseModel):
    id: uuid.UUID
    member: MemberBrief
    recorded_by: MemberBrief | None
    paid_at: datetime
    can_undo: bool  # I paid it, I recorded it, or I'm an admin


class BillPeriodOut(BaseModel):
    """One occurrence of a bill: this month's rent, this week's cleaner, today's milk."""

    period: date  # start: month start, Monday, or the day
    period_end: date
    label: str  # "Oct 2026", "Week of Oct 19", "Mon, Oct 19"
    due_date: date
    status: BillStatus  # paid; due (today or within 3 days); overdue; upcoming
    amount_cents: int | None  # fixed: the bill's amount; variable: this period's, once set
    share_cents: int | None  # everyone mode with a known amount: each person's part
    payments: list[BillPaymentOut]  # oldest first
    paid_count: int
    expected_count: int  # everyone: the active people in the house; otherwise 1
    i_paid: bool
    is_current: bool  # can be paid (not a future period)


class BillOut(BaseModel):
    id: uuid.UUID
    name: str
    icon: str
    payer_mode: PayerMode
    payer: MemberBrief | None
    frequency: Frequency
    due_day: int
    amount_type: AmountType
    amount_cents: int | None  # fixed bills: the amount that repeats
    last_amount_cents: int | None  # variable bills: the latest amount set before this period
    currency: str
    note: str | None
    position: int
    is_active: bool
    current: BillPeriodOut  # the period asked for (default: the one we're in)


class BillList(BaseModel):
    today: date  # in the house's timezone
    bills: list[BillOut]
