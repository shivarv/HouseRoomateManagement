import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.household import MemberBrief

HelpStatus = Literal["open", "done"]


def _clean(value: str | None) -> str | None:
    return value.strip() if value is not None else None


class HelpRequestCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)  # a preset or the person's own words
    details: str | None = Field(default=None, max_length=500)

    _strip = field_validator("title", "details", mode="before")(_clean)


class HelpRequestUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    details: str | None = Field(default=None, max_length=500)  # "" clears it

    _strip = field_validator("title", "details", mode="before")(_clean)


class HelpRequestOut(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    household_name: str
    requester: MemberBrief
    title: str
    details: str | None
    status: HelpStatus
    done_by: MemberBrief | None
    done_at: datetime | None
    created_at: datetime
    updated_at: datetime
    is_mine: bool  # I asked: I can edit or withdraw it while it's open
    can_reopen: bool  # I asked, or I marked it done
