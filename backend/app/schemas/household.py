import uuid
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Unknown timezone: {value}") from exc
    return value


class MemberBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str


class MemberOut(MemberBrief):
    role: Literal["admin", "member"]
    is_active: bool
    has_account: bool


class MemberCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)


class MemberUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    role: Literal["admin", "member"] | None = None


class HouseholdCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def _tz(cls, value: str) -> str:
        return _validate_timezone(value)


class HouseholdUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    timezone: str | None = None

    @field_validator("timezone")
    @classmethod
    def _tz(cls, value: str | None) -> str | None:
        return None if value is None else _validate_timezone(value)


class HouseholdOut(BaseModel):
    id: uuid.UUID
    name: str
    timezone: str
    invite_code: str
    my_member_id: uuid.UUID
    my_role: Literal["admin", "member"]


class HouseholdDetail(HouseholdOut):
    members: list[MemberOut]


class InvitePreview(BaseModel):
    household_id: uuid.UUID
    household_name: str
    unclaimed_members: list[MemberBrief]


class InviteAccept(BaseModel):
    """Claim an existing (name-only) member, or omit member_id to join as a new member."""

    member_id: uuid.UUID | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
