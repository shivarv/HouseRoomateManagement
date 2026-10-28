import re
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

NEXT_PATH = r"^/([^/\\\s]\S*)?$"  # a path on our own site: no other hosts
PHONE = r"^\+?[0-9()\-\s]{7,20}$"  # contact only for now; no SMS checks


def _clean(value: str | None) -> str | None:
    return " ".join(value.split()) if isinstance(value, str) else value


def _check_phone(value: str | None) -> str | None:
    if value and not re.fullmatch(PHONE, value):
        raise ValueError("Enter a phone number, like +1 617 555 0100")
    return value


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
        if not self.first_name and not self.last_name:
            raise ValueError("Add your first or last name")
        return self


class ProfileUpdate(BaseModel):
    """At least a first or last name. `phone: ""` clears it (if I still have an email)."""

    first_name: str = Field(default="", max_length=50)
    last_name: str = Field(default="", max_length=50)
    phone: str | None = Field(default=None, max_length=32)
    # Only for accounts without one yet (some social sign-ups): changing an email isn't supported.
    email: EmailStr | None = None

    _strip = field_validator("first_name", "last_name", "phone", mode="before")(_clean)
    _phone = field_validator("phone")(_check_phone)

    @model_validator(mode="after")
    def _names(self):
        if not self.first_name and not self.last_name:
            raise ValueError("Add your first or last name")
        return self


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class PasswordIn(BaseModel):
    """A first password (`current_password` left out), or a new one (it's required then)."""

    current_password: str | None = None
    new_password: str = Field(min_length=8, max_length=64)


class IdentityOut(BaseModel):
    """A connected Google, Apple or Facebook account."""

    model_config = ConfigDict(from_attributes=True)

    provider: str
    email: str | None  # what that provider says (Apple may give a private relay address)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str | None  # None: signed up with Google, Apple or Facebook with only a phone
    phone: str | None = None
    first_name: str
    last_name: str
    name: str  # "First Last"
    email_verified: bool  # User.email_verified
    providers: list[str] = []  # how I can sign in: "password", "google", "apple", "facebook"
    identities: list[IdentityOut] = []  # the connected providers, with their emails
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


class OAuthIn(BaseModel):
    """What the provider's sign-in screen returned, plus anything the person typed for what the
    provider didn't share (Apple gives the name only the first time; the app passes it here)."""

    token: str = Field(min_length=20, max_length=8000)  # an ID token, or a Facebook access token
    nonce: str | None = Field(default=None, max_length=200)  # Apple / Facebook iOS: checked against the token
    first_name: str = Field(default="", max_length=50)
    last_name: str = Field(default="", max_length=50)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)

    _strip = field_validator("first_name", "last_name", "phone", mode="before")(_clean)
    _phone = field_validator("phone")(_check_phone)


class OAuthOut(BaseModel):
    """Signed in (`access_token` + `user`), or a new account that needs `missing` first: "name"
    (a first or last name) and/or "contact" (an email or phone). Send the same token again with them."""

    access_token: str | None = None
    token_type: str = "bearer"
    user: UserOut | None = None
    created: bool = False  # a brand-new account: the apps say welcome
    missing: list[str] = []
    # This email already has a password account: log in with it, then link (POST /auth/me/identities).
    existing_email: str | None = None
    # What the provider already told us, to prefill the "finish your profile" form.
    first_name: str = ""
    last_name: str = ""
    email: str | None = None


class AuthProvidersOut(BaseModel):
    """Which sign-in buttons to show, and the IDs each one needs."""

    google: dict | None = None
    apple: dict | None = None
    facebook: dict | None = None
