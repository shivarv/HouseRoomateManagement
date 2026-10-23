"""Inviting people by email. The invite is saved (so the house sees it as pending and the invited
person sees it once signed in) and emailed when an email service is set up.

The email links to a private invite (/invite/{token}), not the house code: it works only while the
invite is pending and unexpired, and only for the invited email. Cancelling it, or sending a new
one, kills the old link.
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import HouseholdInvite, HouseholdMember, User
from app.schemas.household import MemberBrief
from app.schemas.invite import EmailInviteOut, EmailInviteResult, EmailInviteResults, MyInvite
from app.services import email
from app.services.errors import Forbidden, NotFound


INVITE_DAYS = 7
EXPIRED = "This invite has expired or was cancelled. Ask your roommate for a new one."


def link(code: str) -> str:
    """The house's shared link (anyone with it can join)."""
    return f"{settings.web_url.rstrip('/')}/join/{code}"


def private_link(token: str) -> str:
    return f"{settings.web_url.rstrip('/')}/invite/{token}"


def _new_link(row: HouseholdInvite) -> None:
    """A fresh private link, good for INVITE_DAYS; any older link for this invite stops working."""
    row.token = secrets.token_urlsafe(32)
    row.expires_at = datetime.now(UTC) + timedelta(days=INVITE_DAYS)


def _message(me: HouseholdMember, url: str) -> tuple[str, str, str]:
    house = me.household
    subject = f"{me.display_name} invited you to {house.name} on Roommates"
    text = (
        f"Hi!\n\n{me.display_name} invited you to join “{house.name}” on Roommates, to share chores, "
        f"groceries and bills.\n\nJoin here: {url}\n\n"
        f"New to Roommates? The link asks you to sign up first (a minute) with this email address. "
        f"It works for {INVITE_DAYS} days.\n"
    )
    html = email.button_email(
        [
            "Hi!",
            f"{me.display_name} invited you to join “{house.name}” on Roommates, to share chores, groceries and bills.",
        ],
        f"Join {house.name}",
        url,
        f"New to Roommates? You'll sign up first (a minute) with this email address. The link works for {INVITE_DAYS} days.",
    )
    return subject, text, html


def find_open(db: Session, token: str) -> HouseholdInvite:
    """A pending, unexpired invite, or the same "expired or cancelled" answer for anything else."""
    row = db.scalar(select(HouseholdInvite).where(HouseholdInvite.token == token))
    if row is None or row.accepted_at is not None or row.expires_at <= datetime.now(UTC):
        raise NotFound(EXPIRED)
    return row


def invite(db: Session, me: HouseholdMember, emails: list[str]) -> EmailInviteResults:
    house = me.household
    member_emails = set(
        db.scalars(
            select(User.email)
            .join(HouseholdMember, HouseholdMember.user_id == User.id)
            .where(HouseholdMember.household_id == house.id, HouseholdMember.is_active)
        )
    )
    results = []
    for address in dict.fromkeys(e.strip().lower() for e in emails):  # in order, no repeats
        if address in member_emails:
            results.append(EmailInviteResult(email=address, status="member"))
            continue
        row = db.scalar(
            select(HouseholdInvite).where(
                HouseholdInvite.household_id == house.id,
                HouseholdInvite.email == address,
                HouseholdInvite.accepted_at.is_(None),
            )
        )
        if row is None:
            row = HouseholdInvite(household_id=house.id, email=address, invited_by_id=me.id)
            db.add(row)
        _new_link(row)  # inviting again sends a new link; the old one stops working
        db.flush()
        problem = email.deliver(address, *_message(me, private_link(row.token)))
        if problem is None:
            row.last_sent_at = datetime.now(UTC)
            results.append(EmailInviteResult(email=address, status="sent"))
        elif problem == email.NOT_SET_UP:
            results.append(EmailInviteResult(email=address, status="saved"))
        else:
            results.append(EmailInviteResult(email=address, status="failed", reason=problem))
    db.commit()
    return EmailInviteResults(results=results, link=link(house.invite_code), email_enabled=email.enabled())


def pending(db: Session, me: HouseholdMember) -> list[EmailInviteOut]:
    rows = db.scalars(
        select(HouseholdInvite)
        .where(HouseholdInvite.household_id == me.household_id, HouseholdInvite.accepted_at.is_(None))
        .order_by(HouseholdInvite.created_at)
    ).unique()
    return [_out(r, me) for r in rows]


def get(db: Session, invite_id: uuid.UUID) -> HouseholdInvite:
    row = db.get(HouseholdInvite, invite_id)
    if row is None or row.accepted_at is not None:
        raise NotFound("Invite not found")
    return row


def cancel(db: Session, row: HouseholdInvite, me: HouseholdMember) -> None:
    if me.role != "admin" and row.invited_by_id != me.id:
        raise Forbidden("Only an admin or whoever sent it can cancel an invite")
    db.delete(row)
    db.commit()


def mine(db: Session, user: User) -> list[MyInvite]:
    """Houses that invited my email, minus the ones I'm already in."""
    joined = {
        m.household_id
        for m in db.scalars(
            select(HouseholdMember).where(HouseholdMember.user_id == user.id, HouseholdMember.is_active)
        )
    }
    rows = db.scalars(
        select(HouseholdInvite)
        .where(
            HouseholdInvite.email == user.email.lower(),
            HouseholdInvite.accepted_at.is_(None),
            HouseholdInvite.expires_at > datetime.now(UTC),
        )
        .order_by(HouseholdInvite.created_at.desc())
    ).unique()
    return [
        MyInvite(
            household_name=r.household.name,
            invite_code=r.household.invite_code,
            token=r.token,
            invited_by=r.invited_by.display_name if r.invited_by else None,
            created_at=r.created_at,
        )
        for r in rows
        if r.household_id not in joined
    ]


def mark_accepted(db: Session, household_id: uuid.UUID, user: User) -> None:
    """Joining a house settles any email invite it sent me. The caller commits."""
    for row in db.scalars(
        select(HouseholdInvite).where(
            HouseholdInvite.household_id == household_id,
            HouseholdInvite.email == user.email.lower(),
            HouseholdInvite.accepted_at.is_(None),
        )
    ):
        row.accepted_at = datetime.now(UTC)


def _out(row: HouseholdInvite, me: HouseholdMember) -> EmailInviteOut:
    by = row.invited_by
    return EmailInviteOut(
        id=row.id,
        email=row.email,
        invited_by=MemberBrief(id=by.id, display_name=by.display_name) if by else None,
        created_at=row.created_at,
        last_sent_at=row.last_sent_at,
        can_cancel=me.role == "admin" or row.invited_by_id == me.id,
    )
