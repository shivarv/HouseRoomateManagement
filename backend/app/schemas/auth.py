import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

NEXT_PATH = r"^/([^/\\\s]\S*)?$"  # a path on our own site: no other hosts


def _clean(value: str | None) -> str | None:
    return " ".join(value.split()) if isinstance(value, str) else value


class RegisterIn(BaseModel):
    """First and last name (the apps send these). Older clients send one `name`, which is split."""

    email: EmailStr
    first_name: str | None = Field(default=None, max_length=50)
    last_name: str | None = Field(default=None, max_length=50)
    name: str | None = Field(default=None, max_length=100)
    password: str = Field(min_length=8, max_length=64)
    # Where the verification link should land afterwards, e.g. "/join/CODE" (a path in the web app).
    next: str | None = Field(default=None, max_length=300, pattern=NEXT_PATH)

    _strip = field_validator("first_name", "last_name", "name", mode="before")(_clean)

    @model_validator(mode="after")
    def _names(self):
        if not self.first_name and self.name:
            first, _, last = self.name.partition(" ")
            self.first_name, self.last_name = first[:50], (self.last_name or last)[:50]
        if not self.first_name:
            raise ValueError("Add your first name")
        return self


class ProfileUpdate(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(default="", max_length=50)

    _strip = field_validator("first_name", "last_name", mode="before")(_clean)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    name: str  # "First Last"
    email_verified: bool  # User.email_verified
    # May point at a house I've since left; clients fall back to my first house.
    last_household_id: uuid.UUID | None = None


class VerifyEmailIn(BaseModel):
    token: str = Field(min_length=10, max_length=2000)


class RegisterOut(BaseModel):
    """Signed up, not signed in: the link we emailed confirms the address and signs them in."""

    email: str
    sent: bool  # handed to the email service
    email_enabled: bool  # False: no email service set up, so the link is only in the server log


class VerifyEmailOut(BaseModel):
    user: UserOut
    # Only the first time the link is opened: it signs them in. Later opens just confirm.
    access_token: str | None = None


class ResendVerificationIn(BaseModel):
    email: EmailStr
    next: str | None = Field(default=None, max_length=300, pattern=NEXT_PATH)


class ResendVerificationOut(BaseModel):
    """The same answer whether or not the account exists, so this can't be used to find accounts."""

    email_enabled: bool


class LastHouseholdIn(BaseModel):
    household_id: uuid.UUID


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
