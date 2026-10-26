from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas.auth import (
    LastHouseholdIn,
    LoginIn,
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
from app.services import email, households, verification

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


@router.patch("/me", response_model=UserOut)
def update_profile(body: ProfileUpdate, db: DbSession, user: CurrentUser):
    """My first and last name. Houses keep the name they call me unless it was my old full name."""
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
