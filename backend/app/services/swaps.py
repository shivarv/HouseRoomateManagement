"""Turn swaps: hand one rotation turn to someone else, and take their next turn in return.

A swap only changes who is on duty on two dates (the turn given away and the payback turn). The
rotation order and start date are never touched, so the cycle continues unchanged afterwards.

Concurrency: the first "yes" is final. `accept` and `cancel` lock the swap row, so clicks that
arrive at the same moment are handled one after another. Anything that picks a payback turn
or creates a request also locks the chore row, so two swaps on the same chore can't both pick
the same turn. There are no uniqueness rules in the database: a turn may be swapped again later.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.models import Chore, ChoreSwap, ChoreTask, HouseholdMember
from app.schemas.chore import ChoreBrief, SwapOut
from app.schemas.household import MemberBrief
from app.services import activity, rotation
from app.services.errors import BadRequest, Conflict, Forbidden, NotFound

MAX_AHEAD_DAYS = 31


# --- Who is on duty ---------------------------------------------------------------------------


class Duty:
    """The rotation formula for one chore, with accepted swaps laid on top."""

    def __init__(self, chore: Chore, swaps: list[ChoreSwap]):
        self.order = [r.member_id for r in chore.rotation]
        self.start = chore.rotation_start_date
        self.step = rotation.step_days(chore.frequency)
        # The most recently accepted swap on a date wins, so a turn can be swapped again.
        self.latest: dict[date, ChoreSwap] = {}
        for swap in sorted(swaps, key=lambda s: s.resolved_at or s.created_at):
            self.latest[swap.given_date] = swap
            if swap.payback_date is not None:
                self.latest[swap.payback_date] = swap

    def on_duty(self, day: date) -> uuid.UUID | None:
        """Who is on duty for the period starting on `day`."""
        swap = self.latest.get(day)
        if swap is not None:
            return swap.acceptor_id if swap.given_date == day else swap.requester_id
        return rotation.assignee(self.order, self.start, day, self.step)

    def swap_on(self, day: date) -> ChoreSwap | None:
        return self.latest.get(day)

    def next_turn(self, member_id: uuid.UUID, after: date) -> date | None:
        """Start of the first period after `after` in which `member_id` is on duty."""
        day = after
        for _ in range(2 * len(self.order) + len(self.latest) + 1):
            day += timedelta(days=self.step)
            if self.on_duty(day) == member_id:
                return day
        return None


def load_duty(db: Session, chore: Chore, since: date | None = None) -> Duty:
    query = select(ChoreSwap).where(ChoreSwap.chore_id == chore.id, ChoreSwap.status == "accepted")
    if since is not None:
        query = query.where(or_(ChoreSwap.given_date >= since, ChoreSwap.payback_date >= since))
    return Duty(chore, list(db.scalars(query).unique()))


# --- Housekeeping -----------------------------------------------------------------------------


def _resolve_open(db: Session, swap: ChoreSwap, status: str) -> bool:
    """Close an open request unless someone else just did (the WHERE re-checks the status)."""
    result = db.execute(
        update(ChoreSwap)
        .where(ChoreSwap.id == swap.id, ChoreSwap.status == "open")
        .values(status=status, resolved_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


def expire_stale(db: Session, chore: Chore, today: date) -> None:
    """Close open requests whose turn is over, or that are no longer the requester's turn."""
    pending = list(
        db.scalars(
            select(ChoreSwap).where(ChoreSwap.chore_id == chore.id, ChoreSwap.status == "open")
        ).unique()
    )
    if not pending:
        return
    current = rotation.period_start(today, chore.frequency)
    duty = load_duty(db, chore, since=min(s.given_date for s in pending))
    for swap in pending:
        if swap.given_date < current:
            if _resolve_open(db, swap, "expired"):
                activity.record(
                    db,
                    chore.household_id,
                    "swap_expired",
                    None,
                    chore=chore,
                    subject_id=swap.requester_id,
                    assignee_id=swap.requester_id,
                    due_date=swap.given_date,
                )
        elif duty.on_duty(swap.given_date) != swap.requester_id:
            if _resolve_open(db, swap, "cancelled"):
                activity.record(
                    db,
                    chore.household_id,
                    "swap_cancelled",
                    None,
                    chore=chore,
                    subject_id=swap.requester_id,
                    assignee_id=swap.requester_id,
                    due_date=swap.given_date,
                    detail="withdrawn",
                )


def cancel_for_chore(
    db: Session, chore: Chore, today: date, member_ids: set[uuid.UUID] | None = None
) -> None:
    """Withdraw live swaps on current/future turns, e.g. when a person leaves the rotation or
    the chore is paused or changes frequency. With `member_ids`, only swaps involving them."""
    current = rotation.period_start(today, chore.frequency)
    query = select(ChoreSwap).where(
        ChoreSwap.chore_id == chore.id,
        ChoreSwap.status.in_(["open", "accepted"]),
        or_(ChoreSwap.given_date >= current, ChoreSwap.payback_date >= current),
    )
    if member_ids:
        query = query.where(
            or_(ChoreSwap.requester_id.in_(member_ids), ChoreSwap.acceptor_id.in_(member_ids))
        )
    for swap in db.scalars(query).unique():
        swap.status = "cancelled"
        swap.resolved_at = datetime.now(UTC)
        activity.record(
            db,
            chore.household_id,
            "swap_cancelled",
            None,
            chore=chore,
            subject_id=swap.acceptor_id or swap.requester_id,
            assignee_id=swap.requester_id,
            due_date=swap.given_date,
            detail="withdrawn",
        )
    db.flush()


# --- Locks ------------------------------------------------------------------------------------


def _lock_chore(db: Session, chore_id: uuid.UUID) -> Chore:
    chore = db.scalars(
        select(Chore)
        .where(Chore.id == chore_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one_or_none()
    if chore is None:
        raise NotFound("Chore not found")
    return chore


def _lock_swap(db: Session, swap_id: uuid.UUID) -> ChoreSwap:
    # Lock just the row (the eager joins to members are outer joins, which can't be locked),
    # then reload it so we see what any click before ours committed.
    locked = db.scalar(select(ChoreSwap.id).where(ChoreSwap.id == swap_id).with_for_update())
    if locked is None:
        raise NotFound("Swap request not found")
    return db.get(ChoreSwap, swap_id, populate_existing=True)


def get_swap(db: Session, swap_id: uuid.UUID) -> ChoreSwap:
    swap = db.get(ChoreSwap, swap_id)
    if swap is None:
        raise NotFound("Swap request not found")
    return swap


def _stored_turn(db: Session, chore_id: uuid.UUID, due: date) -> ChoreTask | None:
    return db.scalar(
        select(ChoreTask)
        .where(ChoreTask.chore_id == chore_id, ChoreTask.due_date == due)
        .execution_options(populate_existing=True)
    )


# --- Actions ----------------------------------------------------------------------------------


def request(
    db: Session, chore_id: uuid.UUID, me: HouseholdMember, due: date, note: str | None, today: date
) -> ChoreSwap:
    """Ask the house to take one of my turns. Asking twice returns the existing request."""
    chore = _lock_chore(db, chore_id)
    if chore.is_open or not chore.is_active:
        raise BadRequest("Only active rotation chores can be swapped")
    if due != rotation.period_start(due, chore.frequency):
        raise BadRequest("That date isn't the start of a turn")
    if due < rotation.period_start(today, chore.frequency):
        raise BadRequest("That turn is already over")
    if due > today + timedelta(days=MAX_AHEAD_DAYS):
        raise BadRequest("You can only ask for a swap up to a month ahead")
    if load_duty(db, chore, since=due).on_duty(due) != me.id:
        raise BadRequest("That isn't your turn")
    turn = _stored_turn(db, chore.id, due)
    if turn is not None and turn.status == "done":
        raise BadRequest("That turn is already done")

    existing = db.scalar(
        select(ChoreSwap).where(
            ChoreSwap.chore_id == chore.id,
            ChoreSwap.given_date == due,
            ChoreSwap.status == "open",
        )
    )
    if existing is not None:
        if existing.requester_id == me.id:
            return existing  # double-click or a second device: one request, not two
        _resolve_open(db, existing, "cancelled")  # left over from the turn's previous owner

    swap = ChoreSwap(
        household_id=chore.household_id,
        chore_id=chore.id,
        given_date=due,
        requester_id=me.id,
        status="open",
        note=note.strip() or None if note else None,
    )
    db.add(swap)
    activity.record(
        db,
        chore.household_id,
        "swap_requested",
        me,
        chore=chore,
        assignee_id=me.id,
        due_date=due,
        detail=swap.note,
    )
    db.commit()
    db.refresh(swap)
    return swap


def accept(db: Session, swap_id: uuid.UUID, me: HouseholdMember, today: date) -> ChoreSwap:
    """Take someone's turn. The first person to accept wins; later clicks change nothing."""
    from app.services import tasks  # local import: tasks depends on this module

    swap = _lock_swap(db, swap_id)
    if swap.status == "accepted":
        if swap.acceptor_id == me.id:
            return swap  # my own retry: same answer
        raise Conflict(f"{swap.acceptor.display_name} already took it")
    if swap.status != "open":
        raise Conflict("This swap request is no longer open")
    if swap.requester_id == me.id:
        raise BadRequest("You can't take your own swap")

    chore = _lock_chore(db, swap.chore_id)
    if me.id not in [r.member_id for r in chore.rotation]:
        raise BadRequest(f"You're not in the rotation for {chore.name}")
    if swap.given_date < rotation.period_start(today, chore.frequency):
        raise Conflict("This swap request is no longer open")
    duty = load_duty(db, chore, since=swap.given_date)
    if duty.on_duty(swap.given_date) != swap.requester_id:
        raise Conflict("This swap request is no longer open")
    turn = _stored_turn(db, chore.id, swap.given_date)
    if turn is not None and turn.status == "done":
        raise Conflict("This turn is already done")
    payback = duty.next_turn(me.id, swap.given_date)
    if payback is None:
        raise BadRequest(f"You have no upcoming {chore.name} turn to give back")

    swap.status = "accepted"
    swap.acceptor_id = me.id
    swap.payback_date = payback
    swap.resolved_at = datetime.now(UTC)
    activity.record(
        db,
        chore.household_id,
        "swap_accepted",
        me,
        chore=chore,
        subject_id=swap.requester_id,
        assignee_id=swap.requester_id,
        due_date=swap.given_date,
        detail=payback.isoformat(),
    )
    db.flush()
    tasks.ensure_chore(db, chore, today)  # the given turn may be the current, already saved one
    db.commit()
    db.refresh(swap)
    return swap


def cancel(db: Session, swap_id: uuid.UUID, me: HouseholdMember, today: date) -> ChoreSwap:
    """Withdraw a request, or undo an accepted swap before its turn is done."""
    from app.services import tasks  # local import: tasks depends on this module

    swap = _lock_swap(db, swap_id)
    if swap.status == "cancelled":
        return swap
    if swap.status == "expired":
        raise Conflict("This swap request has expired")

    was_accepted = swap.status == "accepted"
    if not was_accepted and me.id != swap.requester_id:
        raise Forbidden(f"Only {swap.requester.display_name} can cancel this request")
    if was_accepted:
        if me.id not in (swap.requester_id, swap.acceptor_id):
            raise Forbidden("Only the two people in this swap can cancel it")
        chore = _lock_chore(db, swap.chore_id)
        turn = _stored_turn(db, chore.id, swap.given_date)
        if turn is not None and turn.status == "done":
            raise BadRequest("This swap's turn is already done")
        dates = [swap.given_date, swap.payback_date]
        later = db.scalar(
            select(ChoreSwap.id).where(
                ChoreSwap.chore_id == chore.id,
                ChoreSwap.status == "accepted",
                ChoreSwap.id != swap.id,
                ChoreSwap.resolved_at > swap.resolved_at,
                or_(ChoreSwap.given_date.in_(dates), ChoreSwap.payback_date.in_(dates)),
            )
        )
        if later is not None:
            raise BadRequest("This turn was swapped again. Cancel the later swap first")

    other = (
        None
        if not was_accepted
        else swap.acceptor_id
        if me.id == swap.requester_id
        else swap.requester_id
    )
    swap.status = "cancelled"
    swap.resolved_at = datetime.now(UTC)
    activity.record(
        db,
        swap.household_id,
        "swap_cancelled",
        me,
        chore=swap.chore,
        subject_id=other,
        assignee_id=swap.requester_id,
        due_date=swap.given_date,
    )
    db.flush()
    if was_accepted:
        tasks.ensure_chore(db, swap.chore, today)  # put the current turn back if it was swapped
    db.commit()
    db.refresh(swap)
    return swap


# --- Reading ----------------------------------------------------------------------------------


def open_requests(db: Session, household_id: uuid.UUID) -> list[ChoreSwap]:
    return list(
        db.scalars(
            select(ChoreSwap)
            .where(ChoreSwap.household_id == household_id, ChoreSwap.status == "open")
            .order_by(ChoreSwap.given_date, ChoreSwap.created_at)
        ).unique()
    )


def _brief(member: HouseholdMember | None) -> MemberBrief | None:
    return MemberBrief(id=member.id, display_name=member.display_name) if member else None


def swap_out(db: Session, swap: ChoreSwap, me: HouseholdMember) -> SwapOut:
    chore = swap.chore
    can_accept = (
        swap.status == "open"
        and me.id != swap.requester_id
        and me.id in [r.member_id for r in chore.rotation]
    )
    preview = (
        load_duty(db, chore, since=swap.given_date).next_turn(me.id, swap.given_date)
        if can_accept
        else None
    )
    return SwapOut(
        id=swap.id,
        household_id=swap.household_id,
        household_name=me.household.name,
        chore=ChoreBrief(
            id=chore.id,
            name=chore.name,
            frequency=chore.frequency,
            assignment_mode=chore.assignment_mode,
        ),
        given_date=swap.given_date,
        period_end=rotation.period_end(swap.given_date, chore.frequency),
        requester=_brief(swap.requester),
        acceptor=_brief(swap.acceptor),
        payback_date=swap.payback_date,
        status=swap.status,
        note=swap.note,
        created_at=swap.created_at,
        is_mine=swap.requester_id == me.id,
        can_accept=can_accept and preview is not None,
        payback_preview=preview,
    )
