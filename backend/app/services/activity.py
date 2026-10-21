import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActivityEvent, Chore, HouseholdMember
from app.schemas.chore import ActivityOut
from app.schemas.household import MemberBrief

MAX_FEED = 200
MAX_MONTH = 5000  # a busy month for 8 people is a few hundred events


def record(
    db: Session,
    household_id: uuid.UUID,
    action: str,
    actor: HouseholdMember | None,
    *,
    chore: Chore | None = None,
    subject_id: uuid.UUID | None = None,
    assignee_id: uuid.UUID | None = None,
    due_date: date | None = None,
    detail: str | None = None,
) -> None:
    """Append an event to the household's activity feed. The caller commits."""
    db.add(
        ActivityEvent(
            household_id=household_id,
            actor_id=actor.id if actor else None,
            action=action,
            chore_id=chore.id if chore else None,
            chore_name=chore.name if chore else None,
            subject_id=subject_id,
            assignee_id=assignee_id,
            due_date=due_date,
            detail=detail[:200] if detail else None,
        )
    )


def feed(
    db: Session, household_id: uuid.UUID, limit: int, before: datetime | None
) -> list[ActivityEvent]:
    query = select(ActivityEvent).where(ActivityEvent.household_id == household_id)
    if before is not None:
        query = query.where(ActivityEvent.created_at < before)
    query = query.order_by(ActivityEvent.created_at.desc()).limit(min(limit, MAX_FEED))
    return list(db.scalars(query).unique())


def month_feed(
    db: Session, household_id: uuid.UUID, month_start: date, timezone: str
) -> list[ActivityEvent]:
    """Every event in a calendar month of the household's timezone, newest first."""
    tz = ZoneInfo(timezone)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    start = datetime.combine(month_start, time.min, tz)
    end = datetime.combine(next_month, time.min, tz)
    query = (
        select(ActivityEvent)
        .where(
            ActivityEvent.household_id == household_id,
            ActivityEvent.created_at >= start,
            ActivityEvent.created_at < end,
        )
        .order_by(ActivityEvent.created_at.desc())
        .limit(MAX_MONTH)
    )
    return list(db.scalars(query).unique())


def _brief(member: HouseholdMember | None) -> MemberBrief | None:
    return MemberBrief(id=member.id, display_name=member.display_name) if member else None


def event_out(event: ActivityEvent) -> ActivityOut:
    return ActivityOut(
        id=event.id,
        action=event.action,
        created_at=event.created_at,
        actor=_brief(event.actor),
        subject=_brief(event.subject),
        assignee=_brief(event.assignee),
        chore_id=event.chore_id,
        chore_name=event.chore_name,
        due_date=event.due_date,
        detail=event.detail,
    )
