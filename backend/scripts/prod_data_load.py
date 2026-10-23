"""Tidy existing data after deploying names, invites and verified accounts (migrations 0011–0015).

    python -m scripts.prod_data_load            # shows what would change, changes nothing
    python -m scripts.prod_data_load --apply    # makes the changes

Uses the database in .env (DATABASE_URL). Safe to re-run: each step only touches rows that still
need it. Steps:
  1. Accounts without a first name: first name = their name (up to 50 characters), last name empty.
  2. Accounts not yet verified: mark verified now (existing users count as verified for now).
  3. House members with an account: copy the account's email onto the membership.
  4. Email invites for someone already in that house: mark them accepted.
"""

import sys
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import HouseholdInvite, HouseholdMember, User


def main(apply: bool) -> None:
    now = datetime.now(UTC)
    with SessionLocal() as db:
        print(f"Database: {settings.database_url.split('@')[-1]}")
        print("Mode:", "APPLY (saving changes)" if apply else "dry run (nothing is saved)")

        users = list(db.scalars(select(User).order_by(User.email)))
        unnamed = [u for u in users if not u.first_name]
        print(f"\n1. {len(unnamed)} of {len(users)} account(s) need a first name")
        for u in unnamed:
            print(f"   {u.email}: “{u.name.strip()[:50]}”")
            u.first_name, u.last_name = u.name.strip()[:50], ""

        unverified = [u for u in users if u.email_verified_at is None]
        print(f"2. {len(unverified)} account(s) to mark verified")
        for u in unverified:
            print(f"   {u.email}")
            u.email_verified_at = now

        members = list(
            db.scalars(
                select(HouseholdMember).where(
                    HouseholdMember.user_id.is_not(None), HouseholdMember.email.is_(None)
                )
            ).unique()
        )
        print(f"3. {len(members)} membership(s) to copy the account email onto")
        for m in members:
            print(f"   {m.display_name} in {m.household.name}: {m.user.email}")
            m.email = m.user.email.lower()

        joined = {
            (m.household_id, m.user.email.lower())
            for m in db.scalars(
                select(HouseholdMember).where(HouseholdMember.user_id.is_not(None), HouseholdMember.is_active)
            ).unique()
        }
        settled = [
            i
            for i in db.scalars(select(HouseholdInvite).where(HouseholdInvite.accepted_at.is_(None))).unique()
            if (i.household_id, i.email) in joined
        ]
        print(f"4. {len(settled)} email invite(s) for people already in the house")
        for i in settled:
            print(f"   {i.email} → {i.household.name}")
            i.accepted_at = now

        if apply:
            db.commit()
            print("\nSaved.")
        else:
            db.rollback()
            print("\nDry run: nothing saved. Run with --apply to save.")


if __name__ == "__main__":
    main("--apply" in sys.argv[1:])
