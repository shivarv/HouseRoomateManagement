"""Sign in with Google, Apple or Facebook.

The apps run the provider's own sign-in screen and send us what it returns: an ID token (a JWT the
provider signed: Google, Apple, and Facebook on iOS) or a Facebook access token (web). We check it
with the provider, then:

1. that provider account already signs in as someone → that person;
2. else the provider vouches for an email that has an account → link it, and sign in;
3. else a new account, once it has a first or last name, and an email or phone. Whatever the
   provider didn't give (Apple shares the name only the first time; some Facebook accounts have no
   email) the app asks for, then sends again with the same token.
"""

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import User, UserIdentity
from app.services.errors import BadRequest, Conflict

PROVIDERS = ("google", "apple", "facebook")

GOOGLE_JWKS = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
APPLE_JWKS = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"
# Facebook Login on iOS returns an OpenID token ("Limited Login") instead of an access token.
FACEBOOK_JWKS = "https://limited.facebook.com/.well-known/oauth/openid/jwks/"
FACEBOOK_ISSUERS = ("https://www.facebook.com", "https://limited.facebook.com")
FACEBOOK_GRAPH = "https://graph.facebook.com/v19.0"

_jwks: dict[str, jwt.PyJWKClient] = {}


@dataclass
class Profile:
    """What a provider says about the person."""

    provider: str
    subject: str
    email: str | None
    email_verified: bool
    first_name: str
    last_name: str


def _split(values: str | None) -> list[str]:
    return [v.strip() for v in (values or "").split(",") if v.strip()]


def config() -> dict:
    """What the apps need to show each provider's button. A provider with no IDs set is left out."""
    out: dict = {}
    if settings.google_web_client_id or settings.google_ios_client_id:
        out["google"] = {"web_client_id": settings.google_web_client_id, "ios_client_id": settings.google_ios_client_id}
    if settings.facebook_app_id:
        out["facebook"] = {"app_id": settings.facebook_app_id}
    out["apple"] = {"web_services_id": settings.apple_web_services_id}  # iOS needs nothing from us
    return out


def _decode(token: str, jwks_url: str, audiences: list[str], issuers: tuple[str, ...] | str, nonce: str | None) -> dict:
    if not audiences:
        raise BadRequest("This sign-in option isn't set up yet")
    client = _jwks.setdefault(jwks_url, jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=3600))
    try:
        key = client.get_signing_key_from_jwt(token)
        claims = jwt.decode(token, key.key, algorithms=["RS256", "ES256"], audience=audiences, issuer=issuers)
    except (jwt.PyJWTError, jwt.PyJWKClientError) as e:
        raise BadRequest("That sign-in didn't work or has expired. Try again.") from e
    if nonce is not None and claims.get("nonce") != nonce:
        raise BadRequest("That sign-in didn't work or has expired. Try again.")
    return claims


def _truthy(value) -> bool:
    return value is True or str(value).lower() == "true"


def verify(provider: str, token: str, nonce: str | None = None) -> Profile:
    """Checks the token with the provider. Raises BadRequest if it isn't valid for our app."""
    if provider == "google":
        audiences = _split(settings.google_web_client_id) + _split(settings.google_ios_client_id)
        c = _decode(token, GOOGLE_JWKS, audiences, GOOGLE_ISSUERS, nonce)
        return Profile("google", c["sub"], c.get("email"), _truthy(c.get("email_verified")),
                       c.get("given_name", ""), c.get("family_name", ""))
    if provider == "apple":
        c = _decode(token, APPLE_JWKS, _split(settings.apple_client_ids), APPLE_ISSUER, nonce)
        # Apple sends the name to the app only, the first time; the app passes it along.
        return Profile("apple", c["sub"], c.get("email"), _truthy(c.get("email_verified")), "", "")
    if provider == "facebook":
        if token.count(".") == 2:  # iOS: an OpenID token
            c = _decode(token, FACEBOOK_JWKS, _split(settings.facebook_app_id), FACEBOOK_ISSUERS, nonce)
            return Profile("facebook", c["sub"], c.get("email"), bool(c.get("email")),
                           c.get("given_name", ""), c.get("family_name", ""))
        return _facebook_access_token(token)
    raise BadRequest("Unknown sign-in option")


def _get_json(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=10) as res:  # noqa: S310 - fixed https host
            return json.loads(res.read())
    except Exception as e:  # network trouble or a 4xx from Facebook: either way, not signed in
        raise BadRequest("That sign-in didn't work or has expired. Try again.") from e


def _facebook_access_token(token: str) -> Profile:
    """Web: ask Facebook whether the token was made for our app, then who it's for."""
    if not settings.facebook_app_id or not settings.facebook_app_secret:
        raise BadRequest("This sign-in option isn't set up yet")
    app_token = f"{settings.facebook_app_id}|{settings.facebook_app_secret}"
    check = _get_json(f"{FACEBOOK_GRAPH}/debug_token?" + urllib.parse.urlencode({"input_token": token, "access_token": app_token}))
    data = check.get("data") or {}
    if not data.get("is_valid") or str(data.get("app_id")) != settings.facebook_app_id:
        raise BadRequest("That sign-in didn't work or has expired. Try again.")
    me = _get_json(f"{FACEBOOK_GRAPH}/me?" + urllib.parse.urlencode({"fields": "id,first_name,last_name,email", "access_token": token}))
    # Facebook only returns emails it has confirmed.
    return Profile("facebook", me["id"], me.get("email"), bool(me.get("email")), me.get("first_name", ""), me.get("last_name", ""))


def find_or_create(db: Session, profile: Profile, *, first_name: str, last_name: str,
                   email: str | None, phone: str | None) -> tuple[User | None, list[str]]:
    """The user this provider account signs in as, made or linked if need be.

    `first_name` etc. are what the person typed in the app, for what the provider didn't give.
    Returns (user, []) when signed in, or (None, missing) when a new account still needs
    "name" and/or "contact".
    """
    identity = db.scalar(select(UserIdentity).where(UserIdentity.provider == profile.provider,
                                                    UserIdentity.subject == profile.subject))
    if identity is not None:
        return identity.user, []

    provider_email = profile.email.lower() if profile.email else None
    if provider_email and profile.email_verified:
        user = db.scalar(select(User).where(User.email == provider_email))
        if user is not None:
            # The provider confirms this is their email: the same person, now with one more way in.
            _link(db, user, profile, provider_email)
            if user.email_verified_at is None:
                user.email_verified_at = datetime.now(UTC)
            db.commit()
            return user, []

    first = (profile.first_name or first_name).strip()[:50]
    last = (profile.last_name or last_name).strip()[:50]
    address = provider_email or (email.lower().strip() if email else None)
    phone = phone.strip() if phone else None
    missing = ([] if first or last else ["name"]) + ([] if address or phone else ["contact"])
    if missing:
        return None, missing
    if address and db.scalar(select(User.id).where(User.email == address)):
        raise Conflict("An account with this email already exists. Log in with your password first.")
    if phone and db.scalar(select(User.id).where(User.phone == phone)):
        raise Conflict("An account with this phone number already exists.")

    user = User(
        email=address,
        phone=phone,
        first_name=first,
        last_name=last,
        name=f"{first} {last}".strip(),
        password_hash=None,
        # Confirmed only if the provider vouched for it; a typed-in email isn't.
        email_verified_at=datetime.now(UTC) if provider_email and profile.email_verified else None,
    )
    db.add(user)
    db.flush()
    _link(db, user, profile, provider_email)
    db.commit()
    db.refresh(user)
    return user, []


def _link(db: Session, user: User, profile: Profile, email: str | None) -> None:
    # Through the relationship, so `user.providers` includes it straight away.
    user.identities.append(UserIdentity(provider=profile.provider, subject=profile.subject, email=email))
