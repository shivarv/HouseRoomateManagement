import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(user_id: uuid.UUID) -> str:
    expires = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expires}, settings.jwt_secret, ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


VERIFY_EMAIL_DAYS = 3


def create_email_token(user_id: uuid.UUID, email: str) -> str:
    """A link token proving the holder can read `email`. Tied to the address, so changing it voids old links."""
    expires = datetime.now(UTC) + timedelta(days=VERIFY_EMAIL_DAYS)
    payload = {"sub": str(user_id), "email": email.lower(), "purpose": "verify_email", "exp": expires}
    return jwt.encode(payload, settings.jwt_secret, ALGORITHM)


def decode_email_token(token: str) -> tuple[uuid.UUID, str] | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        if payload.get("purpose") != "verify_email":
            return None
        return uuid.UUID(payload["sub"]), payload["email"]
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
