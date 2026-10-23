"""Give every account a first name, keeping last names empty, in the database configured in .env.

    python -m scripts.backfill_user_names            # shows what would change, changes nothing
    python -m scripts.backfill_user_names --apply    # makes the changes

Migration 0012 already does this when it runs (Render runs migrations on every deploy). This is
for doing it by hand, or again later: it only touches accounts whose first name is still empty,
and sets first name = their current name (up to 50 characters), last name = "".
"""

import sys

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import User


def main(apply: bool) -> None:
    host = settings.database_url.split("@")[-1]
    with SessionLocal() as db:
        users = list(db.scalars(select(User).where(User.first_name == "").order_by(User.email)))
        print(f"Database: {host}")
        print(f"{len(users)} account(s) without a first name:")
        for user in users:
            print(f"  {user.email}: first name “{user.name.strip()[:50]}”, last name empty")
            user.first_name, user.last_name = user.name.strip()[:50], ""
        if not users:
            print("Nothing to do.")
        elif apply:
            db.commit()
            print("Saved.")
        else:
            db.rollback()
            print("Dry run: nothing saved. Run with --apply to save.")


if __name__ == "__main__":
    main("--apply" in sys.argv[1:])
