import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.household import MemberBrief


class InviteEmails(BaseModel):
    emails: list[EmailStr] = Field(min_length=1, max_length=20)


class EmailInviteOut(BaseModel):
    id: uuid.UUID
    email: str
    invited_by: MemberBrief | None
    created_at: datetime
    last_sent_at: datetime | None  # None: saved but not emailed (no email service set up)
    can_cancel: bool


class EmailInviteResult(BaseModel):
    email: str
    # sent: emailed now · saved: kept, but emailing isn't set up · member: already in the house
    status: Literal["sent", "saved", "member"]


class EmailInviteResults(BaseModel):
    results: list[EmailInviteResult]
    link: str  # the house's invite link, for sharing another way
    email_enabled: bool


class MyInvite(BaseModel):
    """A house that invited my email and I haven't joined yet."""

    household_name: str
    invite_code: str
    invited_by: str | None
    created_at: datetime
