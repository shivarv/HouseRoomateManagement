"""Help requests: anyone can ask the house for a hand; anyone in the house can mark it done.

The first person to mark a request done wins: `mark_done` locks the row, so clicks that arrive
at the same moment are handled one after another and a later click never overwrites who helped.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import HelpRequest, HouseholdMember
from app.schemas.help import HelpRequestOut
from app.schemas.household import MemberBrief
from app.services import activity
from app.services.errors import Conflict, Forbidden, NotFound

RECENT_DONE_DAYS = 14  # done requests stay visible to everyone this long; mine stay forever
MAX_LIST = 200


def get(db: Session, request_id: uuid.UUID) -> HelpRequest:
    req = db.get(HelpRequest, request_id)
    if req is None:
        raise NotFound("Help request not found")
    return req


def _lock(db: Session, request_id: uuid.UUID) -> HelpRequest:
    # Lock just the row (the eager joins to members are outer joins, which can't be locked),
    # then reload it so we see what any click before ours committed.
    if db.scalar(select(HelpRequest.id).where(HelpRequest.id == request_id).with_for_update()):
        return db.get(HelpRequest, request_id, populate_existing=True)
    raise NotFound("Help request not found")


def create(db: Session, me: HouseholdMember, title: str, details: str | None) -> HelpRequest:
    req = HelpRequest(
        household_id=me.household_id,
        requester_id=me.id,
        title=title,
        details=details or None,
        status="open",
    )
    db.add(req)
    activity.record(db, me.household_id, "help_requested", me, subject_id=me.id, detail=title)
    db.commit()
    db.refresh(req)
    return req


def update(
    db: Session,
    request_id: uuid.UUID,
    me: HouseholdMember,
    title: str | None,
    details: str | None,
) -> HelpRequest:
    """Only the person who asked can edit, and only while nobody has done it yet."""
    req = _lock(db, request_id)
    if req.requester_id != me.id:
        raise Forbidden("Only the person who asked can edit this request")
    if req.status == "done":
        raise Conflict(f"{_name(req.done_by)} already did this, so it can't be edited")
    changed = False
    if title is not None and title != req.title:
        req.title, changed = title, True
    if details is not None and (details or None) != req.details:
        req.details, changed = details or None, True
    if changed:
        activity.record(
            db, req.household_id, "help_updated", me, subject_id=me.id, detail=req.title
        )
    db.commit()
    db.refresh(req)
    return req


def mark_done(db: Session, request_id: uuid.UUID, me: HouseholdMember) -> HelpRequest:
    req = _lock(db, request_id)
    if req.status == "done":
        if req.done_by_id == me.id:
            return req  # my own double-click or retry: same answer
        raise Conflict(f"{_name(req.done_by)} already marked it done")
    req.status = "done"
    req.done_by_id = me.id
    req.done_at = datetime.now(UTC)
    activity.record(
        db, req.household_id, "help_done", me, subject_id=req.requester_id, detail=req.title
    )
    db.commit()
    db.refresh(req)
    return req


def reopen(db: Session, request_id: uuid.UUID, me: HouseholdMember) -> HelpRequest:
    """Undo "done": the person who asked, or the person who marked it done."""
    req = _lock(db, request_id)
    if req.status == "open":
        return req
    if me.id not in (req.requester_id, req.done_by_id):
        raise Forbidden("Only the person who asked or the person who helped can undo this")
    previous = req.done_by_id
    req.status = "open"
    req.done_by_id = None
    req.done_at = None
    activity.record(
        db, req.household_id, "help_reopened", me, subject_id=previous, detail=req.title
    )
    db.commit()
    db.refresh(req)
    return req


def withdraw(db: Session, request_id: uuid.UUID, me: HouseholdMember) -> None:
    req = _lock(db, request_id)
    if req.requester_id != me.id:
        raise Forbidden("Only the person who asked can withdraw this request")
    if req.status == "done":
        raise Conflict(f"{_name(req.done_by)} already did this, so it can't be withdrawn")
    activity.record(db, req.household_id, "help_withdrawn", me, subject_id=me.id, detail=req.title)
    db.delete(req)
    db.commit()


def visible(db: Session, memberships: list[HouseholdMember]) -> list[HelpRequest]:
    """Open requests in my households, recently done ones, and every request I made."""
    if not memberships:
        return []
    cutoff = datetime.now(UTC) - timedelta(days=RECENT_DONE_DAYS)
    return list(
        db.scalars(
            select(HelpRequest)
            .where(
                HelpRequest.household_id.in_([m.household_id for m in memberships]),
                or_(
                    HelpRequest.status == "open",
                    HelpRequest.done_at >= cutoff,
                    HelpRequest.requester_id.in_([m.id for m in memberships]),
                ),
            )
            .order_by(HelpRequest.created_at.desc())
            .limit(MAX_LIST)
        ).unique()
    )


def _name(member: HouseholdMember | None) -> str:
    return member.display_name if member else "Someone"


def _brief(member: HouseholdMember | None) -> MemberBrief | None:
    return MemberBrief(id=member.id, display_name=member.display_name) if member else None


def out(req: HelpRequest, me: HouseholdMember) -> HelpRequestOut:
    return HelpRequestOut(
        id=req.id,
        household_id=req.household_id,
        household_name=me.household.name,
        requester=_brief(req.requester),
        title=req.title,
        details=req.details,
        status=req.status,
        done_by=_brief(req.done_by),
        done_at=req.done_at,
        created_at=req.created_at,
        updated_at=req.updated_at,
        is_mine=req.requester_id == me.id,
        can_reopen=req.status == "done" and me.id in (req.requester_id, req.done_by_id),
    )
