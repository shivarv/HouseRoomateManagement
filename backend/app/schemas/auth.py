import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


def _clean(value: str | None) -> str | None:
    return " ".join(value.split()) if isinstance(value, str) else value


class RegisterIn(BaseModel):
    """First and last name (the apps send these). Older clients send one `name`, which is split."""

    email: EmailStr
    first_name: str | None = Field(default=None, max_length=50)
    last_name: str | None = Field(default=None, max_length=50)
    name: str | None = Field(default=None, max_length=100)
    password: str = Field(min_length=8, max_length=64)

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


class VerificationSent(BaseModel):
    sent: bool  # handed to the email service
    email_enabled: bool  # False: no email service set up, so nothing can be sent yet
    already_verified: bool


class LastHouseholdIn(BaseModel):
    household_id: uuid.UUID


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
