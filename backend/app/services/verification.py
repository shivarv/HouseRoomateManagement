"""Email verification: a signed link sent at sign-up (and on request) that confirms the address.

Nobody can sign in before confirming. The first time the link is opened it also signs them in;
after that it only says the email is confirmed, so a forwarded email can't be used to get in.

Without an email service nothing is sent; the link is logged instead, so it can be tested locally.
"""

import logging
from datetime import UTC, datetime
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import VERIFY_EMAIL_DAYS, create_email_token, decode_email_token
from app.models import User
from app.services import email
from app.services.errors import BadRequest

log = logging.getLogger(__name__)


def link(user: User, next_path: str | None = None) -> str:
    url = f"{settings.web_url.rstrip('/')}/verify-email?token={create_email_token(user.id, user.email)}"
    return f"{url}&next={quote(next_path, safe='/')}" if next_path else url


def send(user: User, next_path: str | None = None) -> bool:
    """True when the email was handed to the email service. `next_path`: where the link lands after."""
    url = link(user, next_path)
    text = (
        f"Hi {user.first_name or user.name}!\n\n"
        f"Confirm your email for Roommates by opening this link:\n{url}\n\n"
        f"It works for {VERIFY_EMAIL_DAYS} days. If you didn't sign up, you can ignore this email.\n"
    )
    sent = email.send(user.email, "Confirm your email for Roommates", text)
    if not sent:
        log.info("Email verification link for %s (not emailed): %s", user.email, url)
    return sent


def verify(db: Session, token: str) -> tuple[User, bool]:
    """The user, and whether this is the first time (then the link signs them in)."""
    decoded = decode_email_token(token)
    user = db.get(User, decoded[0]) if decoded else None
    if user is None:
        raise BadRequest(
            "This link doesn't work or has expired. Log in to get a new one."
        )
    if user.email.lower() != decoded[1]:
        raise BadRequest("This link was for a different email address. Ask for a new one.")
    if user.email_verified_at is not None:
        return user, False
    user.email_verified_at = datetime.now(UTC)
    db.commit()
    return user, True
