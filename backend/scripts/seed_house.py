"""Load the real household into the database configured in .env (Neon in production).

    python -m scripts.seed_house

Creates one account per roommate (email = name without spaces, lowercase, @gmail.com), the
household "Home" with Shiva as admin, and puts everyone in the Cooking and
"Cleaning Hall and Other" rotations in the order below. Dispose garbage stays open to anyone.
No history is created, so everyone starts at 0. Safe to re-run: it stops if "Home" exists.
"""

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Household, User
from app.services import chores, clock, households

ROOMMATES = ["Jai Vicky", "Sakthivel", "Krishna", "Suraj", "Shiva", "Sameer", "Raghu", "Lauhitya"]
ADMIN = "Shiva"
HOUSE_NAME = "Home"
# The real address isn't in the repo; the admin sets it in Settings → House details.
ADDRESS = "Not set yet: edit in Settings"
TIMEZONE = "America/New_York"
PASSWORD = "password123"
RENAME = {"Clean hall": "Cleaning Hall and Other"}


def email_for(name: str) -> str:
    return name.replace(" ", "").lower() + "@gmail.com"


def _user(db, name: str) -> User:
    email = email_for(name)
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(name=name, email=email, password_hash=hash_password(PASSWORD))
        db.add(user)
        db.commit()
    return user


def main() -> None:
    with SessionLocal() as db:
        admin = _user(db, ADMIN)
        if any(m.household.name == HOUSE_NAME for m in households.memberships(db, admin)):
            print(f"'{HOUSE_NAME}' already exists for {ADMIN}; nothing to do.")
            return

        me = households.create_household(db, admin, HOUSE_NAME, ADDRESS, TIMEZONE)
        house = db.get(Household, me.household_id)
        member_ids = {ADMIN: me.id}
        for name in ROOMMATES:
            if name != ADMIN:
                user = _user(db, name)
                member_ids[name] = households.add_member(db, house, name, user_id=user.id).id

        today = clock.today_in(TIMEZONE)
        order = [member_ids[name] for name in ROOMMATES]
        for chore in chores.list_chores(db, house.id):
            chore.name = RENAME.get(chore.name, chore.name)
            if not chore.is_open:
                chores.set_rotation(db, chore, order, today)
        db.commit()

        print(f"Created '{HOUSE_NAME}' ({TIMEZONE}), admin {ADMIN}, invite {house.invite_code}.")
        for chore in chores.list_chores(db, house.id):
            names = " → ".join(r.member.display_name for r in chore.rotation)
            kind = "anyone" if chore.is_open else names
            print(f"  {chore.name}: {kind}")
        print("Accounts (password: " + PASSWORD + "):")
        for name in ROOMMATES:
            print(f"  {name:<10} {email_for(name)}")


if __name__ == "__main__":
    main()
