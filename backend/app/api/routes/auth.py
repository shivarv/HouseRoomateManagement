from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas.auth import LastHouseholdIn, LoginIn, RegisterIn, TokenOut, UserOut
from app.services import households

router = APIRouter(prefix="/auth", tags=["auth"])


def _token(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: DbSession):
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    return _token(user)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: DbSession):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return _token(user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@router.put("/me/last-household", response_model=UserOut)
def set_last_household(body: LastHouseholdIn, db: DbSession, user: CurrentUser):
    """Remember the house I switched to, so every device opens on it next time."""
    households.require_membership(db, body.household_id, user)
    user.last_household_id = body.household_id
    db.commit()
    return user
