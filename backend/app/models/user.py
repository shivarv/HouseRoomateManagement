import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey


class User(UUIDPrimaryKey, Timestamps, Base):
    """Someone who can sign in. Needs a first or last name, and an email or phone: email/password
    sign-ups always have an email; Google, Apple or Facebook sign-ups may come with only a phone."""

    __tablename__ = "users"

    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True)  # lowercased
    phone: Mapped[str | None] = mapped_column(String(32), unique=True)  # contact only, not for login yet
    first_name: Mapped[str] = mapped_column(String(50), default="")
    last_name: Mapped[str] = mapped_column(String(50), default="")
    # "First Last": what houses call me by default. Kept in step with the two parts.
    name: Mapped[str] = mapped_column(String(100))
    # None: signs in only with Google, Apple or Facebook (UserIdentity).
    password_hash: Mapped[str | None] = mapped_column(String(255))
    # When their email was confirmed. Accounts that existed before checks were added count as
    # verified (migration 0015); new sign-ups stay unverified until there's an email check.
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The house the apps open on: the one picked or joined last, on any device.
    last_household_id: Mapped[uuid.UUID | None] = mapped_column(
        # households.created_by_id points back here; use_alter breaks the cycle for create/drop.
        ForeignKey(
            "households.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_users_last_household_id",
        )
    )

    identities: Mapped[list["UserIdentity"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def is_confirmed(self) -> bool:
        """A real, reachable person: a confirmed email, or signed up through Google, Apple or
        Facebook (they checked the account). Needed to become an admin."""
        return self.email_verified or bool(self.identities)

    @property
    def providers(self) -> list[str]:
        """How I can sign in: "password", "google", "apple", "facebook"."""
        return (["password"] if self.password_hash else []) + sorted({i.provider for i in self.identities})


class UserIdentity(UUIDPrimaryKey, Timestamps, Base):
    """A Google, Apple or Facebook account that signs in as this user. `subject` is the
    provider's own ID for the person (it never changes, unlike their email)."""

    __tablename__ = "user_identities"
    __table_args__ = (UniqueConstraint("provider", "subject"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(16))  # google | apple | facebook
    subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))  # what the provider said, when it said

    user: Mapped[User] = relationship(back_populates="identities")
