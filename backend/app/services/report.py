"""Monthly report: who did which chore how many times, who missed turns, who covered."""

import calendar
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select, union
from sqlalchemy.orm import Session

from app.models import Chore, ChoreLog, ChoreTask, Household, HouseholdMember
from app.schemas.chore import ChoreBrief, ChoreReport, LeaderboardRow, ReportOut, ReportRow
from app.schemas.household import MemberBrief
from app.services import rotation
from app.services.errors import BadRequest


@dataclass
class _Stats:
    done: int = 0
    turns: int = 0
    missed: int = 0
    covered_by_others: int = 0
    covered_for_others: int = 0
    last_done: date | None = None

    def did_it(self, on: date) -> None:
        self.done += 1
        self.last_done = max(self.last_done or on, on)

    @property
    def any(self) -> bool:
        return bool(self.done or self.turns)


def parse_month(value: str) -> date:
    try:
        year, month = (int(p) for p in value.split("-"))
        return date(year, month, 1)
    except (ValueError, TypeError) as exc:
        raise BadRequest("month must look like YYYY-MM") from exc


def month_key(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def available_months(db: Session, household_id: str, today: date) -> list[str]:
    task_months = (
        select(func.to_char(ChoreTask.due_date, "YYYY-MM").label("m"))
        .join(Chore)
        .where(Chore.household_id == household_id)
    )
    log_months = (
        select(func.to_char(ChoreLog.done_on, "YYYY-MM").label("m"))
        .join(Chore)
        .where(Chore.household_id == household_id)
    )
    months = set(db.scalars(select(union(task_months, log_months).subquery().c.m)))
    months.add(month_key(today))
    return sorted(months, reverse=True)


def month_report(db: Session, household: Household, month_start: date, today: date) -> ReportOut:
    month_end = month_start.replace(day=calendar.monthrange(month_start.year, month_start.month)[1])
    members = list(
        db.scalars(
            select(HouseholdMember)
            .where(HouseholdMember.household_id == household.id)
            .order_by(HouseholdMember.created_at)
        )
    )
    by_id = {m.id: m for m in members}
    active_count = sum(1 for m in members if m.is_active) or 1

    tasks = list(
        db.scalars(
            select(ChoreTask)
            .join(Chore)
            .where(
                Chore.household_id == household.id,
                ChoreTask.due_date.between(month_start, min(month_end, today)),
            )
        ).unique()
    )
    logs = list(
        db.scalars(
            select(ChoreLog)
            .join(Chore)
            .where(
                Chore.household_id == household.id, ChoreLog.done_on.between(month_start, month_end)
            )
        ).unique()
    )

    all_chores = list(
        db.scalars(
            select(Chore)
            .where(Chore.household_id == household.id)
            .order_by(Chore.position, Chore.created_at)
        )
    )
    used = {t.chore_id for t in tasks} | {log.chore_id for log in logs}
    shown = [c for c in all_chores if c.is_active or c.id in used]

    stats: dict = {c.id: {} for c in shown}

    def s(chore_id, member_id) -> _Stats:
        return stats[chore_id].setdefault(member_id, _Stats())

    for t in tasks:
        if t.chore_id not in stats:
            continue
        mine = s(t.chore_id, t.member_id)
        mine.turns += 1
        if t.status == "done":
            doer_id = t.completed_by_id or t.member_id
            s(t.chore_id, doer_id).did_it(t.due_date)
            if doer_id != t.member_id:
                mine.covered_by_others += 1
                s(t.chore_id, doer_id).covered_for_others += 1
        elif rotation.period_end(t.due_date, t.chore.frequency) < today:
            mine.missed += 1
    for log in logs:
        if log.chore_id in stats:
            s(log.chore_id, log.member_id).did_it(log.done_on)

    def brief(m: HouseholdMember) -> MemberBrief:
        return MemberBrief(id=m.id, display_name=m.display_name)

    chore_reports = []
    totals: dict = {}
    for chore in shown:
        is_rotation = not chore.is_open
        per_member = stats[chore.id]
        total_done = sum(x.done for x in per_member.values())
        rows = []
        for m in members:
            x = per_member.get(m.id, _Stats())
            if not m.is_active and not x.any:
                continue
            rows.append(
                ReportRow(
                    member=brief(m),
                    is_active=m.is_active,
                    done=x.done,
                    share=round(x.done / total_done, 3) if total_done else 0.0,
                    turns=x.turns if is_rotation else None,
                    missed=x.missed if is_rotation else None,
                    covered_by_others=x.covered_by_others if is_rotation else None,
                    covered_for_others=x.covered_for_others if is_rotation else None,
                    last_done=x.last_done,
                )
            )
            t = totals.setdefault(m.id, _Stats())
            t.done += x.done
            t.missed += x.missed
            t.covered_for_others += x.covered_for_others
        rows.sort(key=lambda r: (-r.done, r.missed or 0, r.member.display_name.lower()))
        chore_reports.append(
            ChoreReport(
                chore=ChoreBrief(
                    id=chore.id,
                    name=chore.name,
                    frequency=chore.frequency,
                    assignment_mode=chore.assignment_mode,
                ),
                is_active=chore.is_active,
                total_done=total_done,
                total_missed=sum(x.missed for x in per_member.values()) if is_rotation else None,
                rows=rows,
            )
        )

    leaderboard = [
        LeaderboardRow(
            member=brief(by_id[mid]),
            is_active=by_id[mid].is_active,
            done=t.done,
            missed=t.missed,
            covered_for_others=t.covered_for_others,
        )
        for mid, t in totals.items()
    ]
    leaderboard.sort(key=lambda r: (-r.done, r.missed, r.member.display_name.lower()))

    return ReportOut(
        month=month_key(month_start),
        start=month_start,
        end=month_end,
        is_current=month_key(month_start) == month_key(today),
        fair_share=round(1 / active_count, 3),
        chores=chore_reports,
        leaderboard=leaderboard,
    )
