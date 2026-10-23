"""Email verification: a signed link sent at sign-up (and on request) that confirms the address.

Without an email service (no RESEND_API_KEY) nothing is sent; the link is logged instead, so it
can be tested locally.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import VERIFY_EMAIL_DAYS, create_email_token, decode_email_token
from app.models import User
from app.services import email
from app.services.errors import BadRequest

log = logging.getLogger(__name__)


def link(user: User) -> str:
    return f"{settings.web_url.rstrip('/')}/verify-email?token={create_email_token(user.id, user.email)}"


def send(user: User) -> bool:
    """True when the email was handed to the email service."""
    url = link(user)
    text = (
        f"Hi {user.first_name or user.name}!\n\n"
        f"Confirm your email for Roommates by opening this link:\n{url}\n\n"
        f"It works for {VERIFY_EMAIL_DAYS} days. If you didn't sign up, you can ignore this email.\n"
    )
    sent = email.send(user.email, "Confirm your email for Roommates", text)
    if not sent:
        log.info("Email verification link for %s (not emailed): %s", user.email, url)
    return sent


def verify(db: Session, token: str) -> User:
    decoded = decode_email_token(token)
    user = db.get(User, decoded[0]) if decoded else None
    if user is None:
        raise BadRequest(
            "This link doesn't work or has expired. Ask for a new one from your profile."
        )
    if user.email.lower() != decoded[1]:
        raise BadRequest("This link was for a different email address. Ask for a new one.")
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)
        db.commit()
    return user
