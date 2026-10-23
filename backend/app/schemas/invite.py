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
    # sent: emailed now · saved: kept, but emailing isn't set up · failed: kept, but the email
    # didn't go out (see reason) · member: already in the house
    status: Literal["sent", "saved", "failed", "member"]
    # failed only: bad_address (check the address) · unavailable (email service down: try again
    # later) · refused (our email setup: see the server log)
    reason: Literal["bad_address", "unavailable", "refused"] | None = None


class EmailInviteResults(BaseModel):
    results: list[EmailInviteResult]
    link: str  # the house's invite link, for sharing another way
    email_enabled: bool


class MyInvite(BaseModel):
    """A house that invited my email and I haven't joined yet."""

    household_name: str
    invite_code: str  # older apps join with this; new ones use `token`
    token: str  # the private invite link: /invite/{token}
    invited_by: str | None
    created_at: datetime


class InviteLinkPublic(BaseModel):
    """What a private invite link shows before signing in."""

    household_name: str
    people: int
    email: str  # who it's for, so they sign up / log in with that address
