"""Create a demo household with 8 roommates so the apps have something to show.

    python -m scripts.seed_demo

Log in as any of the demo accounts below with password `password123`. Safe to re-run.
"""

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Household, User
from app.services import households

PASSWORD = "password123"
ADMIN = ("Ann", "ann@example.com")
WITH_ACCOUNTS = [("Bea", "bea@example.com"), ("Cy", "cy@example.com")]
NAME_ONLY = ["Dev", "Eli", "Fay", "Gus", "Hal"]
HOUSE_NAME = "Demo House"


def _user(db, name: str, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(name=name, email=email, password_hash=hash_password(PASSWORD))
        db.add(user)
        db.commit()
    return user


def main() -> None:
    with SessionLocal() as db:
        admin = _user(db, *ADMIN)
        if any(m.household.name == HOUSE_NAME for m in households.memberships(db, admin)):
            print("Demo house already exists.")
            return
        me = households.create_household(db, admin, HOUSE_NAME, "America/New_York")
        house = db.get(Household, me.household_id)
        for name, email in WITH_ACCOUNTS:
            households.add_member(db, house, name, user_id=_user(db, name, email).id)
        for name in NAME_ONLY:
            households.add_member(db, house, name)
        print(f"Created '{HOUSE_NAME}' (invite code {house.invite_code}).")
        print(f"Log in as {', '.join(e for _, e in [ADMIN, *WITH_ACCOUNTS])} / {PASSWORD}")


if __name__ == "__main__":
    main()
