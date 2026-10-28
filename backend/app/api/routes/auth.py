from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas.auth import (
    AuthProvidersOut,
    LastHouseholdIn,
    LoginIn,
    OAuthIn,
    OAuthOut,
    PasswordIn,
    ProfileUpdate,
    RegisterIn,
    RegisterOut,
    ResendVerificationIn,
    ResendVerificationOut,
    TokenOut,
    UserOut,
    VerifyEmailIn,
    VerifyEmailOut,
)
from app.services import email, households, oauth, verification

router = APIRouter(prefix="/auth", tags=["auth"])


def full_name(first: str, last: str) -> str:
    return f"{first} {last}".strip()


def _token(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/register", response_model=RegisterOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: DbSession):
    """Not signed in yet: the emailed link confirms the address and signs them in."""
    address = body.email.lower()
    if db.scalar(select(User.id).where(User.email == address)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    first, last = body.first_name, body.last_name or ""
    user = User(
        email=address,
        first_name=first,
        last_name=last,
        name=full_name(first, last),
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    sent = verification.send(user, body.next)  # a failed email doesn't fail sign-up; they can ask again
    return RegisterOut(email=user.email, sent=sent, email_enabled=email.enabled())


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: DbSession):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is not None and user.password_hash is None:
        names = " or ".join(p.title() for p in user.providers) or "Google, Apple or Facebook"
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"This account signs in with {names}. Use that button instead.")
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.email_verified:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Confirm your email first: open the link we sent you."
        )
    return _token(user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(user: CurrentUser, db: DbSession):
    """Deletes my account for good (App Store rule: sign-up means in-app deletion)."""
    households.delete_account(db, user)


@router.get("/providers", response_model=AuthProvidersOut)
def providers():
    """Which "Continue with …" buttons the apps show, and the IDs each needs (none are secret)."""
    return oauth.config()


@router.post("/oauth/{provider}", response_model=OAuthOut)
def oauth_sign_in(provider: str, body: OAuthIn, db: DbSession):
    """Sign in (or up) with Google, Apple or Facebook. A new account may first need a name, or an
    email or phone: then `missing` says which, and the app sends the same token again with them."""
    if provider not in oauth.PROVIDERS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown sign-in option")
    profile = oauth.verify(provider, body.token, body.nonce)
    try:
        user, missing, created = oauth.find_or_create(
            db, profile, first_name=body.first_name, last_name=body.last_name, email=body.email, phone=body.phone
        )
    except oauth.AccountExists as e:
        return OAuthOut(existing_email=e.email)
    if user is None:
        return OAuthOut(missing=missing, first_name=profile.first_name, last_name=profile.last_name, email=profile.email)
    return OAuthOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user), created=created)


def _check_provider(provider: str) -> None:
    if provider not in oauth.PROVIDERS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown sign-in option")


def _tell(tasks: BackgroundTasks, user: User, change: str) -> None:
    """Emails me when a way to sign in changes, so I'd notice if it wasn't me."""
    if user.email and email.enabled():
        text = (f"Hi {user.first_name or user.name},\n\n{change}\n\n"
                "If this wasn't you, set a new password in Roommates → Profile, or reply to this email.")
        tasks.add_task(email.send, user.email, "A sign-in change on your Roommates account", text)


@router.post("/me/identities/{provider}", response_model=UserOut)
def link_sign_in(provider: str, body: OAuthIn, db: DbSession, user: CurrentUser, tasks: BackgroundTasks):
    """Connects Google, Apple or Facebook to my account (Profile → Ways to sign in, or after
    logging in with my password because that provider's email matched it). Then any of them signs
    in as me."""
    _check_provider(provider)
    user, linked = oauth.link(db, user, oauth.verify(provider, body.token, body.nonce))
    if linked:
        _tell(tasks, user, f"{provider.title()} was connected: you can now sign in with it.")
    return user


@router.delete("/me/identities/{provider}", response_model=UserOut)
def unlink_sign_in(provider: str, db: DbSession, user: CurrentUser, tasks: BackgroundTasks):
    """Disconnects Google, Apple or Facebook. Not the last way I can sign in."""
    _check_provider(provider)
    user = oauth.unlink(db, user, provider)
    _tell(tasks, user, f"{provider.title()} was disconnected: it no longer signs in to your account.")
    return user


@router.put("/me/password", response_model=UserOut)
def set_password(body: PasswordIn, db: DbSession, user: CurrentUser, tasks: BackgroundTasks):
    """Sets a first password (accounts made with Google, Apple or Facebook), or changes mine (it
    asks for the current one). Logging in with it uses my email."""
    if user.email is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add an email first: it's what you log in with.")
    had_password = user.password_hash is not None
    if had_password and not (body.current_password and verify_password(body.current_password, user.password_hash)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Your current password isn't right")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    _tell(tasks, user, "Your password was changed." if had_password else "A password was set: you can now log in with your email too.")
    return user


@router.patch("/me", response_model=UserOut)
def update_profile(body: ProfileUpdate, db: DbSession, user: CurrentUser):
    """My name, and my phone. An email can be added when I don't have one yet. I always keep a
    first or last name, and an email or phone. Houses keep the name they call me unless it was my
    old full name."""
    if body.email is not None and user.email is None:
        address = body.email.lower()
        if db.scalar(select(User.id).where(User.email == address)):
            raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
        user.email = address
    if body.phone is not None:
        phone = body.phone or None
        if phone is None and user.email is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Keep a phone number or add an email")
        if phone and db.scalar(select(User.id).where(User.phone == phone, User.id != user.id)):
            raise HTTPException(status.HTTP_409_CONFLICT, "Another account already uses this phone number")
        user.phone = phone
    old = user.name
    user.first_name, user.last_name = body.first_name, body.last_name
    user.name = full_name(body.first_name, body.last_name)
    for member in households.memberships(db, user):
        if member.display_name == old:  # never renamed in that house: follow the new name
            member.display_name = user.name
    db.commit()
    return user


@router.post("/verify-email", response_model=VerifyEmailOut)
def verify_email(body: VerifyEmailIn, db: DbSession):
    """The link in the email proves the address. The first open also signs them in."""
    user, first_time = verification.verify(db, body.token)
    token = create_access_token(user.id) if first_time else None
    return VerifyEmailOut(user=UserOut.model_validate(user), access_token=token)


@router.post("/resend-verification", response_model=ResendVerificationOut)
def resend_verification(body: ResendVerificationIn, db: DbSession):
    """Send the link again (signed out: they can't sign in yet). Says nothing about whether the
    account exists."""
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is not None and not user.email_verified:
        verification.send(user, body.next)
    return ResendVerificationOut(email_enabled=email.enabled())


@router.put("/me/last-household", response_model=UserOut)
def set_last_household(body: LastHouseholdIn, db: DbSession, user: CurrentUser):
    """Remember the house I switched to, so every device opens on it next time."""
    households.require_membership(db, body.household_id, user)
    user.last_household_id = body.household_id
    db.commit()
    return user
