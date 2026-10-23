"""Guided set-up: a new house, its people, chores, groceries and bills, created in one go.

Nothing is saved unless all of it is valid, so a half-finished house can't be left behind.
"""

from sqlalchemy.orm import Session

from app.models import Bill, GroceryCategory, GroceryPreset, HouseholdMember, User
from app.schemas.setup import (
    MAX_ITEMS,
    HouseholdSetup,
    SetupBill,
    SetupChore,
    SetupGrocery,
    SetupTemplate,
)
from app.services import activity, chores, clock, grocery_settings, households
from app.services.errors import BadRequest

# What the set-up screens prefill, in order: asking for 4 chores gives the first 4.
TEMPLATE_CHORES = (
    SetupChore(name="Cooking", frequency="daily", assignment_mode="rotation"),
    SetupChore(name="Bathroom cleaning", frequency="weekly", assignment_mode="rotation"),
    SetupChore(name="Room cleaning", frequency="weekly", assignment_mode="rotation"),
    SetupChore(name="Utensils cleaning", frequency="daily", assignment_mode="rotation"),
    SetupChore(name="Floor cleaning", frequency="weekly", assignment_mode="rotation"),
    SetupChore(name="Bin clearance", frequency="daily", assignment_mode="open"),
    SetupChore(name="Kitchen cleaning", frequency="weekly", assignment_mode="rotation"),
    SetupChore(name="Fridge cleaning", frequency="weekly", assignment_mode="rotation"),
    SetupChore(name="Vacuuming", frequency="weekly", assignment_mode="rotation"),
    SetupChore(name="Dusting & windows", frequency="weekly", assignment_mode="rotation"),
)

TEMPLATE_GROCERIES = (
    SetupGrocery(name="Eggs", category_key="groceries"),
    SetupGrocery(name="Milk", category_key="groceries"),
    SetupGrocery(name="Rice", category_key="groceries"),
    SetupGrocery(name="Bread", category_key="groceries"),
    SetupGrocery(name="Oil", category_key="groceries"),
    SetupGrocery(name="Onions", category_key="groceries"),
    SetupGrocery(name="Toothpaste", category_key="toiletries"),
    SetupGrocery(name="Dish soap", category_key="cleaning"),
    SetupGrocery(name="Garbage bags", category_key="cleaning"),
    SetupGrocery(name="Toilet paper", category_key="household"),
)

TEMPLATE_BILLS = (
    SetupBill(name="Rent", icon="🏠", payer_mode="everyone", amount_type="fixed"),
    SetupBill(name="Electricity", icon="⚡", payer_mode="anyone", amount_type="variable"),
    SetupBill(name="Water", icon="💧", payer_mode="anyone", amount_type="variable"),
    SetupBill(name="Gas", icon="🔥", payer_mode="anyone", amount_type="variable"),
    SetupBill(name="Internet / WiFi", icon="📶", payer_mode="anyone", amount_type="fixed"),
    SetupBill(name="Trash collection", icon="🗑️", payer_mode="anyone", amount_type="fixed"),
    SetupBill(name="Maintenance", icon="🛠️", payer_mode="everyone", amount_type="fixed"),
    SetupBill(name="Renter's insurance", icon="🛡️", payer_mode="anyone", amount_type="fixed"),
    SetupBill(name="Cleaning service", icon="🧹", payer_mode="everyone", frequency="weekly", amount_type="fixed"),
    SetupBill(name="Streaming", icon="📺", payer_mode="anyone", amount_type="fixed"),
)


def template() -> SetupTemplate:
    return SetupTemplate(
        max_items=MAX_ITEMS,
        chores=list(TEMPLATE_CHORES),
        groceries=list(TEMPLATE_GROCERIES),
        bills=list(TEMPLATE_BILLS),
        categories=[
            {"key": key, "label": label, "icon": icon}
            for key, label, icon in grocery_settings.STANDARD_CATEGORIES
        ],
    )


def create(db: Session, user: User, body: HouseholdSetup) -> HouseholdMember:
    keys = {key for key, _, _ in grocery_settings.STANDARD_CATEGORIES}
    for g in body.groceries:
        if g.category_key not in keys:
            raise BadRequest(f"{g.name}: unknown category “{g.category_key}”")
    people = [user.name, *body.roommates]
    if len({p.lower() for p in people}) != len(people):
        raise BadRequest(f"A roommate has your name, {user.name}: give them a different one")
    names = {p.lower() for p in people}
    for c in body.chores:
        if c.people is None or c.assignment_mode != "rotation":
            continue
        if not c.people:
            raise BadRequest(f"{c.name}: pick at least one person to take turns")
        missing = [p for p in c.people if p.lower() not in names]
        if missing:
            raise BadRequest(f"{c.name}: “{missing[0]}” isn't one of the people in the house")
        if len({p.lower() for p in c.people}) != len(c.people):
            raise BadRequest(f"{c.name}: someone is in the rotation twice")
    for b in body.bills:
        if b.payer_mode == "one" and b.payer_name.lower() not in names:
            raise BadRequest(f"{b.name}: “{b.payer_name}” isn't one of the people in the house")

    household, admin = households.new_household(db, user, body.name, body.address, body.timezone)
    today = clock.today_in(household.timezone)

    # People first, so every chore rotates through all of them.
    by_name = {user.name.lower(): admin}
    for name in body.roommates:
        member = HouseholdMember(
            household_id=household.id, display_name=name, role="member", is_active=True
        )
        db.add(member)
        by_name[name.lower()] = member
    db.flush()
    for member in by_name.values():
        if member is not admin:
            activity.record(db, household.id, "member_added", admin, subject_id=member.id)

    for c in body.chores:
        member_ids = None  # everyone
        if c.people is not None and c.assignment_mode == "rotation":
            member_ids = [by_name[p.lower()].id for p in c.people]
        chores.create_chore(
            db,
            household,
            c.name,
            member_ids=member_ids,
            today=today,
            frequency=c.frequency,
            assignment_mode=c.assignment_mode,
        )

    # The standard sections, then only the quick-add items picked here.
    for position, (key, label, icon) in enumerate(grocery_settings.STANDARD_CATEGORIES):
        db.add(
            GroceryCategory(
                household_id=household.id, key=key, label=label, icon=icon, position=position
            )
        )
    for position, g in enumerate(body.groceries):
        db.add(
            GroceryPreset(
                household_id=household.id, name=g.name, category_key=g.category_key, position=position
            )
        )

    for position, b in enumerate(body.bills):
        payer = by_name[b.payer_name.lower()] if b.payer_mode == "one" else None
        db.add(
            Bill(
                household_id=household.id,
                name=b.name,
                icon=b.icon,
                payer_mode=b.payer_mode,
                payer_id=payer.id if payer else None,
                frequency=b.frequency,
                due_day=b.due_day,
                amount_type=b.amount_type,
                amount_cents=b.amount_cents if b.amount_type == "fixed" else None,
                currency=body.currency,
                position=position,
                is_active=True,
            )
        )
    db.commit()
    return admin
